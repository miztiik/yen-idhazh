"""Does year packing keep every row, pack each finished year once, and leave other ledgers alone?

These run the shipped `compact-visual-prunes` task, found the way the runner
finds it, live over trees built under `tmp_path` through the ledger door: the
twelve month files of 2026, the January of 2027 that lets 2026 be packed, and
the indexes a compaction leaves beside them. The declaration
ships `dry_run: true` and packs no year, and each test turns on what it needs
for itself only. Each oracle is named where it is checked: a scheduled wake
packs a year on the day its wait ends and not the day before, naming the months
it reads itself; every row the month files held reads back from the year file,
one row group a month; a month with no row adds none, and every month's lost
days carry into its year; a year with no row is an entry with no file; a year
file no entry names is adopted before any month is read; a month no entry
names is adopted from its own file, or its days are recorded lost when nothing
of it is left; a month file that is gone or cannot be read costs its year that
month's days, the second moved under set-aside and counted; a second
pass changes nothing; a pass cut part way loses and doubles no row, and the
next finishes it when the cut came before the indexes; and a ledger that does
not pack years keeps its month files byte for byte.

Nothing here reads the committed `state/` or a clock the test did not set
(CLAUDE.md sections 2 and 13).
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Final

import pyarrow.parquet
import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener import schedule
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.tasks import _compaction_periods, _yearly_period
from idhazh.gardener.tasks._compact_tree import CompactTree
from idhazh.ledger import StoredRow

from ._marks import marks_on_disk
from ._task import context_for, run_task
from .test_compaction import recovered

pytestmark = pytest.mark.contract

VISUALS: Final = LedgerName.VISUAL_PRUNES
TASK: Final = "compact-visual-prunes"
MONTHS_OF_2026: Final = [f"2026-{number:02d}" for number in range(1, 13)]

#: The first wake that packs 2026 at the smallest wait the declaration allows:
#: 77 days is `daily_keep_days` 45 plus 32, and 2027-03-20 is 78 days after 2026 ended.
TODAY: Final = date(2027, 3, 20)
PACKS: Final[dict[str, Any]] = {"monthly_window": {"unit": "forever"}, "monthly_keep_days": 77}

#: The smallest waits the declaration contract allows: a month closes 31 days
#: after it ends, and a year 63 days after, `daily_keep_days` plus 32.
SMALLEST: Final[dict[str, Any]] = {
    "daily_keep_days": 31,
    "monthly_window": {"unit": "forever"},
    "monthly_keep_days": 63,
}

#: 2026 ends at 00:00 UTC on 1 January 2027, and 63 days later is 5 March.
READY: Final = date(2027, 3, 5)

#: The compaction's own identity, which every compact file's envelope names.
COMPACTION: Final = WriterIdentity(
    run_id="2027-02-15-1",
    attempt=1,
    job=ServerJob.RUN_TASKS,
    shard=0,
    producer="gardener.tasks.compaction",
    git_sha="c" * 40,
)


def a_pass(on: str) -> VisualPruneRow:
    """One reporting cleanup pass on one day, told from every other day's by what it weighed."""
    weighed = int(on.replace("-", ""))
    return VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=on,
        run_id=f"{on}-1",
        policy_months=-1,
        max_deletes_per_run=200,
        dry_run=True,
        candidates_found=0,
        deleted=0,
        skipped_by_fuse=0,
        fuse_tripped=False,
        bytes_reclaimed=0,
        oldest_kept=None,
        payload_bytes_before=weighed,
        payload_bytes_after=weighed,
    )


def state(root: Path) -> Path:
    return root / ledger.STATE_DIRNAME


def a_month_file(root: Path, scratch: Path, month: str) -> None:
    """One month already absorbed: two passes, filed raw on its 5th and its 20th, in one file."""
    raws = [
        ledger.persist(
            scratch,
            [a_pass(f"{month}-{day}")],
            ledger=VISUALS,
            covers=f"{month}-{day}",
            identity=WriterIdentity(
                run_id=f"{month}-{day}-1",
                attempt=1,
                job=ServerJob.RUN_TASKS,
                shard=0,
                producer="gardener.tasks.visual_prune",
                git_sha="a" * 40,
            ),
        )[0]
        for day in ("05", "20")
    ]
    ledger.persist_period(
        state(root),
        ledger.load_stored(raws, model=VisualPruneRow),
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.MONTHLY,
        covers=month,
        identity=COMPACTION,
        built_from=len(raws),
    )


def index_entries(root: Path, period: Period, entries: list[CompactEntry]) -> None:
    """One period's index, as a compaction writes it."""
    path = ledger.compact_index_path(state(root), VISUALS, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    index = CompactIndex(
        version=CompactIndex.schema_version(), ledger=VISUALS, period=period, entries=entries
    )
    path.write_bytes(index.to_json().encode("ascii"))


def a_finished_year(
    tmp_path: Path, *, today: date = TODAY, january: bool = True, first: str = MONTHS_OF_2026[0]
) -> Path:
    """A checkout whose ledger holds 2026 as month files from `first`, and 2027's January if asked.

    The daily index names every day after the newest month to the newest day a
    pass on `today` would take, each quiet, so the marks stand there and the
    only work a pass finds is the year's and the months'. The yearly index is
    there and empty, as the month step leaves it beside the other two.
    """
    root, scratch = tmp_path / "checkout", tmp_path / "scratch"
    months = [month for month in MONTHS_OF_2026 if month >= first] + (
        ["2027-01"] if january else []
    )
    for month in months:
        a_month_file(root, scratch, month)
    index_entries(
        root,
        Period.MONTHLY,
        [
            CompactEntry(covers=month, rows=2, bytes=month_file(root, month).stat().st_size)
            for month in months
        ],
    )
    wake = datetime.combine(today, time.min, tzinfo=UTC)
    newest = schedule.newest_eligible(now=wake, after_days=1).isoformat()
    after = (date.fromisoformat(f"{months[-1]}-01") + timedelta(days=31)).replace(day=1)
    index_entries(
        root,
        Period.DAILY,
        [
            CompactEntry(covers=day, rows=0, bytes=0, state=EntryState.EMPTY)
            for day in days(after.isoformat(), newest)
        ],
    )
    index_entries(root, Period.YEARLY, [])
    return root


def month_file(root: Path, month: str) -> Path:
    found = ledger.compact_file(state(root), VISUALS, Period.MONTHLY, month)
    assert found is not None, f"no month file holds {month}"
    return found


def compact(root: Path, today: date, **knobs: Any) -> Pass:
    """One live pass of the shipped compaction over this checkout, with these knobs changed."""
    return run_task(TASK, root, today=today, dry_run=False, **knobs)


def covers(root: Path, period: Period) -> list[str]:
    path = ledger.compact_index_path(state(root), VISUALS, period)
    return [entry.covers for entry in CompactIndex.read(path).entries] if path.is_file() else []


def yearly(root: Path) -> list[CompactEntry]:
    """The yearly index's entries, oldest first."""
    return CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)).entries


def recorded(
    root: Path, *, quiet: tuple[str, ...] = (), lost: dict[str, list[str]] | None = None
) -> None:
    """Rewrite the monthly index the way the month step records a month since entries had a state.

    Each `quiet` month held no row, so its entry is `empty` and its file goes.
    Each month `lost` names lists those days as recorded lost.
    """
    path = ledger.compact_index_path(state(root), VISUALS, Period.MONTHLY)
    entries = []
    for entry in CompactIndex.read(path).entries:
        month = entry.covers
        if month in quiet:
            month_file(root, month).unlink()
        entries.append(
            CompactEntry(
                covers=month,
                rows=0 if month in quiet else entry.rows,
                bytes=0 if month in quiet else entry.bytes,
                state=EntryState.EMPTY if month in quiet else EntryState.PACKED,
                lost_days=(lost or {}).get(month, []),
            )
        )
    index_entries(root, Period.MONTHLY, entries)


def mark(root: Path, period: Period) -> str | None:
    """How far the indexes the pass left say `period` is packed: where the next pass starts."""
    return marks_on_disk(state(root), VISUALS)[period]


def files_under(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def served(root: Path) -> list[StoredRow[VisualPruneRow]]:
    """Every row the ledger's reader serves, each source read once and nothing settled.

    Settling would fold a row read twice into one, so this counts what the
    sources hold as they are: a row two sources both served shows up twice.
    """
    found = ledger.list_ledger_files(state(root), VISUALS)
    return [
        row
        for source in found.sources
        for row in ledger.load_stored(list(source.paths), model=VisualPruneRow)
    ]


def disjoint(outcome: Pass) -> bool:
    """What the shard that lands a pass requires: no path both written and deleted."""
    return set(outcome.written).isdisjoint(outcome.taken)


def days(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


# --- one pass packs the year ------------------------------------------------------


def test_one_pass_packs_a_finished_year_and_every_row_its_months_held_reads_back_from_it(
    tmp_path: Path,
) -> None:
    """THE ORACLE: the year file holds each month's rows in order, one row group a month."""
    root = a_finished_year(tmp_path)
    held = {
        month: ledger.load_stored([month_file(root, month)], model=VisualPruneRow)
        for month in MONTHS_OF_2026
    }
    everything = served(root)

    outcome = compact(root, TODAY, **PACKS)

    year = ledger.compact_file(state(root), VISUALS, Period.YEARLY, "2026")
    assert year is not None
    assert ledger.load_stored([year], model=VisualPruneRow) == [
        row for month in MONTHS_OF_2026 for row in held[month]
    ]
    footer = pyarrow.parquet.read_metadata(year)
    groups = [footer.row_group(at).num_rows for at in range(footer.num_row_groups)]
    assert groups == [len(held[month]) for month in MONTHS_OF_2026]
    (entry,) = CompactIndex.read(
        ledger.compact_index_path(state(root), VISUALS, Period.YEARLY)
    ).entries
    assert (entry.covers, entry.rows, entry.bytes) == ("2026", 24, year.stat().st_size)
    assert covers(root, Period.MONTHLY) == ["2027-01"]
    assert all(
        ledger.compact_file(state(root), VISUALS, Period.MONTHLY, month) is None
        for month in MONTHS_OF_2026
    )
    assert (mark(root, Period.YEARLY), mark(root, Period.MONTHLY)) == ("2026", "2027-01")
    assert served(root) == everything
    found = ledger.list_ledger_files(state(root), VISUALS)
    assert found.holes == ()
    for day in days("2026-01-01", "2027-01-31"):
        assert len([source for source in found.sources if source.holds(day)]) == 1, day
    assert ledger.load_days(state(root), VISUALS, ["2026-06-20"], model=VisualPruneRow) == [
        a_pass("2026-06-20")
    ]
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


def test_a_second_pass_changes_nothing(tmp_path: Path) -> None:
    root = a_finished_year(tmp_path)
    compact(root, TODAY, **PACKS)
    before = files_under(root)

    again = compact(root, TODAY, **PACKS)

    assert files_under(root) == before
    assert (again.written, again.taken) == ((), ())
    assert again.stopped_because is StopReason.EXHAUSTED


def test_a_dry_run_names_every_path_the_live_pass_changes_and_changes_nothing(
    tmp_path: Path,
) -> None:
    root = a_finished_year(tmp_path)
    before = files_under(root)

    dry = run_task(TASK, root, today=TODAY, **PACKS)

    assert dry.dry_run and files_under(root) == before
    live = compact(root, TODAY, **PACKS)
    assert (dry.written, dry.taken) == (live.written, live.taken)
    assert dry.bytes_freed == live.bytes_freed == sum(len(before[path]) for path in live.taken)


def test_a_window_that_only_reports_packs_a_year_as_a_live_one_does(tmp_path: Path) -> None:
    """A window kept for ever drops nothing, so its switch changes nothing a pass packs."""
    trees = [a_finished_year(tmp_path / "live"), a_finished_year(tmp_path / "reports")]

    live = compact(trees[0], TODAY, **PACKS, month_deletes_dry_run=False)
    reports = compact(trees[1], TODAY, **PACKS, month_deletes_dry_run=True)

    assert (reports.taken, reports.written) == (live.taken, live.written)
    assert reports.selected == live.selected == len(live.taken)
    assert [mark(root, Period.YEARLY) for root in trees] == ["2026", "2026"]


# --- which years a wake packs, and what a year records -----------------------------


@pytest.mark.parametrize(("today", "packed"), [(date(2027, 3, 4), False), (READY, True)])
def test_a_scheduled_wake_packs_a_year_the_day_its_wait_ends_and_not_the_day_before(
    tmp_path: Path, today: date, packed: bool
) -> None:
    """2026 ended at 00:00 UTC on 1 January 2027, and 63 days later is 5 March.

    A wake's listing names only the ledger's marks, so the year step names the
    months it reads itself. January 2027 is old enough to close on both days,
    which is why the monthly index holds it.
    """
    root = a_finished_year(tmp_path, today=today)

    outcome = compact(root, today, wake=True, **SMALLEST)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert (mark(root, Period.YEARLY) == "2026") is packed
    assert (ledger.compact_file(state(root), VISUALS, Period.YEARLY, "2026") is not None) is packed
    assert covers(root, Period.MONTHLY) == (
        ["2027-01"] if packed else [*MONTHS_OF_2026, "2027-01"]
    )


def test_a_ledger_that_began_in_may_packs_its_first_year_from_may(tmp_path: Path) -> None:
    """The months before a ledger's first are not missing, so nothing is asked of them."""
    root = a_finished_year(tmp_path, today=READY, first="2026-05")
    kept = [month for month in MONTHS_OF_2026 if month >= "2026-05"]
    held = [
        row
        for month in kept
        for row in ledger.load_stored([month_file(root, month)], model=VisualPruneRow)
    ]

    outcome = compact(root, READY, wake=True, **SMALLEST)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    year = ledger.compact_file(state(root), VISUALS, Period.YEARLY, "2026")
    assert year is not None
    assert ledger.load_stored([year], model=VisualPruneRow) == held
    assert pyarrow.parquet.read_metadata(year).num_row_groups == len(kept)
    assert covers(root, Period.MONTHLY) == ["2027-01"]


@pytest.mark.parametrize("wake", [False, True], ids=["whole-listing", "wake-listing"])
def test_a_month_with_no_row_adds_none_and_every_month_s_lost_days_carry_into_its_year(
    tmp_path: Path, wake: bool
) -> None:
    """A month closed with no row is an entry with no file, never a missing file."""
    root = a_finished_year(tmp_path, today=READY)
    quiet = ("2026-02", "2026-07")
    recorded(
        root,
        quiet=quiet,
        lost={"2026-02": ["2026-02-10"], "2026-09": ["2026-09-03", "2026-09-30"]},
    )
    kept = [month for month in MONTHS_OF_2026 if month not in quiet]
    held = [
        row
        for month in kept
        for row in ledger.load_stored([month_file(root, month)], model=VisualPruneRow)
    ]

    outcome = compact(root, READY, wake=wake, **SMALLEST)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    year = ledger.compact_file(state(root), VISUALS, Period.YEARLY, "2026")
    assert year is not None
    assert ledger.load_stored([year], model=VisualPruneRow) == held
    assert pyarrow.parquet.read_metadata(year).num_row_groups == len(kept)
    (entry,) = yearly(root)
    assert (entry.state, entry.rows, entry.lost_days) == (
        EntryState.PACKED,
        len(held),
        ["2026-02-10", "2026-09-03", "2026-09-30"],
    )
    assert covers(root, Period.MONTHLY) == ["2027-01"]


def test_a_year_whose_months_hold_no_row_is_an_empty_entry_with_no_file(tmp_path: Path) -> None:
    root = a_finished_year(tmp_path, today=READY)
    recorded(root, quiet=tuple(MONTHS_OF_2026), lost={"2026-03": ["2026-03-14"]})

    outcome = compact(root, READY, **SMALLEST)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert yearly(root) == [
        CompactEntry(
            covers="2026", rows=0, bytes=0, state=EntryState.EMPTY, lost_days=["2026-03-14"]
        )
    ]
    assert ledger.compact_file(state(root), VISUALS, Period.YEARLY, "2026") is None
    assert covers(root, Period.MONTHLY) == ["2027-01"]
    assert mark(root, Period.YEARLY) == "2026", "a year with no row moves the mark too"


def test_a_year_whose_months_hold_no_row_adopts_its_own_file_when_one_is_at_its_path(
    tmp_path: Path
) -> None:
    """An index restored from an older commit can name a year's months while its file holds them.

    Recorded `empty`, the year would hide every row its file holds, so the file
    is adopted, and the days its months list as lost stay lost.
    """
    root = a_finished_year(tmp_path, today=READY)
    rows = [
        row
        for month in MONTHS_OF_2026
        for row in ledger.load_stored([month_file(root, month)], model=VisualPruneRow)
    ]
    own = ledger.persist_period(
        state(root),
        rows,
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.YEARLY,
        covers="2026",
        identity=COMPACTION,
        built_from=len(MONTHS_OF_2026),
    )
    before = own.read_bytes()
    recorded(root, quiet=tuple(MONTHS_OF_2026), lost={"2026-03": ["2026-03-14"]})

    outcome = compact(root, READY, **SMALLEST)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert yearly(root) == [
        CompactEntry(
            covers="2026", rows=len(rows), bytes=len(before), lost_days=["2026-03-14"]
        )
    ]
    assert recovered(outcome, "2026") == [RecoveryNote.INDEX_REBUILT]
    assert own.read_bytes() == before
    assert covers(root, Period.MONTHLY) == ["2027-01"]


# --- a pass that stopped part way ------------------------------------------------


@pytest.mark.parametrize(
    ("landed", "indexed", "left"),
    [
        (1, ["2027-01"], []),
        (2, [*MONTHS_OF_2026, "2027-01"], MONTHS_OF_2026),
        (3, ["2027-01"], MONTHS_OF_2026),
        (6, ["2027-01"], MONTHS_OF_2026[3:]),
        (15, ["2027-01"], []),
    ],
    ids=["data", "year-index", "both-indexes", "three-months-deleted", "all-months-deleted"],
)
def test_a_pass_cut_part_way_loses_and_doubles_no_row_and_the_next_finishes_it_before_its_indexes(
    tmp_path: Path, landed: int, indexed: list[str], left: list[str]
) -> None:
    """Packing decides four kinds of change in order, and any first part of them may land alone.

    Cut before its indexes, the year file no entry names is adopted by the next
    pass, which finishes the year. Cut after them, the yearly mark has moved
    past the year, so no later pass comes back to it: a month both indexes name
    is read from the year, and a month file no index names is read by nothing.
    A person restores the ledger from git. A runner lands a pass in one commit,
    so none of this reaches `main`.
    """
    root = a_finished_year(tmp_path)
    everything = served(root)
    context = context_for(TASK, root, today=TODAY, dry_run=False, **PACKS)
    policy = context.policy
    assert isinstance(policy, CompactionPolicy)
    tree = CompactTree.read(context.state_dir, VISUALS, context.listing)
    now = datetime.combine(TODAY, time.min, tzinfo=UTC)
    chosen = _compaction_periods.choose(tree, policy, now=now, operator_range=None)
    assert chosen.years is not None

    stops = _yearly_period.absorb(tree, chosen.years, identity=COMPACTION)

    assert stops == ()
    tree.finish()
    compact_root = f"{ledger.STATE_DIRNAME}/compact/{VISUALS.value}"
    decided = [change.path.relative_to(root).as_posix() for change in tree.changes]
    assert decided == [
        f"{compact_root}/yearly/2026/2026.parquet",
        f"{compact_root}/index/yearly.json",
        f"{compact_root}/index/monthly.json",
        *[f"{compact_root}/monthly/{month.replace('-', '/')}.parquet" for month in MONTHS_OF_2026],
    ]
    dataclasses.replace(tree, changes=tree.changes[:landed]).apply()
    assert served(root) == everything, "a reader between the two passes lost or doubled a row"

    outcome = compact(root, TODAY, **PACKS)

    assert served(root) == everything
    assert (covers(root, Period.YEARLY), covers(root, Period.MONTHLY)) == (["2026"], indexed)
    assert mark(root, Period.YEARLY) == "2026"
    still = [
        month
        for month in MONTHS_OF_2026
        if ledger.compact_file(state(root), VISUALS, Period.MONTHLY, month) is not None
    ]
    assert still == left
    assert outcome.stopped_because is StopReason.EXHAUSTED and disjoint(outcome)


# --- what waits, what is refused, and who is left alone -----------------------------


@pytest.mark.parametrize(
    "window",
    [{"unit": "forever"}, None],
    ids=["kept-forever", "the-shipped-window"],
)
def test_a_ledger_that_does_not_pack_years_keeps_its_month_files_exactly_as_before(
    tmp_path: Path, window: dict[str, Any] | None
) -> None:
    root = a_finished_year(tmp_path)
    before = files_under(root)

    outcome = compact(root, TODAY, **({} if window is None else {"monthly_window": window}))

    assert files_under(root) == before
    assert (outcome.written, outcome.taken) == ((), ())
    assert not (state(root) / "compact" / VISUALS.value / Period.YEARLY.value).exists()


@pytest.mark.parametrize(
    ("today", "january", "packed"),
    [
        (date(2027, 4, 10), True, False),
        (date(2027, 4, 11), True, True),
        (date(2027, 6, 1), False, False),
    ],
    ids=["a-day-before-its-wait", "the-day-its-wait-ends", "its-next-january-not-absorbed"],
)
def test_a_year_waits_for_its_wait_and_for_its_next_january(
    tmp_path: Path, today: date, january: bool, packed: bool
) -> None:
    """100 days after 2026 ended is 2027-04-11; and a year goes only once January is absorbed."""
    root = a_finished_year(tmp_path, today=today, january=january)

    compact(root, today, monthly_window={"unit": "forever"}, monthly_keep_days=100)

    assert (mark(root, Period.YEARLY) == "2026") is packed
    assert (ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-06") is None) is packed


def without_june(root: Path) -> None:
    """Rewrite the monthly index without June's entry, as an index restored from an older commit."""
    kept = [month for month in [*MONTHS_OF_2026, "2027-01"] if month != "2026-06"]
    index_entries(
        root,
        Period.MONTHLY,
        [
            CompactEntry(covers=month, rows=2, bytes=month_file(root, month).stat().st_size)
            for month in kept
        ],
    )


def test_a_year_missing_a_month_with_nothing_of_it_left_records_its_days_lost(
    tmp_path: Path
) -> None:
    """No entry, no month file, no day file and no raw file: June's rows are gone, and 2026 packs."""
    root = a_finished_year(tmp_path)
    month_file(root, "2026-06").unlink()
    without_june(root)

    outcome = compact(root, TODAY, **PACKS)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    (entry,) = yearly(root)
    assert (entry.covers, entry.state, entry.rows) == ("2026", EntryState.PACKED, 22)
    assert entry.lost_days == days("2026-06-01", "2026-06-30")
    assert recovered(outcome, "2026-06") == [RecoveryNote.RECORDED_LOST]
    assert covers(root, Period.MONTHLY) == ["2027-01"]


def test_a_year_missing_a_month_whose_raw_day_is_still_there_is_refused_and_nothing_moves(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A raw file in June says June never closed, so its days are not lost: a person decides."""
    root = a_finished_year(tmp_path)
    month_file(root, "2026-06").unlink()
    without_june(root)
    ledger.persist(
        state(root),
        [a_pass("2026-06-10")],
        ledger=VISUALS,
        covers="2026-06-10",
        identity=WriterIdentity(
            run_id="2026-06-10-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.visual_prune",
            git_sha="a" * 40,
        ),
    )
    before = files_under(root)

    with caplog.at_level(logging.ERROR):
        outcome = compact(root, TODAY, **PACKS)

    assert (outcome.stopped_because, outcome.resume_from, outcome.fault) == (
        StopReason.FAILED,
        "2026",
        GardenerFault.RAISED,
    )
    assert "monthly.json does not name 2026-06" in caplog.text
    assert f"fault={ledger.LedgerFault.DAY_MISSING}" in caplog.text
    assert files_under(root) == before


def test_a_month_no_entry_names_is_adopted_from_its_own_file_into_its_year(tmp_path: Path) -> None:
    """June's file is at its path while no entry names it, so its rows go into 2026 and none is lost."""
    root = a_finished_year(tmp_path)
    without_june(root)

    outcome = compact(root, TODAY, **PACKS)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    (entry,) = yearly(root)
    assert (entry.rows, entry.lost_days) == (24, [])
    assert recovered(outcome, "2026-06") == [RecoveryNote.INDEX_REBUILT]
    assert ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-06") is None


def test_a_month_file_its_entry_names_that_is_gone_costs_its_year_that_month_s_days(
    tmp_path: Path
) -> None:
    """THE ORACLE for a packed month file that is gone when its year closes: no file to set aside."""
    root = a_finished_year(tmp_path)
    month_file(root, "2026-06").unlink()

    outcome = compact(root, TODAY, **PACKS)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    (entry,) = yearly(root)
    assert (entry.rows, entry.set_aside) == (22, 0)
    assert entry.lost_days == days("2026-06-01", "2026-06-30")
    assert recovered(outcome, "2026-06") == [RecoveryNote.RECORDED_LOST]


def test_a_month_file_that_cannot_be_read_is_set_aside_and_its_year_counts_every_file(
    tmp_path: Path
) -> None:
    """June's file moves under set-aside, its days are lost, and the year adds March's count to it."""
    root = a_finished_year(tmp_path)
    broken = month_file(root, "2026-06")
    broken.write_bytes(b"not a ledger file\n")
    months = [*MONTHS_OF_2026, "2027-01"]
    index_entries(
        root,
        Period.MONTHLY,
        [
            CompactEntry(
                covers=month,
                rows=2,
                bytes=month_file(root, month).stat().st_size,
                set_aside=2 if month == "2026-03" else 0,
            )
            for month in months
        ],
    )

    outcome = compact(root, TODAY, **PACKS)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    (entry,) = yearly(root)
    assert (entry.rows, entry.set_aside) == (22, 3)
    assert entry.lost_days == days("2026-06-01", "2026-06-30")
    moved = state(root) / "raw/visual-prunes/set-aside/compact/visual-prunes/monthly/2026/06.parquet"
    assert moved.read_bytes() == b"not a ledger file\n"
    assert not broken.exists()
    assert recovered(outcome, "2026-06") == [
        RecoveryNote.SET_ASIDE,
        RecoveryNote.RECORDED_LOST,
    ]


@pytest.mark.parametrize("months_kept", [True, False], ids=["months-kept", "months-gone"])
def test_a_year_file_no_entry_names_is_adopted_before_any_month_is_read_or_called_lost(
    tmp_path: Path, months_kept: bool
) -> None:
    """A year file holds exactly its months' rows, so it is adopted first and never written over.

    With the month files still there they go by name; with them gone, which
    their packed entries would otherwise call lost, no day is lost.
    """
    root = a_finished_year(tmp_path)
    rows = [
        row
        for month in MONTHS_OF_2026
        for row in ledger.load_stored([month_file(root, month)], model=VisualPruneRow)
    ]
    own = ledger.persist_period(
        state(root),
        rows,
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.YEARLY,
        covers="2026",
        identity=COMPACTION,
        built_from=len(MONTHS_OF_2026),
    )
    before = own.read_bytes()
    if not months_kept:
        for month in MONTHS_OF_2026:
            month_file(root, month).unlink()

    outcome = compact(root, TODAY, **PACKS)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    assert yearly(root) == [CompactEntry(covers="2026", rows=24, bytes=len(before))]
    assert own.read_bytes() == before
    assert recovered(outcome, "2026") == [RecoveryNote.INDEX_REBUILT]
    assert recovered(outcome, "2026-06") == []
    gone = [ledger.compact_file(state(root), VISUALS, Period.MONTHLY, m) for m in MONTHS_OF_2026]
    assert gone == [None] * len(MONTHS_OF_2026)
    assert covers(root, Period.MONTHLY) == ["2027-01"]
    assert disjoint(outcome)


def test_a_year_file_over_github_s_large_file_line_is_refused_and_its_months_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The line is GitHub's; it is lowered here so a small year crosses it, and nothing else moves."""
    root = a_finished_year(tmp_path)
    before = files_under(root)
    monkeypatch.setattr(_yearly_period, "GITHUB_LARGE_FILE_BYTES", 1000)

    with caplog.at_level(logging.ERROR):
        outcome = compact(root, TODAY, **PACKS)

    assert (outcome.stopped_because, outcome.resume_from, outcome.fault) == (
        StopReason.FAILED,
        "2026",
        GardenerFault.RAISED,
    )
    assert "over GitHub's large-file line of 1000" in caplog.text
    assert files_under(root) == before
