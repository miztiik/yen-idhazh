"""Which periods may the drop, year, month and day steps take on a wake, and what does taking one record?

Each step chooses its periods from the ledger's own marks and the wake's UTC
day, never from the window a planner named for another step: that window
offered seven ledgers months from before they began, and their compactions
failed on 2026-10-04, and it named no month a new day falls in, so no
compaction packed one. The unit cases ask the chooser over marks written here
as literals. The integration cases run the shipped compaction over ledgers
built under `tmp_path` with the helpers in `_task.py`, live where the
declaration ships as a dry run, some over the listing a scheduled wake builds.
Nothing reads the committed `state/` or a clock the test did not set (CLAUDE.md
sections 2 and 13).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger, month_partition
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import PeriodsChosen, StartReason, StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import _compaction_periods
from idhazh.gardener.tasks._compact_tree import CompactTree

from ._task import declared, run_task
from .test_compaction import (
    DROP_WAKE,
    VISUALS,
    a_pass,
    chosen_on,
    compact,
    disjoint,
    filed,
    mark,
    recovered,
    state,
)

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
    yearly: tuple[str, ...] = (),
    raw_days: tuple[str, ...] = (),
) -> CompactTree:
    """A ledger's indexes as a pass reads them, with no file behind them: the chooser reads none.

    The marks are worked out from the entries, as every pass works them out.
    `raw_days` are the names of the raw days the pass's listing holds.
    """
    return CompactTree(
        state_dir=Path("state"),
        ledger=which,
        listing=FileListing.from_paths(Path(), [], folders=["state"]),
        daily={day: quiet(day) for day in daily},
        monthly={month: CompactEntry(covers=month, rows=1, bytes=1) for month in monthly},
        yearly={year: CompactEntry(covers=year, rows=1, bytes=1) for year in yearly},
        raw_days=sorted(raw_days),
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
    tree = marks(VISUALS, days("2026-09-01", "2026-10-31"), monthly=("2026-08",))

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
    tree = marks(VISUALS, days("2026-09-01", "2026-11-30"), monthly=("2026-08",))

    choice = months_chosen(tree, policy_of(TASK), today, operator=operator)

    assert (choice.first, choice.last, choice.stopped_because, choice.resume_from) == expected
    assert choice.start is StartReason.OPERATOR_RANGE or choice.first is not None


# --- the day step's choice: unit cases over literal marks --------------------------


def days_chosen(
    tree: CompactTree,
    policy: CompactionPolicy,
    today: date,
    *,
    operator: tuple[str, str] | None = None,
) -> StepChoice:
    return _compaction_periods.choose(tree, policy, now=at(today), operator_range=operator).days


def test_new_days_run_from_the_day_after_the_mark_to_the_cap() -> None:
    """A mark of 16 September, eight days a wake, one whole day after each: 17 to 24 September."""
    chosen = _compaction_periods.choose(
        marks(VISUALS, days(FIRST_DAY, "2026-09-16")),
        policy_of(TASK, max_periods_per_run=8, compact_after_days=1),
        now=at(FAILED_WAKE),
        operator_range=None,
    )

    assert chosen.newest_eligible_day == "2026-10-02"
    assert (chosen.days.start, chosen.days.first, chosen.days.last) == (
        StartReason.MARK,
        "2026-09-17",
        "2026-09-24",
    )
    assert (chosen.days.stopped_because, chosen.days.resume_from) == (
        StopReason.CEILING,
        "2026-09-25",
    )


def test_new_days_end_at_the_newest_due_day() -> None:
    choice = days_chosen(marks(VISUALS, days(FIRST_DAY, "2026-09-28")), policy_of(TASK), FAILED_WAKE)

    assert (choice.first, choice.last, choice.stopped_because) == ("2026-09-29", "2026-10-02", None)


def test_a_mark_on_the_newest_due_day_offers_no_new_day() -> None:
    choice = days_chosen(marks(VISUALS, days(FIRST_DAY, "2026-10-02")), policy_of(TASK), FAILED_WAKE)

    assert (choice.start, choice.first, choice.stopped_because) == (StartReason.MARK, None, None)


def test_a_first_run_starts_at_the_oldest_raw_day_in_the_months_it_looks_back_over() -> None:
    """Two months back from the newest due day's month: August to October, and not May."""
    tree = marks(VISUALS, [], raw_days=("2026-05-10", "2026-08-12", "2026-09-20"))

    choice = days_chosen(tree, policy_of(TASK, lookback=2), FAILED_WAKE)

    assert (choice.start, choice.first, choice.last) == (
        StartReason.OLDEST_RAW_DAY,
        "2026-08-12",
        "2026-08-19",
    )
    assert (choice.stopped_because, choice.resume_from) == (StopReason.CEILING, "2026-08-20")


@pytest.mark.parametrize(
    ("lookback", "looked_over"),
    [(None, ("2026-08", "2026-10")), (4, ("2026-06", "2026-10"))],
    ids=["default", "configured"],
)
def test_a_first_run_looks_back_over_the_newest_due_month_and_lookback_months_before_it(
    lookback: int | None, looked_over: tuple[str, str]
) -> None:
    """The newest due day is 2 October, so October and, by default, the two months before it."""
    looked = _compaction_periods.first_run_months(
        marks(VISUALS, []),
        policy_of(TASK, lookback=lookback),
        now=at(FAILED_WAKE),
        operator_range=None,
    )

    assert looked == month_partition.months_between(*looked_over)


def test_a_first_run_with_no_raw_day_in_reach_takes_nothing() -> None:
    tree = marks(VISUALS, [], raw_days=("2026-05-10",))

    choice = days_chosen(tree, policy_of(TASK, lookback=2), FAILED_WAKE)

    assert (choice.start, choice.first, choice.stopped_because) == (StartReason.NONE, None, None)


@pytest.mark.parametrize(
    ("reports", "start", "first"),
    [(False, "keep-line", "2026-09-03"), (True, "oldest-raw-day", "2026-08-12")],
    ids=["deletes-live", "deletes-report"],
)
def test_a_first_run_starts_no_earlier_than_the_keep_line_while_month_deletes_are_live(
    reports: bool, start: str, first: str
) -> None:
    """A one-month window keeps September on at 16 November; August's raw day is past it."""
    policy = policy_of(
        TASK,
        lookback=3,
        monthly_window={"unit": "months", "value": 1},
        month_deletes_dry_run=reports,
    )
    tree = marks(VISUALS, [], raw_days=("2026-08-12", "2026-09-03"))

    chosen = _compaction_periods.choose(tree, policy, now=at(date(2026, 11, 16)), operator_range=None)

    assert chosen.keep_line == "2026-09"
    assert (chosen.days.start, chosen.days.first) == (start, first)


@pytest.mark.parametrize(
    ("operator", "today", "expected"),
    [
        (("2026-10", "2026-10"), date(2026, 12, 20), (None, None, StopReason.FAILED, "2026-09-17")),
        (("2026-10", "2026-10"), date(2026, 9, 18), (None, None, None, None)),
        (("2026-07", "2026-08"), date(2026, 12, 20), (None, None, None, None)),
        (("2026-09", "2026-09"), date(2026, 12, 20), ("2026-09-17", "2026-09-30", None, None)),
    ],
    ids=["skips-a-due-day", "skips-a-day-not-due", "ends-before", "limits-the-end"],
)
def test_an_operator_range_limits_the_new_days_and_never_skips_a_due_one(
    operator: tuple[str, str],
    today: date,
    expected: tuple[str | None, str | None, StopReason | None, str | None],
) -> None:
    """A range that leaves out the day the step must pack first is refused at that day."""
    tree = marks(VISUALS, days(FIRST_DAY, "2026-09-16"))

    choice = days_chosen(tree, policy_of(TASK, max_periods_per_run=31), today, operator=operator)

    assert (choice.first, choice.last, choice.stopped_because, choice.resume_from) == expected
    assert choice.start is StartReason.OPERATOR_RANGE or choice.first is not None


@pytest.mark.parametrize(
    ("through", "operator", "span"),
    [
        ("2026-09-16", None, ("2026-09-04", "2026-09-16")),
        ("2026-09-03", None, None),
        (None, None, None),
        ("2026-10-02", ("2026-09", "2026-09"), ("2026-09-04", "2026-09-30")),
        ("2026-09-16", ("2026-10", "2026-10"), None),
    ],
    ids=["to-the-mark", "mark-older-than-the-span", "no-mark", "inside-a-range", "range-after"],
)
def test_the_re_run_span_runs_from_thirty_days_before_the_wake_to_the_mark(
    through: str | None, operator: tuple[str, str] | None, span: tuple[str, str] | None
) -> None:
    """GitHub lets a run be re-run for 30 days, and a re-run writes into its first day."""
    tree = marks(VISUALS, days("2026-09-01", through) if through is not None else [])

    chosen = _compaction_periods.choose(
        tree, policy_of(TASK), now=at(FAILED_WAKE), operator_range=operator
    )

    assert chosen.rerun_span == span


# --- the year step's choice: unit cases over literal marks -------------------------

#: The smallest waits the declaration contract allows that pack years: a month
#: closes 31 days after it ends, and a year 63 days after, 31 plus 32.
PACKS_YEARS: Final[dict[str, object]] = {
    "daily_keep_days": 31,
    "monthly_window": {"unit": "forever"},
    "monthly_keep_days": 63,
}


def closed(first: str, last: str) -> tuple[str, ...]:
    """The months from `first` to `last`, each closed into the monthly index."""
    return tuple(month_partition.months_between(first, last))


def years_chosen(
    tree: CompactTree,
    policy: CompactionPolicy,
    today: date,
    *,
    operator: tuple[str, str] | None = None,
) -> StepChoice:
    chosen = _compaction_periods.choose(tree, policy, now=at(today), operator_range=operator)
    assert chosen.years is not None, "a declaration that packs years chooses years"
    return chosen.years


@pytest.mark.parametrize(("today", "ready"), [(date(2027, 3, 4), False), (date(2027, 3, 5), True)])
def test_a_year_may_be_packed_63_whole_days_after_it_ends(today: date, ready: bool) -> None:
    """2026 ends at 00:00 UTC on 1 January 2027, and 63 days later is 5 March.

    January 2027 is old enough to close on both days, which is why the monthly
    index holds it and the monthly mark stands on it.
    """
    tree = marks(VISUALS, [], monthly=closed("2026-01", "2027-01"))

    chosen = _compaction_periods.choose(
        tree, policy_of(TASK, **PACKS_YEARS), now=at(today), operator_range=None
    )

    assert chosen.newest_closable_month == "2027-01"
    assert chosen.newest_packable_year == ("2026" if ready else "2025")
    assert chosen.years is not None
    assert (chosen.years.start, chosen.years.first, chosen.years.last) == (
        StartReason.OLDEST_INDEXED,
        "2026" if ready else None,
        "2026" if ready else None,
    )


@pytest.mark.parametrize(
    "operator", [None, ("2026-01", "2026-12")], ids=["scheduled", "the-year-named-whole"]
)
def test_a_year_waits_while_the_monthly_mark_stands_on_its_december(
    operator: tuple[str, str] | None,
) -> None:
    """The mark must be strictly past December, whether or not a range names the year."""
    tree = marks(VISUALS, [], monthly=closed("2026-01", "2026-12"))

    choice = years_chosen(tree, policy_of(TASK, **PACKS_YEARS), date(2027, 6, 1), operator=operator)

    assert (choice.first, choice.stopped_because) == (None, None)


def test_a_ledger_that_began_in_may_chooses_its_first_year() -> None:
    tree = marks(VISUALS, [], monthly=closed("2026-05", "2027-01"))

    choice = years_chosen(tree, policy_of(TASK, **PACKS_YEARS), date(2027, 3, 5))

    assert (choice.start, choice.first, choice.last) == (StartReason.OLDEST_INDEXED, "2026", "2026")


def test_the_years_start_after_the_yearly_mark_and_the_cap_cuts_them() -> None:
    """Five years are ready and two go a wake: 2027 and 2028, and the next wake starts at 2029."""
    tree = marks(
        VISUALS,
        [],
        monthly=closed("2027-01", "2032-01"),
        yearly=("2026",),
    )

    choice = years_chosen(
        tree, policy_of(TASK, **PACKS_YEARS, max_periods_per_run=2), date(2032, 3, 5)
    )

    assert (choice.start, choice.first, choice.last) == (StartReason.MARK, "2027", "2028")
    assert (choice.stopped_because, choice.resume_from) == (StopReason.CEILING, "2029")


def test_a_ledger_with_nothing_indexed_offers_no_year() -> None:
    choice = years_chosen(marks(VISUALS, []), policy_of(TASK, **PACKS_YEARS), date(2027, 3, 5))

    assert (choice.start, choice.first, choice.stopped_because) == (StartReason.NONE, None, None)


def test_a_declaration_that_packs_no_year_chooses_no_year() -> None:
    tree = marks(VISUALS, [], monthly=closed("2026-01", "2027-01"))

    chosen = _compaction_periods.choose(
        tree, policy_of(TASK), now=at(date(2028, 1, 1)), operator_range=None
    )

    assert (chosen.newest_packable_year, chosen.years) == (None, None)


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        (("2026-01", "2026-12"), (StartReason.OLDEST_INDEXED, "2026", "2026", None, None)),
        (("2026-01", "2027-03"), (StartReason.OLDEST_INDEXED, "2026", "2026", None, None)),
        (("2026-11", "2026-12"), (StartReason.OPERATOR_RANGE, None, None, None, None)),
        (("2026-02", "2026-11"), (StartReason.OPERATOR_RANGE, None, None, None, None)),
        (
            ("2027-01", "2027-12"),
            (StartReason.OPERATOR_RANGE, None, None, StopReason.FAILED, "2026"),
        ),
        (("2025-01", "2025-12"), (StartReason.OPERATOR_RANGE, None, None, None, None)),
    ],
    ids=[
        "names-a-year-whole",
        "names-one-year-whole-and-part-of-the-next",
        "names-the-end-of-a-year",
        "names-the-middle-of-a-year",
        "skips-a-ready-year",
        "ends-before",
    ],
)
def test_an_operator_range_limits_the_years_to_those_it_holds_whole(
    operator: tuple[str, str],
    expected: tuple[StartReason, str | None, str | None, StopReason | None, str | None],
) -> None:
    """A year goes under a range only when the range names its January to its December.

    So a ranged pass reads no month outside the range. A range that holds no
    whole year asks for no year's work, so it takes none and refuses none; a
    range that holds a whole year and leaves out an older ready one is refused
    at that year, as the month step refuses a month.
    """
    tree = marks(VISUALS, [], monthly=closed("2026-01", "2028-01"))

    choice = years_chosen(tree, policy_of(TASK, **PACKS_YEARS), date(2028, 6, 1), operator=operator)

    assert (
        choice.start,
        choice.first,
        choice.last,
        choice.stopped_because,
        choice.resume_from,
    ) == expected


# --- the drop step's choice: unit cases over literal marks -------------------------


def drops_chosen(
    tree: CompactTree,
    policy: CompactionPolicy,
    today: date,
    *,
    operator: tuple[str, str] | None = None,
) -> StepChoice:
    chosen = _compaction_periods.choose(tree, policy, now=at(today), operator_range=operator)
    assert chosen.drops is not None, "a monthly window that drops months chooses months to drop"
    return chosen.drops


def test_the_drop_step_takes_the_oldest_months_past_the_keep_line_to_the_cap() -> None:
    """Nine months are past the line and eight go a wake: January to August 2025, then September."""
    tree = marks(VISUALS, [], monthly=closed("2025-01", "2026-09"))

    chosen = _compaction_periods.choose(
        tree, policy_of(TASK), now=at(DROP_WAKE), operator_range=None
    )

    assert (chosen.keep_line, chosen.cap) == ("2025-10", 8)
    assert chosen.drops == StepChoice(
        start=StartReason.OLDEST_INDEXED,
        first="2025-01",
        last="2025-08",
        stopped_because=StopReason.CEILING,
        resume_from="2025-09",
    )


@pytest.mark.parametrize(
    ("oldest", "span"),
    [("2025-09", ("2025-09", "2025-09")), ("2025-10", (None, None))],
    ids=["one-month-left-past-the-line", "none-left-past-the-line"],
)
def test_the_next_wake_starts_at_the_oldest_month_the_index_still_names(
    oldest: str, span: tuple[str | None, str | None]
) -> None:
    """A dropped month has left the index, so no later wake chooses it again."""
    tree = marks(VISUALS, [], monthly=closed(oldest, "2026-09"))

    choice = drops_chosen(tree, policy_of(TASK), DROP_WAKE)

    assert (choice.start, choice.first, choice.last, choice.stopped_because) == (
        StartReason.OLDEST_INDEXED,
        *span,
        None,
    )


def test_the_cap_counts_entries_so_a_month_the_index_does_not_name_is_not_one() -> None:
    """With February 2025 named nowhere, a cap of 3 takes January, March and April."""
    tree = marks(
        VISUALS,
        [],
        monthly=("2025-01", *closed("2025-03", "2026-09")),
    )

    choice = drops_chosen(tree, policy_of(TASK, max_periods_per_run=3), DROP_WAKE)

    assert (choice.first, choice.last, choice.stopped_because, choice.resume_from) == (
        "2025-01",
        "2025-04",
        StopReason.CEILING,
        "2025-05",
    )


def test_a_monthly_window_that_keeps_every_month_chooses_no_drop() -> None:
    tree = marks(VISUALS, [], monthly=closed("2025-01", "2026-09"))

    chosen = _compaction_periods.choose(
        tree,
        policy_of(TASK, monthly_window={"unit": "forever"}),
        now=at(DROP_WAKE),
        operator_range=None,
    )

    assert (chosen.keep_line, chosen.drops) == (None, None)


def test_a_ledger_with_no_month_indexed_has_nothing_to_drop() -> None:
    assert drops_chosen(marks(VISUALS, []), policy_of(TASK), DROP_WAKE) == StepChoice(
        start=StartReason.NONE
    )


@pytest.mark.parametrize(
    ("operator", "expected"),
    [
        (
            ("2025-01", "2026-12"),
            (StartReason.OLDEST_INDEXED, "2025-01", "2025-08", StopReason.CEILING, "2025-09"),
        ),
        (("2025-03", "2025-05"), (StartReason.OPERATOR_RANGE, "2025-03", "2025-05", None, None)),
        (("2025-06", "2026-12"), (StartReason.OPERATOR_RANGE, "2025-06", "2025-09", None, None)),
        (("2024-01", "2024-12"), (StartReason.OPERATOR_RANGE, None, None, None, None)),
        (("2025-10", "2026-09"), (StartReason.OPERATOR_RANGE, None, None, None, None)),
    ],
    ids=[
        "holds-every-old-month",
        "names-three-old-months",
        "starts-after-the-oldest",
        "ends-before",
        "names-only-kept-months",
    ],
)
def test_an_operator_range_only_narrows_the_drops_and_refuses_nothing(
    operator: tuple[str, str],
    expected: tuple[StartReason, str | None, str | None, StopReason | None, str | None],
) -> None:
    """A month the range leaves out stays in the index for a later pass, so no month is skipped."""
    tree = marks(VISUALS, [], monthly=closed("2025-01", "2026-09"))

    choice = drops_chosen(tree, policy_of(TASK), DROP_WAKE, operator=operator)

    assert (
        choice.start,
        choice.first,
        choice.last,
        choice.stopped_because,
        choice.resume_from,
    ) == expected


# --- the pass: integration over a ledger built under tmp_path ----------------------


def an_index(root: Path, which: LedgerName, period: Period, entries: list[CompactEntry]) -> None:
    path = ledger.compact_index_path(state(root), which, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    held = CompactIndex(
        version=CompactIndex.schema_version(), ledger=which, period=period, entries=entries
    )
    path.write_bytes(held.to_json().encode("ascii"))


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
    """A wake's listing names only each ledger's marks, and the month step names what it chooses."""
    first, last = FAILED_ON_2026_10_04[name]
    policy = policy_of(name)
    root = tmp_path / "checkout"
    an_index(root, policy.ledger, Period.DAILY, [quiet(day) for day in days(first, last)])
    an_index(root, policy.ledger, Period.MONTHLY, [])
    an_index(root, policy.ledger, Period.YEARLY, [])

    outcome = run_task(name, root, today=FAILED_WAKE, wake=True)

    assert outcome.stopped_because is not StopReason.FAILED, outcome.resume_from
    assert mark(root, Period.MONTHLY, policy.ledger) is None


@pytest.mark.parametrize(("today", "closes"), [(date(2026, 11, 14), False), (date(2026, 11, 15), True)])
def test_a_ledger_from_the_12th_closes_september_on_the_15th_of_november_from_its_first_day(
    tmp_path: Path, today: date, closes: bool
) -> None:
    """The days before the ledger's first are not holes: nothing is recorded for them."""
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=ROWS_ON)

    outcome = compact(root, today)

    assert outcome.stopped_because is not StopReason.FAILED
    assert mark(root, Period.MONTHLY) == ("2026-09" if closes else None)
    if closes:
        closed = september(root)
        assert (closed.state, closed.rows, closed.lost_days) == (EntryState.PACKED, 3, [])
        assert month_rows(root) == list(ROWS_ON)
        assert daily_september(root) == []


@pytest.mark.parametrize("wake", [False, True], ids=["whole-listing", "wake-listing"])
def test_a_day_missing_with_its_raw_files_is_packed_again_and_its_month_closes_next_wake(
    tmp_path: Path, wake: bool
) -> None:
    """The day is 56 days old on 15 November, past the 30-day re-run span, and still packed.

    The month step holds September while the day's raw files wait, so the day
    step packs a raw day at or below its mark in any month not yet closed, or
    the month would wait for ever. Over a wake's listing the month step names
    September's raw folder, which is where the day step finds the day.
    """
    root = tmp_path / "checkout"
    a_ledger(root, rows_on=ROWS_ON)
    without(root, "2026-09-20", keep_file=False)
    filed(root, a_pass("2026-09-20", run="7"))

    held = compact(root, date(2026, 11, 15), wake=wake)

    assert mark(root, Period.MONTHLY) is None, "a raw day waiting holds its month"
    index = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.DAILY))
    assert {entry.covers: entry.rows for entry in index.entries}["2026-09-20"] == 1
    assert held.stopped_because is not StopReason.FAILED

    compact(root, date(2026, 11, 15), wake=wake)

    assert mark(root, Period.MONTHLY) == "2026-09"
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
    assert mark(root, Period.MONTHLY) is None
    assert daily_september(root) == days("2026-09-01", "2026-09-30")


# --- the day step: integration over a ledger built under tmp_path ------------------


def a_marked_ledger(root: Path, through: str) -> None:
    """A ledger packed from FIRST_DAY through `through`, every day quiet, nothing coarser."""
    an_index(root, VISUALS, Period.DAILY, [quiet(day) for day in days(FIRST_DAY, through)])
    an_index(root, VISUALS, Period.MONTHLY, [])
    an_index(root, VISUALS, Period.YEARLY, [])


def daily_entries(root: Path) -> dict[str, CompactEntry]:
    held = CompactIndex.read(ledger.compact_index_path(state(root), VISUALS, Period.DAILY))
    return {entry.covers: entry for entry in held.entries}


def test_raw_days_after_the_mark_reach_the_newest_due_day_in_two_wakes(tmp_path: Path) -> None:
    """A wake's listing names only the ledger's marks; the day step names its own days."""
    root = tmp_path / "checkout"
    a_marked_ledger(root, "2026-09-16")
    for day in days("2026-09-17", "2026-10-02"):
        filed(root, a_pass(day))

    first = compact(root, FAILED_WAKE, wake=True)

    assert (first.stopped_because, first.resume_from) == (StopReason.CEILING, "2026-09-25")
    assert mark(root, Period.DAILY) == "2026-09-24"

    second = compact(root, FAILED_WAKE, wake=True)

    assert second.stopped_because is StopReason.EXHAUSTED
    assert mark(root, Period.DAILY) == "2026-10-02"
    assert list(daily_entries(root)) == days(FIRST_DAY, "2026-10-02")
    assert ledger.list_raw_files(state(root), VISUALS) == []
    assert disjoint(first) and disjoint(second)


def test_a_first_run_over_a_wake_s_listing_starts_at_its_oldest_raw_day(tmp_path: Path) -> None:
    """The planner names no month a first run looks back over, so the pass names them first."""
    root = tmp_path / "checkout"
    for day in (FIRST_DAY, "2026-09-20"):
        filed(root, a_pass(day))

    outcome = compact(root, FAILED_WAKE, wake=True)

    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.CEILING, "2026-09-20")
    assert list(daily_entries(root)) == days(FIRST_DAY, "2026-09-19")
    assert mark(root, Period.DAILY) == "2026-09-19"


def test_a_day_with_no_row_is_an_entry_with_no_file(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    a_marked_ledger(root, "2026-09-28")
    filed(root, a_pass("2026-09-30"))

    compact(root, FAILED_WAKE)

    held = daily_entries(root)
    for day in ("2026-09-29", "2026-10-01", "2026-10-02"):
        assert held[day] == quiet(day)
        assert ledger.compact_file(state(root), VISUALS, Period.DAILY, day) is None
    assert (held["2026-09-30"].state, held["2026-09-30"].rows) == (EntryState.PACKED, 1)
    assert mark(root, Period.DAILY) == "2026-10-02", "a day with no row moves the mark too"


@pytest.mark.parametrize("wake", [False, True], ids=["whole-listing", "wake-listing"])
@pytest.mark.parametrize("state_", [EntryState.EMPTY, EntryState.LOST])
def test_a_re_run_into_a_day_recorded_with_no_file_is_packed_from_its_raw_files(
    tmp_path: Path, state_: EntryState, wake: bool
) -> None:
    """A re-run lands in a day recorded with no file: nothing is missing, so it is packed.

    Over a wake's listing the day step finds the re-run by naming the raw
    folders of the days a re-run may still write into.
    """
    root = tmp_path / "checkout"
    held = {day: quiet(day) for day in days(FIRST_DAY, "2026-09-28")}
    held["2026-09-19"] = a_packed_day(root, "2026-09-19")
    held["2026-09-20"] = CompactEntry(covers="2026-09-20", rows=0, bytes=0, state=state_)
    an_index(root, VISUALS, Period.DAILY, [held[day] for day in sorted(held)])
    an_index(root, VISUALS, Period.MONTHLY, [])
    an_index(root, VISUALS, Period.YEARLY, [])
    late = filed(root, a_pass("2026-09-20", run="2", before=222))

    outcome = compact(root, FAILED_WAKE, wake=wake)

    assert outcome.stopped_because is StopReason.EXHAUSTED, outcome.resume_from
    repacked = daily_entries(root)["2026-09-20"]
    assert (repacked.state, repacked.rows) == (EntryState.PACKED, 1)
    found = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-20")
    assert found is not None
    assert ledger.load([found], model=VisualPruneRow) == [a_pass("2026-09-20", run="2", before=222)]
    assert not late.is_file()
    assert mark(root, Period.DAILY) == "2026-10-02"


def test_a_new_day_whose_file_no_entry_names_is_adopted_not_written_over(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An index restored from an older commit lost the day; its file is the day's record."""
    root = tmp_path / "checkout"
    a_marked_ledger(root, "2026-09-28")
    adopted = a_packed_day(root, "2026-09-29")

    with caplog.at_level(logging.WARNING):
        compact(root, FAILED_WAKE)

    assert daily_entries(root)["2026-09-29"] == adopted
    assert recovered(caplog, "2026-09-29") == [f"note={RecoveryNote.INDEX_REBUILT}"]
    assert mark(root, Period.DAILY) == "2026-10-02"


def test_a_ledger_with_an_index_and_no_watermark_resumes_where_its_index_ends(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for a ledger with no watermark file: its index alone says where to resume.

    The daily index names days to 16 September, so the pass takes the eight days
    after it. Nothing the index names is taken again: a lost day stays lost, and
    a packed day's file is not rewritten.
    """
    root = tmp_path / "checkout"
    held = {day: quiet(day) for day in days(FIRST_DAY, "2026-09-16")}
    held["2026-09-13"] = CompactEntry(covers="2026-09-13", rows=0, bytes=0, state=EntryState.LOST)
    held["2026-09-14"] = a_packed_day(root, "2026-09-14")
    an_index(root, VISUALS, Period.DAILY, [held[day] for day in sorted(held)])
    an_index(root, VISUALS, Period.MONTHLY, [])
    an_index(root, VISUALS, Period.YEARLY, [])
    packed = ledger.compact_file(state(root), VISUALS, Period.DAILY, "2026-09-14")
    assert packed is not None
    before = packed.read_bytes()

    with caplog.at_level(logging.INFO):
        outcome = compact(root, FAILED_WAKE)

    assert chosen_on(caplog)["days"] == {
        "start": "mark",
        "first": "2026-09-17",
        "last": "2026-09-24",
        "stopped_because": "ceiling",
        "resume_from": "2026-09-25",
    }
    entries = daily_entries(root)
    assert all(entries[day] == held[day] for day in held)
    assert packed.read_bytes() == before
    assert packed.relative_to(root).as_posix() not in outcome.written
    assert (outcome.stopped_because, outcome.resume_from) == (StopReason.CEILING, "2026-09-25")
    assert mark(root, Period.DAILY) == "2026-09-24"