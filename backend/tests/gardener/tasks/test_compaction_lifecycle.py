"""Does the real compaction, wake by wake, leave the right entries for each stage of a ledger's life?

A ledger starts, pauses, resumes and stops, and so does the task that packs it.
Each test here builds its own declaration and files its own raw rows under
`tmp_path`, then wakes the shipped compaction on the UTC days it names, the way
a scheduled wake runs it: the listing names only the ledger's three indexes,
and each step names what it reads. A task that is paused is one the runner does
not wake, so a stall is a run of days with no wake. Each test checks what the
wakes leave on disk - every entry of the three indexes, and the files the
packed entries name - against values written out here, so no committed knob
can move what a test expects. The task's record is not read.

What the indexes record at each stage, and what a reader answers, is
`docs/architecture/contracts/ledger-lifecycle.md`.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import (
    CompactionPolicy,
    ForeverWindow,
    TaskKind,
    TaskLifecycleStatus,
)
from idhazh.contracts.ledger_index import CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow

from ._task import run_declared

pytestmark = pytest.mark.contract

LEDGER: Final = LedgerName.VISUAL_PRUNES
TASK: Final = f"compact-{LEDGER.value}"
#: The first UTC year a ledger can hold. Only a pass that rebuilds an absent index reads it.
FIRST_YEAR: Final = "2026"

#: One index entry as these tests read it: what it covers, its state, its rows and its lost days.
type Entry = tuple[str, EntryState, int, tuple[str, ...]]


def state(root: Path) -> Path:
    return root / ledger.STATE_DIRNAME


def declared(
    root: Path,
    *,
    compact_after_days: int,
    daily_keep_days: int,
    max_periods_per_run: int,
    monthly_keep_days: int | None = None,
) -> CompactionPolicy:
    """A live compaction of the ledger that keeps every month, with the knobs a test names."""
    return CompactionPolicy(
        kind=TaskKind.COMPACTION,
        lifecycle_status=TaskLifecycleStatus.ACTIVE,
        window=ForeverWindow(unit="forever"),
        dry_run=False,
        max_deletes_per_run=None,
        owns=[
            ledger.raw_root(state(root), LEDGER).relative_to(root).as_posix(),
            ledger.compact_folder(state(root), LEDGER).relative_to(root).as_posix(),
        ],
        ledger=LEDGER,
        daily_keep_days=daily_keep_days,
        monthly_window=ForeverWindow(unit="forever"),
        month_deletes_dry_run=False,
        monthly_keep_days=monthly_keep_days,
        max_periods_per_run=max_periods_per_run,
        max_raw_files_per_period=10,
        compact_after_days=compact_after_days,
        prune_refusal=None,
    )


def filed(root: Path, on: str, *, runs: int = 1) -> None:
    """`runs` runs of the writer each file one row for `on`, each its own raw file."""
    for run in range(1, runs + 1):
        row = VisualPruneRow(
            version=VisualPruneRow.schema_version(),
            date=on,
            run_id=f"{on}-{run}",
            policy_months=-1,
            max_deletes_per_run=200,
            dry_run=True,
            candidates_found=0,
            deleted=0,
            skipped_by_fuse=0,
            fuse_tripped=False,
            bytes_reclaimed=0,
            oldest_kept=None,
            payload_bytes_before=1000,
            payload_bytes_after=1000,
        )
        ledger.persist(
            state(root),
            [row],
            ledger=LEDGER,
            covers=on,
            identity=WriterIdentity(
                run_id=row.run_id,
                attempt=1,
                job=ServerJob.RUN_TASKS,
                shard=0,
                producer="gardener.tasks.visual_prune",
                git_sha="a" * 40,
            ),
        )


def wake(root: Path, task: CompactionPolicy, on: date) -> None:
    """One scheduled wake of the compaction on the UTC day `on`."""
    run_declared(TASK, task, root, today=on, first_year=FIRST_YEAR)


def named(root: Path, period: Period) -> list[Entry]:
    """Every entry of one of the ledger's indexes, oldest first."""
    index = CompactIndex.read(ledger.compact_index_path(state(root), LEDGER, period))
    return [
        (entry.covers, entry.state, entry.rows, tuple(entry.lost_days)) for entry in index.entries
    ]


def packed(covers: str, rows: int) -> Entry:
    return (covers, EntryState.PACKED, rows, ())


def empty(covers: str) -> Entry:
    return (covers, EntryState.EMPTY, 0, ())


def days(first: str, last: str) -> list[str]:
    """Every UTC day from `first` to `last`, both included."""
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


def quiet(first: str, last: str) -> list[Entry]:
    """An `empty` daily entry for every UTC day from `first` to `last`."""
    return [empty(day) for day in days(first, last)]


def newest_day(root: Path) -> str:
    """The newest day the daily index names: where the next wake's day step starts after."""
    return named(root, Period.DAILY)[-1][0]


def unmatched_files(root: Path) -> list[str]:
    """Each way the ledger's packed files and its entries disagree, one line each; none when they agree.

    A packed entry names a file of the size it records, no other entry names
    one, and no other data file is in the compact folder. That folder is one
    the test built, so walking it is bounded.
    """
    folder = ledger.compact_folder(state(root), LEDGER)
    indexes = ledger.compact_index_path(state(root), LEDGER, Period.DAILY).parent
    disagreements: list[str] = []
    named_files: set[Path] = set()
    for period in Period:
        index = CompactIndex.read(ledger.compact_index_path(state(root), LEDGER, period))
        for entry in index.entries:
            found = ledger.compact_file(state(root), LEDGER, period, entry.covers)
            where = f"{period.value} {entry.covers} ({entry.state.value})"
            if entry.state is not EntryState.PACKED:
                if found is not None:
                    disagreements.append(f"{where} has a file")
            elif found is None:
                disagreements.append(f"{where} has no file")
            else:
                named_files.add(found)
                if found.stat().st_size != entry.bytes:
                    disagreements.append(f"{where} records {entry.bytes} bytes")
    held = {path for path in folder.rglob("*") if path.is_file() and path.parent != indexes}
    disagreements.extend(
        f"{path.relative_to(folder).as_posix()} is named by no entry"
        for path in sorted(held - named_files)
    )
    return disagreements


def test_a_ledger_whose_writer_never_filed_a_row_gets_no_compact_folder_at_any_wake(
    tmp_path: Path,
) -> None:
    """A pass that finds no raw day writes nothing: no index, and no compact folder.

    The wakes cross a month's end, the day the month would close, and a
    year's end. The ledger stays declared and never packed, so the site has
    nothing to stage for it and a reader answers that it is not packed yet.
    """
    root = tmp_path / "checkout"
    state(root).mkdir(parents=True)
    task = declared(root, compact_after_days=1, daily_keep_days=31, max_periods_per_run=8)

    for on in (date(2026, 8, 14), date(2026, 9, 1), date(2026, 10, 2), date(2027, 1, 1)):
        wake(root, task, on)

        assert not ledger.compact_folder(state(root), LEDGER).exists(), on
        assert [path for path in root.rglob("*") if path.is_file()] == [], on


def test_a_ledger_that_begins_mid_month_starts_its_days_on_its_first_raw_day_and_loses_none_before(
    tmp_path: Path,
) -> None:
    """The first daily entry is the first raw day; the month and the year cover from their 1st.

    The writer files its first row on 12 August 2026. The first wake names that
    day first, never 1 August. Once August closes, its entry covers the month
    and lists no day before the 12th as lost; once 2026 packs, its entry covers
    the year and lists no day of January to July as lost. A month closes at the
    first wake after its last day is packed, once `daily_keep_days`, 31, have
    passed since it ended: August on 3 October 2026. The year packs at the wake
    after January 2027 closes, on 7 March 2027.
    """
    root = tmp_path / "checkout"
    task = declared(
        root,
        compact_after_days=1,
        daily_keep_days=31,
        max_periods_per_run=100,
        monthly_keep_days=63,
    )

    filed(root, "2026-08-12")
    wake(root, task, date(2026, 8, 14))

    assert named(root, Period.DAILY) == [packed("2026-08-12", 1)]
    assert named(root, Period.MONTHLY) == []
    assert named(root, Period.YEARLY) == []
    assert ledger.raw_days(state(root), LEDGER) == []
    assert unmatched_files(root) == []

    filed(root, "2026-08-20", runs=2)
    wake(root, task, date(2026, 10, 2))

    assert named(root, Period.DAILY) == [
        packed("2026-08-12", 1),
        *quiet("2026-08-13", "2026-08-19"),
        packed("2026-08-20", 2),
        *quiet("2026-08-21", "2026-09-30"),
    ]
    assert named(root, Period.MONTHLY) == []

    wake(root, task, date(2026, 10, 3))

    assert named(root, Period.MONTHLY) == [packed("2026-08", 3)]
    assert named(root, Period.DAILY) == quiet("2026-09-01", "2026-10-01")
    assert unmatched_files(root) == []

    filed(root, "2026-12-30")
    for on in (date(2027, 3, 4), date(2027, 3, 5), date(2027, 3, 6)):
        wake(root, task, on)

    assert named(root, Period.YEARLY) == []
    assert named(root, Period.MONTHLY) == [
        packed("2026-08", 3),
        empty("2026-09"),
        empty("2026-10"),
        empty("2026-11"),
        packed("2026-12", 1),
        empty("2027-01"),
    ]

    wake(root, task, date(2027, 3, 7))

    assert named(root, Period.YEARLY) == [packed("2026", 4)]
    assert named(root, Period.MONTHLY) == [empty("2027-01")]
    assert named(root, Period.DAILY) == quiet("2027-02-01", "2027-03-05")
    assert unmatched_files(root) == []


def test_a_writer_paused_then_resumed_leaves_one_empty_entry_for_each_day_it_filed_nothing(
    tmp_path: Path,
) -> None:
    """The daily index keeps moving while the writer is paused, one `empty` entry a day.

    The writer files on 1 to 3 September 2026, files nothing from the 4th to
    the 8th, and files again on the 9th and 10th. The compaction wakes every
    day and packs through the day two before it, so each wake moves the newest
    entry on by one day, paused or not, and a quiet day has no file.
    """
    root = tmp_path / "checkout"
    task = declared(root, compact_after_days=1, daily_keep_days=31, max_periods_per_run=8)
    writes = {"2026-09-01", "2026-09-02", "2026-09-03", "2026-09-09", "2026-09-10"}
    newest_after = {
        "2026-09-03": "2026-09-01",
        "2026-09-04": "2026-09-02",
        "2026-09-05": "2026-09-03",
        "2026-09-06": "2026-09-04",
        "2026-09-07": "2026-09-05",
        "2026-09-08": "2026-09-06",
        "2026-09-09": "2026-09-07",
        "2026-09-10": "2026-09-08",
        "2026-09-11": "2026-09-09",
        "2026-09-12": "2026-09-10",
    }

    for on in days("2026-09-01", "2026-09-12"):
        if on in writes:
            filed(root, on)
        if on in newest_after:
            wake(root, task, date.fromisoformat(on))
            assert newest_day(root) == newest_after[on], on

    assert named(root, Period.DAILY) == [
        packed("2026-09-01", 1),
        packed("2026-09-02", 1),
        packed("2026-09-03", 1),
        *quiet("2026-09-04", "2026-09-08"),
        packed("2026-09-09", 1),
        packed("2026-09-10", 1),
    ]
    assert ledger.raw_days(state(root), LEDGER) == []
    assert unmatched_files(root) == []


def test_a_writer_that_stops_leaves_empty_days_to_the_newest_due_day_and_its_quiet_month_closes_empty(
    tmp_path: Path,
) -> None:
    """The month that holds the last rows closes `packed`, and the quiet month after it `empty`.

    The writer files on 3, 4 and 5 August 2026 and never again. Every later due
    day gets an `empty` entry, so the daily mark reaches each month's last day
    and the month closes `daily_keep_days` after it ends: August on 2 October
    with its four rows, September on 1 November with none and no file.
    """
    root = tmp_path / "checkout"
    task = declared(root, compact_after_days=1, daily_keep_days=31, max_periods_per_run=40)
    filed(root, "2026-08-03")
    filed(root, "2026-08-04", runs=2)
    filed(root, "2026-08-05")

    wake(root, task, date(2026, 8, 7))

    assert named(root, Period.DAILY) == [
        packed("2026-08-03", 1),
        packed("2026-08-04", 2),
        packed("2026-08-05", 1),
    ]

    wake(root, task, date(2026, 9, 10))

    assert named(root, Period.DAILY)[3:] == quiet("2026-08-06", "2026-09-08")
    assert named(root, Period.MONTHLY) == []

    wake(root, task, date(2026, 10, 2))

    assert named(root, Period.MONTHLY) == [packed("2026-08", 4)]
    assert named(root, Period.DAILY) == quiet("2026-09-01", "2026-09-30")
    assert unmatched_files(root) == []

    wake(root, task, date(2026, 11, 1))

    assert named(root, Period.MONTHLY) == [packed("2026-08", 4), empty("2026-09")]
    assert named(root, Period.DAILY) == quiet("2026-10-01", "2026-10-30")
    assert named(root, Period.YEARLY) == []
    assert unmatched_files(root) == []


def test_packing_resumed_after_a_stall_moves_at_most_max_periods_per_run_days_a_wake(
    tmp_path: Path,
) -> None:
    """The newest entry stays where the stall left it, then catches up a capped run of days a wake.

    The writer files one row every day from 1 to 20 September 2026. The
    compaction wakes on the 3rd and 4th, then not from the 5th to the 14th.
    From the 15th it wakes every day again and takes at most
    `max_periods_per_run`, 3, of the due days a wake, oldest first, until it
    reaches the newest due day; no day is skipped or lost on the way.
    """
    root = tmp_path / "checkout"
    task = declared(root, compact_after_days=1, daily_keep_days=31, max_periods_per_run=3)
    newest_after = {
        "2026-09-03": "2026-09-01",
        "2026-09-04": "2026-09-02",
        "2026-09-15": "2026-09-05",
        "2026-09-16": "2026-09-08",
        "2026-09-17": "2026-09-11",
        "2026-09-18": "2026-09-14",
        "2026-09-19": "2026-09-17",
        "2026-09-20": "2026-09-18",
    }

    for on in days("2026-09-01", "2026-09-20"):
        filed(root, on)
        if on in newest_after:
            wake(root, task, date.fromisoformat(on))
            assert newest_day(root) == newest_after[on], on

    assert named(root, Period.DAILY) == [packed(day, 1) for day in days("2026-09-01", "2026-09-18")]
    assert ledger.raw_days(state(root), LEDGER) == ["2026-09-19", "2026-09-20"]
    assert unmatched_files(root) == []
