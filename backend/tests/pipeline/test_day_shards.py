"""A day directory of writer-owned files reads back as the rows a head holds.

Two claims, and they answer different questions.

**Parity.** `day_shards.settled_rows` over a day directory returns exactly what
`stages.compact` writes into a head for the same bytes. The fixture files are
the same files in both runs, so a difference is a difference in the fold rather
than in the input. That is the whole of what moving the settlement out of the
writer is allowed to change: nothing.

**The move.** Parity cannot say whether every production reader was moved onto
the walker that reads both shapes, so the second half of this module reads the
modules decision 5.2 of the no-file-has-two-writers plan enumerates and checks
each one by name. The list is fixed and written out here, so this test costs the
same however much the repository grows (`CLAUDE.md` section 13).

Nothing writes a day directory yet, so every reader below answers today exactly
as it answered before.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_shards, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.stages import compact

pytestmark = pytest.mark.contract

#: The committed tree holding one ledger root in both shapes at once. A fixture
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
    root = FIXTURE / "both-shapes" / "span-rollup"
    assert root.is_dir(), f"the day-shards fixture is missing at {root}"
    return root


def _rows_of(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_a_day_directory_settles_to_what_the_fold_writes_into_its_settled_file(
    tmp_path: Path,
) -> None:
    """The oracle. Same bytes, two settlements, one answer, row for row."""
    root = _root()

    day = tmp_path / ledger.STATE_DIRNAME / ledger.SPAN_ROLLUP_DIRNAME / "2026" / "09" / "18"
    day.mkdir(parents=True)
    for name in WRITERS:
        shutil.copy(root / "2026" / "09" / "18" / name, day / name)
    report = compact.stage_compact(
        tmp_path / ledger.STATE_DIRNAME, date="2026-09-30", after_days=7
    )
    assert report.files_replaced == len(WRITERS)
    folded = _rows_of(day / day_shards.SETTLED_NAME)

    # `days=1` is the newest recorded day, which is the day directory alone -
    # the same rows the three writer files above carried.
    settled = day_shards.settled_rows(root, ledger.SPAN_ROLLUP_KEY, SpanRollupRow, days=1)

    assert settled == folded
    assert [(row["shard"], row["span_name"]) for row in settled] == [
        ("0", "item"),
        ("0", "robots"),
        ("1", "item"),
    ]
    # The supersede case: attempt 2 corrected the figures attempt 1 wrote.
    assert settled[0]["count"] == "14"
    assert settled[0]["total_ms"] == "5000"


def test_the_walk_reads_a_day_file_and_a_day_directory_as_one_ledger() -> None:
    """Both shapes, one root, and a day is a day whichever shape it is in."""
    root = _root()

    every = list(day_shards.shard_files(root, days=UNBOUNDED_WINDOW))
    assert [path.name for path in every] == ["17.csv", *WRITERS]
    assert [day_shards.date_of(path) for path in every] == [
        "2026-09-17",
        "2026-09-18",
        "2026-09-18",
        "2026-09-18",
    ]

    # The cover counts recorded days, never files: the newest day is three files
    # and it is still one day.
    assert [path.name for path in day_shards.shard_files(root, days=1)] == list(WRITERS)
    assert [path.name for path in day_shards.shard_files(root, days=2)] == [
        "17.csv",
        *WRITERS,
    ]

    assert len(day_shards.settled_rows(root, ledger.SPAN_ROLLUP_KEY, SpanRollupRow, days=2)) == 5
    assert list(day_shards.shard_files(root.parent / "never-written", days=1)) == []


def test_settled_sorts_below_every_writer_file(tmp_path: Path) -> None:
    """A closed day's fold reads first, and a straggler beside it reads after."""
    day = tmp_path / "2026" / "09" / "18"
    day.mkdir(parents=True)
    columns = SpanRollupRow.csv_columns()
    settled = [
        {**dict.fromkeys(columns, ""), "version": "2026-09-06", "date": "2026-09-18"}
        | {"run_id": "2026-09-18-1", "shard": "0", "span_name": "item"}
        | {"count": "12", "total_ms": "4200"}
    ]
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
    rows = day_shards.settled_rows(tmp_path, ledger.SPAN_ROLLUP_KEY, SpanRollupRow, days=1)
    assert [row["count"] for row in rows] == ["14", "12"]


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
        day_shards.settled_rows(tmp_path, ledger.SPAN_ROLLUP_KEY, SpanRollupRow, days=1)


#: Every reader that left the day-file walk: the module, the exact call it used
#: to make, and the `day_shards` call it makes instead. A module keeps its other
#: day-file walks - `state/seen/`, `state/counterfactual-scores/` and the judge
#: trees are not moving - so the claim is about the named call and never about
#: the file.
#:
#: The entry point differs by what the reader wants. `shard_files` hands back
#: every file, which is what a prune and a census need. `settled_rows`,
#: `settled_day` and `one_day` settle a day's shards into one answer first,
#: which is what a published number needs.
#:
#: `ledger.py` keeps the item-health reader and lost the host-fingerprint one:
#: `load_item_health` settles the window itself, while the host records are read
#: by the two panels that show them.
#:
#: Written out rather than discovered. A discovered list passes on a module
#: nobody checked, and it would grow with the repository (Guardrail #12).
MOVED: Final = (
    (
        "backend/idhazh/ledger.py",
        "day_files(state_dir / ITEM_HEALTH_DIRNAME)",
        "settled_rows(",
    ),
    (
        "backend/idhazh/telemetry/publish/console_band.py",
        "day_files(state_dir / HOST_FINGERPRINT_DIRNAME)",
        "one_day(",
    ),
    (
        "backend/idhazh/telemetry/publish/machine.py",
        "day_files(state_dir / HOST_FINGERPRINT_DIRNAME)",
        "dates_by_month(",
    ),
    ("backend/idhazh/retention.py", "day_files(ledger_root)", "shard_files("),
    ("backend/idhazh/evals/writer.py", "day_files(state_dir / LEDGER_DIRNAME)", "shard_files("),
    ("backend/idhazh/evals/writer.py", "day_files(state_dir / INDEX_DIRNAME)", "shard_files("),
    ("backend/idhazh/telemetry/prune.py", "day_files(state_root / store)", "shard_files("),
    ("backend/utilities/measure_ledgers.py", "day_files(directory)", "shard_files("),
    (
        "backend/utilities/item_health_provenance.py",
        "day_files(root / LEDGER_ROOT)",
        "shard_files(",
    ),
    ("backend/utilities/server_memory_mark.py", "day_files(root / LEDGER_ROOT)", "shard_files("),
    ("backend/utilities/empty_column_census.py", "day_files(root / store.root)", "shard_files("),
)

#: The two stores that keep the day-file walk. `state/published/` and
#: `state/visual-prunes/` are not moving, and `day_partition.day_files` refusing
#: a directory is the tripwire that catches a twelfth tree arriving without a
#: plan.
KEPT: Final = (
    "day_partition.day_files(state_dir / PUBLISHED_DIRNAME)",
    "day_partition.day_files(state_dir / VISUAL_PRUNES_DIRNAME)",
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
        f"{relpath} still walks day files at `{was}`. A store sharded by run identity "
        f"is read through day_shards.{reaches[:-1]}, which reads a day directory too."
    )


def test_the_two_stores_that_keep_the_day_file_walk_still_have_it() -> None:
    """The tripwire is only a tripwire while something still trips it."""
    source = _squeezed("backend/idhazh/ledger.py")
    for kept in KEPT:
        assert kept in source, (
            f"`{kept}` is gone, so nothing refuses a day directory under a store that never "
            "planned to hold one."
        )
