"""A day directory of writer-owned files reads back as one row per record.

Two claims, and they answer different questions.

**Parity.** `day_shards.settled_rows` over a day directory returns exactly what
the gardener's closed-day fold writes into that day's `settled.csv` for the same
bytes. The fixture files are the same files in both runs, so a difference is a
difference in the fold rather than in the input. That is the whole of what
moving the settlement out of the writer is allowed to change: nothing.

**The readers.** Parity cannot say whether every production reader of a
writer-owned tree reads it through the walker, so the second half of this module
names each one and checks it by name. The list is fixed and written out here, so
this test costs the same however much the repository grows (`CLAUDE.md` section
13).

A day is a directory, so a `<DD>.csv` beside one is a name no writer spells
and the walk refuses it with every other stray. The one file a month folder may
hold is a closed month's own `settled.csv`, which reads back as the days it
replaced.
"""

from __future__ import annotations

import csv
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.gardener import DEFAULT_CLOSED_AFTER_DAYS
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.validation_row import ValidationRow
from idhazh.gardener import closed_day_fold

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


def _feed_row(day: str, number: int) -> FeedHealthRow:
    return FeedHealthRow.model_validate({
        "date": day,
        "run_id": f"{day}-1",
        "feed_id": f"feed-{number}",
        "checked_at": f"{day}T06:00:00Z",
        "outcome": FetchOutcome.OK,
        "status": 200,
        "items": 3,
    })


def test_a_day_directory_settles_to_what_the_fold_writes_into_its_settled_file(
    tmp_path: Path,
) -> None:
    """The oracle. Same bytes, two settlements, one answer, row for row."""
    state = tmp_path / ledger.STATE_DIRNAME
    feeds = [_feed_row("2026-09-18", number) for number in range(3)]
    for attempt, shard, rows in (
        (1, 0, feeds[:2]),
        (1, 1, feeds[2:]),
        (2, 0, feeds[:1]),
    ):
        ledger.write_segment(
            state,
            TREE,
            rows,
            run_id="2026-09-18-1",
            attempt=attempt,
            job=ServerJob.WORK,
            shard=shard,
            date="2026-09-18",
        )
    root = ledger.tree_root(state, TREE)
    day = ledger.path(state, TREE, "2026-09-18")
    assert sorted(path.name for path in day.iterdir()) == list(WRITERS)
    assert sum(len(_rows_of(path)) for path in day.iterdir()) == 4
    settled = day_shards.settled_rows(
        root, ledger.segment_key(TREE), FeedHealthRow, days=1
    )
    assert [row["feed_id"] for row in settled] == [feed.feed_id for feed in feeds]

    folded = closed_day_fold.fold(
        state,
        [TREE],
        now=datetime(2026, 9, 30, tzinfo=UTC),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=False,
        period_paths=[ledger.tree_root(state, TREE)],
    )
    assert folded.files == len(WRITERS)
    folded_rows = _rows_of(day / day_shards.SETTLED_NAME)

    assert settled == folded_rows
    assert day_shards.settled_rows(
        root, ledger.segment_key(TREE), FeedHealthRow, days=1
    ) == settled


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


TREE: Final = LedgerName.FEED_HEALTH


def _a_month_settled_whole(tmp_path: Path) -> tuple[Path, list[dict[str, str]]]:
    """Two real feed-health days settled as a month, with their original reader answer."""
    state = tmp_path / ledger.STATE_DIRNAME
    root = ledger.tree_root(state, TREE)
    for number, day in enumerate(("2026-08-03", "2026-08-17")):
        ledger.write_segment(
            state,
            TREE,
            [_feed_row(day, number)],
            run_id=f"{day}-1",
            attempt=1,
            job=ServerJob.WORK,
            shard=0,
            date=day,
        )
    before = day_shards.settled_rows(
        root, ledger.segment_key(TREE), FeedHealthRow, days=UNBOUNDED_WINDOW
    )
    folded = closed_day_fold.fold(
        state,
        [TREE],
        now=datetime(2026, 10, 1, tzinfo=UTC),
        after_days=DEFAULT_CLOSED_AFTER_DAYS,
        dry_run=False,
        settles_months=True,
        period_paths=[root],
    )
    assert [each.month for each in folded.months] == ["2026-08"]
    return root, before


def test_a_month_settled_whole_reads_back_as_the_days_it_replaced(tmp_path: Path) -> None:
    """Every reader that walks the tree gets the same rows, in the same order, after the fold.

    The month's file is a member of the walk, stamped with its month, after every
    earlier month and before every later one. It reads at attempt 0 and holds
    the settled answer of every file it replaced, which is the answer those
    files gave.
    """
    key, model = ledger.segment_key(TREE), ledger.segment_contract(TREE)
    root, before = _a_month_settled_whole(tmp_path)

    month_file = root / "2026" / "08" / day_shards.SETTLED_NAME
    assert month_file in list(day_shards.shard_files(root, days=UNBOUNDED_WINDOW))
    assert day_shards.is_month_file(month_file)
    assert day_shards.date_of(month_file) == "2026-08"
    assert not day_shards.is_month_file(root / "2026" / "09" / "29" / day_shards.SETTLED_NAME)
    assert day_shards.settled_rows(root, key, model, days=UNBOUNDED_WINDOW) == before


def test_a_reader_that_settles_day_by_day_is_refused_a_month_settled_whole(
    tmp_path: Path,
) -> None:
    """A month file is not a day directory, so a day-directory reader must refuse it."""
    root, _ = _a_month_settled_whole(tmp_path)

    with pytest.raises(ValueError, match=r"2026/08/settled\.csv"):
        day_shards.dates_by_month(root, days=UNBOUNDED_WINDOW)


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
#: every file, which is what a prune and a census need. `settled_rows`,
#: `settled_day` and `one_day` settle a day's shards into one answer first,
#: which is what a published number needs.
#:
#: The item census, the eval rows, the machine rows and the counterfactual
#: scores are not here: they moved under `state/raw/` through the ledger door,
#: and their readers call `ledger.load_days`, which walks no day tree of this
#: kind. The two migration utilities are not here either, because reading an
#: older shape is their job.
#:
#: The cleanup passes left `retention.py` for the gardener's tasks, so their walk
#: is named where it runs now, each with the day-file call it would be if it
#: went back.
#:
#: Written out rather than discovered. A discovered list passes on a module
#: nobody checked, and it would grow with the repository (Guardrail #12).
MOVED: Final = (
    (
        "backend/idhazh/ledger/rows.py",
        "day_files(paths.tree_root(state_dir, LedgerName.FEED_HEALTH))",
        "settled_rows(",
    ),
    ("backend/idhazh/gardener/closed_day_fold.py", "day_files(root)", "shard_files("),
    ("backend/idhazh/gardener/retention_files.py", "day_files(tree)", "shards_by_month("),
    ("backend/idhazh/telemetry/prune.py", "day_files(state_root / ledger)", "shard_files("),
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
