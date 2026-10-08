"""Does the day-shard reader accept only the declared writer-owned files?

The fixture tests the day shape, read order, and named production readers. The
list of production readers is fixed and written out here, so this test costs the
same however much the repository grows (`CLAUDE.md` section 13).

A day is a directory, so a `<DD>.csv` beside one is a name no writer spells
and the walk refuses it with every other stray. The one file a month folder may
hold is a closed month's own `settled.csv`, which reads back as the days it
replaced.
"""

from __future__ import annotations

import csv
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_shards, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.validation_row import ValidationRow

pytestmark = pytest.mark.contract

#: The committed tree holding one ledger root of writer-owned files. A fixture
#: rather than the archive, so this costs one directory whatever `state/` grows
#: to (Guardrail #12).
FIXTURE: Final = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "day-shards"

#: The day directory's three writer files, newest attempt last.
WRITERS: Final = (
    "2026-09-18-1-1-work-00.csv",
    "2026-09-18-1-1-work-01.csv",
    "2026-09-18-1-2-work-00.csv",
)


def _root() -> Path:
    """The fixture ledger root, read inside the test that needs it.

    Never at module scope: a fixture opened while the module loads fails before
    any test owns the failure, and takes every test in the file with it.
    """
    root = FIXTURE / "writer-files" / "candidate-models"
    assert root.is_dir(), f"the day-shards fixture is missing at {root}"
    return root


def _rows_of(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_the_walk_reads_every_writer_file_of_a_day_and_nothing_else() -> None:
    """One day directory, three writers, one recorded day."""
    root = _root()

    every = list(day_shards.shard_files(root, days=UNBOUNDED_WINDOW))
    assert [path.name for path in every] == list(WRITERS)
    assert [day_shards.date_of(path) for path in every] == ["2026-09-18"] * len(WRITERS)

    settled = day_shards.settled_rows(root, ledger.VALIDATION_KEY, ValidationRow, days=1)
    assert len(settled) == 3
    assert [row["model_id"] for row in settled] == ["candidate-0", "candidate-extra", "candidate-1"]
    assert settled[0]["articles"] == "14"
    assert settled[0]["measured_hhem"] == "0.5"
    assert list(day_shards.shard_files(root.parent / "never-written", days=1)) == []


def test_the_cover_counts_recorded_days_and_never_the_files_inside_them(
    tmp_path: Path,
) -> None:
    """A day of three writers is one day, so a cover of 1 takes all three."""
    source = _root() / "2026" / "09" / "18"
    for date in ("17", "18"):
        day = tmp_path / "2026" / "09" / date
        day.mkdir(parents=True)
        for name in WRITERS:
            shutil.copy(source / name, day / name.replace("2026-09-18", f"2026-09-{date}"))

    newest = day_shards.shard_files(tmp_path, days=1)
    assert [day_shards.date_of(path) for path in newest] == ["2026-09-18"] * len(WRITERS)
    assert len(list(day_shards.shard_files(tmp_path, days=2))) == 2 * len(WRITERS)


def test_a_day_file_beside_the_day_directories_stops_the_read(tmp_path: Path) -> None:
    """There is no head above a day, so `<DD>.csv` is a name no writer spells.

    It used to be a shape of its own and the walk read it as one recorded day.
    A reader that still took it would fold a day twice - once from the file and
    once from the directory beside it - and report the total as an answer.
    """
    day = tmp_path / "2026" / "09" / "18"
    day.mkdir(parents=True)
    shutil.copy(_root() / "2026" / "09" / "18" / WRITERS[0], day / WRITERS[0])
    shutil.copy(_root() / "2026" / "09" / "18" / WRITERS[0], tmp_path / "2026" / "09" / "17.csv")

    with pytest.raises(ValueError, match=r"17\.csv"):
        list(day_shards.shard_files(tmp_path, days=UNBOUNDED_WINDOW))
    assert day_shards.one_day(tmp_path, "2026-09-17") == []


def test_settled_sorts_below_every_writer_file(tmp_path: Path) -> None:
    """A closed day's fold reads first, and a straggler beside it reads after."""
    day = tmp_path / "2026" / "09" / "18"
    day.mkdir(parents=True)
    columns = ValidationRow.csv_columns()
    settled = _rows_of(_root() / "2026" / "09" / "18" / WRITERS[0])
    (day / day_shards.SETTLED_NAME).write_text(
        ledger.render_file(columns, settled), encoding="utf-8", newline=""
    )
    shutil.copy(
        _root() / "2026" / "09" / "18" / "2026-09-18-1-2-work-00.csv",
        day / "2026-09-18-1-2-work-00.csv",
    )

    order = [path.name for path in day_shards.shard_files(tmp_path, days=UNBOUNDED_WINDOW)]
    assert order == ["2026-09-18-1-2-work-00.csv", day_shards.SETTLED_NAME]

    # Reading order is not listing order. `settled.csv` holds rows that already
    # won a settlement, so it reads at attempt 0 and the straggler corrects it.
    rows = day_shards.settled_rows(tmp_path, ledger.VALIDATION_KEY, ValidationRow, days=1)
    assert [row["articles"] for row in rows] == ["14", "12"]


def test_every_name_no_writer_owns_reads_and_reads_before_every_writer_file() -> None:
    """A migrated day, read back whole: the reserved names first, the straggler last.

    `before-partition.csv` is what the migration wrote for the bytes a committed
    head already held, and nothing read one back until the first real read of a
    migrated tree stopped on it. Three names are reserved and all three sort at
    attempt 0, so a writer file always corrects them rather than the other way
    round.

    Held against a fixture day and never `state/`, so it costs one directory
    whatever the archive grows to (Guardrail #12).
    """
    root = FIXTURE / "migrated-day" / "candidate-models"
    assert root.is_dir(), f"the migrated-day fixture is missing at {root}"

    # Listing order is alphabetical and reading order is not: the writer file
    # lists first and reads last, because its attempt is 2 and theirs is 0.
    assert [path.name for path in day_shards.shard_files(root, days=UNBOUNDED_WINDOW)] == [
        "2026-09-19-1-2-work-00.csv",
        ledger.BEFORE_PARTITION_NAME,
        day_shards.SETTLED_NAME,
    ]

    rows = day_shards.settled_rows(root, ledger.VALIDATION_KEY, ValidationRow, days=1)
    # First seen first, so the pre-identity bytes open the answer and the fold's
    # own row follows them.
    assert [row["model_id"] for row in rows] == ["candidate-0", "candidate-extra", "candidate-1"]
    # The straggler corrects the pre-identity row rather than repeating it: 11
    # items where the migrated bytes said 9, and nothing else moved.
    assert [row["articles"] for row in rows] == ["11", "4", "6"]
    assert rows[0]["measured_hhem"] == "0.36"
    assert rows[0]["detail"] == "rerun"


def test_a_day_directory_with_no_readable_file_stops_the_read(tmp_path: Path) -> None:
    """An empty day is not a quiet day, and the walk says so rather than yielding."""
    (tmp_path / "2026" / "09" / "18").mkdir(parents=True)
    with pytest.raises(ValueError, match="2026/09/18"):
        list(day_shards.shard_files(tmp_path, days=UNBOUNDED_WINDOW))


def test_a_stray_inside_a_day_tree_stops_the_read(tmp_path: Path) -> None:
    """Nothing inside a day tree is skipped, whichever level the stray sits at."""
    (tmp_path / "2026" / "09").mkdir(parents=True)
    (tmp_path / "2026" / "09" / "notes.txt").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match=r"notes\.txt"):
        list(day_shards.shard_files(tmp_path, days=UNBOUNDED_WINDOW))


def test_a_name_inside_a_day_directory_that_is_not_a_writers_stops_the_read(
    tmp_path: Path,
) -> None:
    """An unknown name inside a day directory is refused rather than skipped."""
    day = tmp_path / "2026" / "09" / "18"
    day.mkdir(parents=True)
    shutil.copy(
        _root() / "2026" / "09" / "18" / "2026-09-18-1-1-work-01.csv",
        day / "nobody-declared-this.csv",
    )
    with pytest.raises(ValueError, match="is not a writer's name"):
        day_shards.settled_rows(tmp_path, ledger.VALIDATION_KEY, ValidationRow, days=1)


def test_a_row_the_contract_cannot_read_stops_the_read(tmp_path: Path) -> None:
    """The one ledger read that does not degrade, asked from the side that loses rows.

    Each file is written whole by one writer from the contract's own columns, so
    a row that will not read means the writer and this reader disagree about the
    shape. Skipping it would lose a column quietly, and quietly is the part that
    costs: the count taken off the day would still look like an answer.
    """
    day = tmp_path / "2026" / "09" / "18"
    day.mkdir(parents=True)
    shard = day / "2026-09-18-1-1-work-01.csv"
    shutil.copy(_root() / "2026" / "09" / "18" / "2026-09-18-1-1-work-01.csv", shard)
    with shard.open("a", encoding="utf-8", newline="") as handle:
        handle.write("1999-01-01,not-a-date,,,,,,\n")

    with pytest.raises(ValueError, match="does not read as a ValidationRow"):
        day_shards.settled_rows(tmp_path, ledger.VALIDATION_KEY, ValidationRow, days=1)


#: Every reader of a writer-owned CSV day tree: the module, the day-file call it
#: would make if it went back to the one-file-a-day walk, and the `day_shards`
#: call it makes instead. A module keeps its other day-file walks - the judge
#: trees and the council's outcomes still file one file a day - so the
#: claim is about the named call and never about the file.
#:
#: The entry point differs by what the reader wants. `shard_files` hands back
#: every file, which is what a census needs. `settled_rows`, `settled_day` and
#: `one_day` settle a day's shards into one answer first, which is what a
#: published number needs.
#:
#: The item census, the eval rows, the machine rows, the counterfactual scores
#: and the feed verdicts are not here: they moved under `state/raw/` through the
#: ledger door, and their readers call `ledger.load_days`, which walks no day
#: tree of this kind. The two migration utilities are not here either, because
#: reading an older shape is their job.
#:
#: The cleanup passes left `retention.py` for the gardener's tasks, so their walk
#: is named where it runs now, each with the day-file call it would be if it
#: went back. The gardener's closed-day fold walked the shards too, and it is
#: gone with the CSV day trees it settled.
#:
#: Written out rather than discovered. A discovered list passes on a module
#: nobody checked, and it would grow with the repository (Guardrail #12).
MOVED: Final = (
    ("backend/idhazh/gardener/retention_files.py", "day_files(tree)", "shards_by_month("),
)

#: A ledger that keeps the day-file walk, and the reader that walks it: the judge's
#: fitted line, walked by the post-merge settlement. `day_partition.day_files`
#: refusing a directory is the tripwire that catches a twelfth tree arriving
#: without a plan. `state/visual-prunes/` and `state/published/` were walked this
#: way until each moved under `state/raw/`.
#:
#: The reader is called rather than read, so what is checked is that the refusal
#: still reaches a caller - a walk swapped for one that skips what it cannot
#: place fails here even when the call still spells `day_files`.
KEPT: Final = (
    (
        LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS,
        lambda state_dir: ledger.keyed_paths(state_dir, date=None),
    ),
)


def _squeezed(relpath: str) -> str:
    """One module's source with every run of whitespace collapsed to one space.

    So a line break the formatter moves cannot make this test pass or fail.
    """
    source = (Path(__file__).resolve().parents[3] / relpath).read_text(encoding="utf-8")
    return " ".join(source.split())


@pytest.mark.parametrize(("relpath", "was", "reaches"), MOVED)
def test_every_named_reader_walks_the_shards_and_not_the_day_files(
    relpath: str, was: str, reaches: str
) -> None:
    """The enumeration parity cannot settle: each named call moved.

    The call is matched unqualified, because a module may import the entry point
    by name or reach it through `day_shards`, and both are the same read.
    """
    source = _squeezed(relpath)
    assert reaches in source, f"{relpath} does not reach day_shards.{reaches[:-1]} at all"
    assert was not in source, (
        f"{relpath} still walks day files at `{was}`. A ledger sharded by run identity "
        f"is read through day_shards.{reaches[:-1]}, which reads a day directory too."
    )


@pytest.mark.parametrize(("which", "read"), KEPT, ids=[which.value for which, _ in KEPT])
def test_a_ledger_that_keeps_the_day_file_walk_still_refuses_a_day_directory(
    which: LedgerName, read: Callable[[Path], object], tmp_path: Path
) -> None:
    """The tripwire is only a tripwire while something still trips it.

    A day directory is what a tree that gained writer-owned files looks like from
    a reader that was never told. This reader must stop rather than return a
    short answer, because a report that quietly drops a day is a report of the
    wrong series.

    The tree is built from the registry, so this cannot drift from where the
    ledger actually lives, and it holds one directory whatever `state/` grows to
    (Guardrail #12).
    """
    state_dir = tmp_path / "state"
    root = ledger.tree_root(state_dir, which)
    (root / "2026" / "09" / "18").mkdir(parents=True)

    with pytest.raises(ValueError, match=f"{root.parent.name}/{root.name} holds 2026/09/18"):
        read(state_dir)
