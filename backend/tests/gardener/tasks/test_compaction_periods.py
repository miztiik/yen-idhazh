"""Which months may the month step close on a wake, and what does closing one record?

The month step chooses its months from the ledger's own marks and the wake's
UTC day, never from the window a planner named for another step: that window
offered seven ledgers months from before they began, and their compactions
failed on 2026-10-04. The unit cases ask the chooser over marks written here as
literals. The integration cases run the shipped compaction over ledgers built
under `tmp_path` with the helpers in `_task.py`, live where the declaration
ships as a dry run. Nothing reads the committed `state/` or a clock the test
did not set (CLAUDE.md sections 2 and 13).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import PeriodsChosen, StartReason, StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.period_inputs import scheduled_range
from idhazh.gardener.tasks import _compaction_periods
from idhazh.gardener.tasks._compact_tree import CompactTree

from ._task import declared, run_task
from .test_compaction import VISUALS, a_pass, compact, filed, recovered, state, watermark

pytestmark = pytest.mark.contract

#: The daily span each ledger's index named on 2026-10-04, read from the
#: committed indexes that day. Each of these seven compactions ended `failed`,
#: refusing a month from before its ledger began.
FAILED_ON_2026_10_04: Final = {
    "compact-candidate-models": ("2026-09-01", "2026-09-16"),
    "compact-counterfactual-scores": ("2026-09-01", "2026-10-01"),
    "compact-feed-health": ("2026-08-01", "2026-10-01"),
    "compact-host-fingerprint": ("2026-09-01", "2026-10-01"),
    "compact-published": ("2026-08-01", "2026-10-01"),
    "compact-seen": ("2026-08-01", "2026-10-01"),
    "compact-summary-quality-evals": ("2026-08-01", "2026-09-30"),
}

#: The wake those seven failed on.
FAILED_WAKE: Final = date(2026, 10, 4)

#: The ledger the integration cases build, and what packs it.
TASK: Final = "compact-visual-prunes"

#: The first day the integration ledger holds, the middle of a month.
FIRST_DAY: Final = "2026-09-12"


def days(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


def at(day: date) -> datetime:
    """00:00 UTC on a wake's day, the instant every rule counts from."""
    return datetime.combine(day, time.min, tzinfo=UTC)


def policy_of(name: str, **changed: object) -> CompactionPolicy:
    held = declared()[name]
    assert isinstance(held, CompactionPolicy)
    return CompactionPolicy.model_validate({**held.model_dump(mode="json"), **changed})


def quiet(day: str) -> CompactEntry:
    """A day looked at that held no row: an entry with no file."""
    return CompactEntry(covers=day, rows=0, bytes=0, state=EntryState.EMPTY)


def marks(
    which: LedgerName,
    daily: list[str],
    *,
    monthly: tuple[str, ...] = (),
    monthly_through: str | None = None,
) -> CompactTree:
    """A ledger's marks as a pass reads them, with no file behind them: the chooser reads none."""
    return CompactTree(
        state_dir=Path("state"),
        ledger=which,
        listing=FileListing.from_paths(Path(), [], folders=["state"]),
        daily_through=daily[-1] if daily else None,
        monthly_through=monthly_through,
        yearly_through=None,
        daily={day: quiet(day) for day in daily},
        monthly={month: CompactEntry(covers=month, rows=1, bytes=1) for month in monthly},
        yearly={},
        raw_days=[],
    )


def months_chosen(
    tree: CompactTree,
    policy: CompactionPolicy,
    today: date,
    *,
    operator: tuple[str, str] | None = None,
) -> StepChoice:
    chosen = _compaction_periods.choose(tree, policy, now=at(today), operator_range=operator)
    assert isinstance(chosen, PeriodsChosen)
    return chosen.months


# --- the choice: unit cases over literal marks -------------------------------------


@pytest.mark.parametrize("name", sorted(FAILED_ON_2026_10_04))
def test_no_ledger_that_failed_on_2026_10_04_is_offered_a_month_before_it_began(name: str) -> None:
    """On that wake nothing is old enough to close, and later the first month is the oldest indexed."""
    first, last = FAILED_ON_2026_10_04[name]
    policy = policy_of(name)
    tree = marks(policy.ledger, days(first, last))

    on_the_day = months_chosen(tree, policy, FAILED_WAKE)
    later = months_chosen(tree, policy, date(2026, 11, 20))

    assert (on_the_day.first, on_the_day.start) == (None, StartReason.OLDEST_INDEXED)
    assert later.first in (None, first[:7])
    assert later.start is StartReason.OLDEST_INDEXED


@pytest.mark.parametrize(("today", "closes"), [(date(2026, 11, 14), False), (date(2026, 11, 15), True)])
def test_a_month_may_close_45_whole_days_after_it_ends(today: date, closes: bool) -> None:
    """September ends at 00:00 UTC on 1 October, and 45 days later is 15 November."""
    chosen = _compaction_periods.choose(
        marks(VISUALS, days(FIRST_DAY, "2026-10-01")),
        policy_of(TASK),
        now=at(today),
        operator_range=None,
    )

    assert chosen.newest_closable_month == ("2026-09" if closes else "2026-08")
    assert (chosen.months.first, chosen.months.last) == (
        ("2026-09", "2026-09") if closes else (None, None)
    )


def test_the_daily_mark_must_reach_a_month_s_last_day() -> None:
    """A mark on 30 September closes September; one on 29 September does not."""
    policy = policy_of(TASK)

    reached = months_chosen(marks(VISUALS, days("2026-09-01", "2026-09-30")), policy, date(2026, 12, 1))
    short = months_chosen(marks(VISUALS, days("2026-09-01", "2026-09-29")), policy, date(2026, 12, 1))

    assert (reached.first, reached.last) == ("2026-09", "2026-09")
    assert short.first is None


def test_the_cap_cuts_the_span_and_names_where_the_next_wake_starts() -> None:
    policy = policy_of(TASK, max_periods_per_run=3)
    tree = marks(VISUALS, days("2026-01-01", "2026-12-31"))

    choice = months_chosen(tree, policy, date(2027, 6, 1))

    assert (choice.first, choice.last) == ("2026-01", "2026-03")
    assert (choice.stopped_because, choice.resume_from) == (StopReason.CEILING, "2026-04")


def test_the_span_starts_after_the_monthly_mark() -> None:
    tree = marks(VISUALS, days("2026-09-01", "2026-10-31"), monthly=("2026-08",), monthly_through="2026-08")

    choice = months_chosen(tree, policy_of(TASK), date(2027, 1, 1))

    assert (choice.start, choice.first, choice.last) == (StartReason.MARK, "2026-09", "2026-10")


def test_a_ledger_with_nothing_indexed_offers_nothing() -> None:
    choice = months_chosen(marks(VISUALS, []), policy_of(TASK), date(2027, 1, 1))

    assert (choice.start, choice.first, choice.stopped_because) == (StartReason.NONE, None, None)


@pytest.mark.parametrize(
    ("operator", "today", "expected"),
    [
        (("2026-10", "2026-10"), date(2027, 1, 1), (None, None, StopReason.FAILED, "2026-09")),
        (("2026-10", "2026-10"), date(2026, 11, 1), (None, None, None, None)),
        (("2026-07", "2026-08"), date(2027, 1, 1), (None, None, None, None)),
        (("2026-09", "2026-09"), date(2027, 1, 1), ("2026-09", "2026-09", None, None)),
    ],
    ids=["skips-a-ready-month", "skips-a-month-not-ready", "ends-before", "limits-the-end"],
)
def test_an_operator_range_limits_the_span_and_never_skips_a_ready_month(
    operator: tuple[str, str],
    today: date,
    expected: tuple[str | None, str | None, StopReason | None, str | None],
) -> None:
    """A range that leaves out the month the step must close first is refused at that month."""
    tree = marks(VISUALS, days("2026-09-01", "2026-11-30"), monthly=("2026-08",), monthly_through="2026-08")

    choice = months_chosen(tree, policy_of(TASK), today, operator=operator)

    assert (choice.first, choice.last, choice.stopped_because, choice.resume_from) == expected
    assert choice.start is StartReason.OPERATOR_RANGE or choice.first is not None


# --- the pass: integration over a ledger built under tmp_path ----------------------


def an_index(root: Path, which: LedgerName, period: Period, entries: list[CompactEntry]) -> None:
    path = ledger.compact_index_path(state(root), which, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    held = CompactIndex(
        version=CompactIndex.schema_version(), ledger=which, period=period, entries=entries
    )
    path.write_bytes(held.to_json().encode("ascii"))


def a_daily_mark(root: Path, which: LedgerName, through: str) -> None:
    path = ledger.watermark_path(state(root), which, Period.DAILY)
    path.parent.mkdir(parents=True, exist_ok=True)
    mark = Watermark(
        version=Watermark.schema_version(),
        ledger=which,
        period=Period.DAILY,
        through=through,
        advanced_at="2026-10-02T00:41:00Z",
        run_id="2026-10-02-1",
    )
    path.write_bytes(mark.to_json().encode("ascii"))


def a_packed_day(root: Path, day: str, *, rows: int = 1) -> CompactEntry:
    """One day's packed file, built from `rows` rows filed through the door, and its entry."""
    raws = [filed(root / "scratch", a_pass(day, run=str(number))) for number in range(rows)]
    written = ledger.persist_period(
        state(root),
        ledger.load_stored(raws, model=VisualPruneRow),
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.DAILY,
        covers=day,
        identity=WriterIdentity(
            run_id="2026-10-02-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.compaction",
            git_sha="d" * 40,
        ),
        built_from=len(raws),
    )
    return CompactEntry(covers=day, rows=rows, bytes=written.stat().st_size)


def a_ledger(
    root: Path, *, rows_on: tuple[str, ...], first: str = FIRST_DAY, zero_row_files: bool = False
) -> dict[str, CompactEntry]:
    """A ledger whose first day is `first`, packed through 1 October.

    A quiet day is an entry with no file, or with `zero_row_files` a file
    holding no row, as packing wrote one before entries had a state.
    """
    held = {
        day: a_packed_day(root, day)
        if day in rows_on
        else (a_packed_day(root, day, rows=0) if zero_row_files else quiet(day))
        for day in days(first, "2026-10-01")
    }
    an_index(root, VISUALS, Period.DAILY, [held[day] for day in sorted(held)])
    an_index(root, VISUALS, Period.MONTHLY, [])
    an_index(root, VISUALS, Period.YEARLY, [])
    a_daily_mark(root, VISUALS, "2026-10-01")
    return held


def without(root: Path, day: str, *, keep_file: bool) -> None:
    """Take one day out of the daily index, and out of the tree unless its file is kept."""
    path = ledger.compact_index_path(state(root), VISUALS, Period.DAILY)
    index = CompactIndex.read(path)
    kept = [entry for entry in index.entries if entry.covers != day]
    path.write_bytes(index.model_copy(update={"entries": kept}).to_json().encode("ascii"))
    found = ledger.compact_file(state(root), VISUALS, Period.DAILY, day)
    if found is not None and not keep_file:
        found.unlink()


def september(root: Path) -> CompactEntry:
    """September's monthly entry, which the case has closed."""
    held = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.MONTHLY))
    (found,) = [entry for entry in held.entries if entry.covers == "2026-09"]
    return found


def daily_september(root: Path) -> list[str]:
    """The September days the daily index still names."""
    held = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.DAILY))
    return [entry.covers for entry in held.entries if entry.covers.startswith("2026-09-")]


def month_rows(root: Path) -> list[str]:
    found = ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-09")
    assert found is not None, "no month file holds September"
    return [row.date for row in ledger.load([found], model=VisualPruneRow)]


ROWS_ON: Final = ("2026-09-12", "2026-09-20", "2026-09-25")


@pytest.mark.parametrize("name", sorted(FAILED_ON_2026_10_04))
def test_none_of_the_seven_ends_failed_on_the_wake_they_failed_on(tmp_path: Path, name: str) -> None:
    """The planner's window still names the months before each ledger began; the month step ignores it."""
    first, last = FAILED_ON_2026_10_04[name]
    policy = policy_of(name)
    root = tmp_path / "checkout"
    an_index(root, policy.ledger, Period.DAILY, [quiet(day) for day in days(first, last)])
    an_index(root, policy.ledger, Period.MONTHLY, [])
    an_index(root, policy.ledger, Period.YEARLY, [])
    a_daily_mark(root, policy.ledger, last)

    outcome = run_task(
        name, root, today=FAILED_WAKE, period_range=scheduled_range(name, policy, FAILED_WAKE)
    )

    assert outcome.stopped_because is not StopReason.FAILED, outcome.resume_from
    assert watermark(root, Period.MONTHLY, policy.ledger) is None
    expected = min(
        date.fromisoformat(last) + timedelta(days=policy.max_periods_per_run),
        FAILED_WAKE - timedelta(days=policy.compact_after_days + 1),
    ).isoformat()
    assert watermark(root, Period.DAILY, policy.ledger) == expected
    assert outcome.until == "2026-10-02"


@pytest.mark.parametrize(("today", "closes"), [(date(2026, 11, 14), False), (date(2026, 11, 15), True)])
def test_a_ledger_from_the_12th_closes_september_on_the_15th_of_november_from_its_first_day(
    tmp_path: Path, today: date, closes: bool
) -> None:
    """The days before the ledger's first are not holes: nothing is recorded for them."""
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=ROWS_ON)

    outcome = compact(root, today)

    assert outcome.stopped_because is not StopReason.FAILED
    assert watermark(root, Period.MONTHLY) == ("2026-09" if closes else None)
    if closes:
        closed = september(root)
        assert (closed.state, closed.rows, closed.lost_days) == (EntryState.PACKED, 3, [])
        assert month_rows(root) == list(ROWS_ON)
        assert daily_september(root) == []


def test_a_day_missing_with_its_raw_files_is_packed_again_and_its_month_closes_next_wake(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=ROWS_ON)
    without(root, "2026-09-20", keep_file=False)
    filed(root, a_pass("2026-09-20", run="7"))

    held = compact(root, date(2026, 11, 15))

    assert watermark(root, Period.MONTHLY) is None, "a raw day waiting holds its month"
    index = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.DAILY))
    assert {entry.covers: entry.rows for entry in index.entries}["2026-09-20"] == 1
    assert held.stopped_because is not StopReason.FAILED

    compact(root, date(2026, 11, 15))

    assert watermark(root, Period.MONTHLY) == "2026-09"
    assert september(root).lost_days == []
    assert month_rows(root) == list(ROWS_ON)


@pytest.mark.parametrize(
    ("rows_on", "state_"),
    [(ROWS_ON, EntryState.PACKED), (("2026-09-20",), EntryState.EMPTY)],
    ids=["other-days-hold-rows", "the-lost-day-held-the-only-row"],
)
def test_a_day_missing_with_nothing_to_rebuild_it_is_listed_lost_on_a_month_never_lost(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, rows_on: tuple[str, ...], state_: EntryState
) -> None:
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=rows_on)
    without(root, "2026-09-20", keep_file=False)

    with caplog.at_level(logging.WARNING):
        outcome = compact(root, date(2026, 11, 15))

    assert outcome.stopped_because is not StopReason.FAILED
    closed = september(root)
    assert (closed.state, closed.lost_days) == (state_, ["2026-09-20"])
    assert recovered(caplog, "2026-09-20") == [f"note={RecoveryNote.RECORDED_LOST}"]
    assert (ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-09") is None) is (
        state_ is EntryState.EMPTY
    )


def test_a_day_whose_entry_is_gone_and_whose_file_is_kept_is_adopted_not_lost(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=ROWS_ON)
    without(root, "2026-09-25", keep_file=True)

    with caplog.at_level(logging.WARNING):
        compact(root, date(2026, 11, 15))

    assert september(root).lost_days == []
    assert month_rows(root) == list(ROWS_ON)
    assert recovered(caplog, "2026-09-25") == [f"note={RecoveryNote.INDEX_REBUILT}"]


def test_a_month_with_no_row_is_an_empty_entry_with_no_file(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=())

    compact(root, date(2026, 11, 15))

    assert september(root) == CompactEntry(covers="2026-09", rows=0, bytes=0, state=EntryState.EMPTY)
    assert ledger.compact_file(state(root), VISUALS, Period.MONTHLY, "2026-09") is None
    assert daily_september(root) == []


def test_a_lost_day_entry_goes_into_its_month_s_lost_days(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    held = a_ledger(root, rows_on=ROWS_ON)
    held["2026-09-15"] = CompactEntry(covers="2026-09-15", rows=0, bytes=0, state=EntryState.LOST)
    an_index(root, VISUALS, Period.DAILY, [held[day] for day in sorted(held)])

    compact(root, date(2026, 11, 15))

    assert september(root).lost_days == ["2026-09-15"]
    assert month_rows(root) == list(ROWS_ON)


def test_an_indexed_empty_month_finishes_without_a_file_to_look_for(tmp_path: Path) -> None:
    """A pass that stopped after the monthly index landed left the month's days behind."""
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=())
    a_packed_day(root, "2026-09-13")
    an_index(root, VISUALS, Period.MONTHLY, [quiet("2026-09")])

    outcome = compact(root, date(2026, 11, 15))

    assert outcome.stopped_because is not StopReason.FAILED
    assert watermark(root, Period.MONTHLY) == "2026-09"
    assert ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-13") is None
    assert daily_september(root) == []


def a_month_file(root: Path, rows_on: tuple[str, ...]) -> Path:
    """September's own month file at its path, built from these days' rows, named by no entry."""
    raws = [filed(root / "scratch", a_pass(day, run=str(number))) for number, day in enumerate(rows_on)]
    return ledger.persist_period(
        state(root),
        ledger.load_stored(raws, model=VisualPruneRow),
        model=VisualPruneRow,
        ledger=VISUALS,
        period=Period.MONTHLY,
        covers="2026-09",
        identity=WriterIdentity(
            run_id="2026-10-02-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.compaction",
            git_sha="d" * 40,
        ),
        built_from=len(raws),
    )


def test_a_month_file_no_entry_names_is_adopted_when_its_days_give_no_row(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An index restored from an older commit lost the month; its file is the month's record."""
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=(), first="2026-09-01")
    held = a_month_file(root, ROWS_ON)

    with caplog.at_level(logging.WARNING):
        compact(root, date(2026, 11, 15))

    assert september(root) == CompactEntry(covers="2026-09", rows=3, bytes=held.stat().st_size)
    assert month_rows(root) == list(ROWS_ON)
    assert recovered(caplog, "2026-09") == [f"note={RecoveryNote.INDEX_REBUILT}"]


def test_a_month_file_no_entry_names_that_holds_other_rows_than_its_days_is_refused(
    tmp_path: Path,
) -> None:
    """Nothing is written over it: which of the two is the month is for a person to read."""
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=ROWS_ON, first="2026-09-01", zero_row_files=True)
    held = a_month_file(root, ("2026-09-12",))
    before = held.read_bytes()

    outcome = compact(root, date(2026, 11, 15))

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.FAILED, "2026-09")
    assert held.read_bytes() == before
    assert watermark(root, Period.MONTHLY) is None
    assert daily_september(root) == days("2026-09-01", "2026-09-30")