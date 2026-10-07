"""Which periods each compaction step may take on this wake.

Each step chooses from the ledger's own marks, the wake's UTC day and its
declaration, never from folders a planner named for another step, so no step
is offered a period from before its ledger began. Each mark is worked out from
the ledger's indexes (`ledger_marks.work_out_marks`), so a step has no mark only
when no index names a period of its kind or a coarser one. The choice opens no
file and lists nothing: the pass first names the months a first day run looks
back over (`first_run_months`), then the choice is made once, before any step
runs, logged, and handed to each step as its parameters (`PeriodsChosen`).

**The drop step takes the oldest months past the keep line**, the oldest month
the monthly window keeps. It starts at the oldest monthly entry, because the
monthly index is its record of what is left to drop: a month it drops leaves
the index, so no later pass looks at it again. It takes the entries older than
the line, oldest first, at most `max_periods_per_run` of them, and the span
counts entries rather than calendar months.

**The year step takes the years after its mark**, and only where the
declaration sets `monthly_keep_days`. It starts at the year after the yearly
mark; with no mark, at the year that holds the oldest monthly entry; with no
monthly entry either, nowhere. It takes consecutive years, each at least
`monthly_keep_days` whole days past its end and each whose December the
monthly mark is strictly past, so its next January is closed too, at most
`max_periods_per_run` of them.

**The month step takes the months after its mark.** It starts at the month
after the monthly mark; with no mark, at the oldest month the daily index
names; with nothing indexed, nowhere. It takes consecutive months, each at least
`daily_keep_days` whole days past its end and each one whose last day the daily
mark has reached, at most `max_periods_per_run` of them. A month in that span
that a raw day still waits in is held when the step comes to it, once its raw
folder is named; whether a day waits is a file, not a mark. The drop step
taking months out of the index moves no mark, so the month step never starts
at a month the drop step took.

**The day step takes the days after its mark.** It starts at the day after the
daily mark and takes days up to the earlier of the mark plus
`max_periods_per_run` and the newest due day, the newest at least
`compact_after_days` whole days past its end. With no mark, a first run starts
at the oldest raw day in the months it looks back over: the operator range's,
or the month that holds the newest due day and the `lookback` months before it.
While the
monthly window's deletes are live a first run starts no earlier than the keep
line, the oldest month the window keeps, and with no day to start at it takes
nothing. The span is the most the step takes: the step also names the raw
folders of the packed days a GitHub re-run may still write into, from
`GITHUB_RERUN_DAYS` days before the wake to the mark, and each day it takes
again counts against the same cap.

**A span is the most a step takes, never a promise.** Sizes are not known here,
because the choice lists nothing; once a step has named its periods it takes
only those whose files fit what is left of the shard's download budget, and
stops at the first that does not (`CompactTree.fit_to_budget`).

**An operator range limits the choice and never makes a step skip a period.**
A range that ends before the step's first period leaves nothing to take. A
range that starts after it, while that first period is ready, is refused at
that period, so the person widens the range rather than finding it left open.
The refusal defers the pass with the fault `range-starts-late`: a person's
range, not a defect, so the job stays green.
Whether that period is ready is read from the calendar and the marks alone, so
the refusal reads nothing outside the range. The year step counts only the
whole years a range holds, January to December, so it reads no month outside
it; a range that holds no whole year takes no year and refuses none. The drop
step has no mark a range could carry past a month: a month the range leaves
out stays in the index for a later pass, so its range refuses nothing.

Every rule counts whole days after a period's own end, from 00:00 UTC on the
wake's day, so every wake of one UTC day chooses the same (CLAUDE.md section 2).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from idhazh import month_partition
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.gardener_events import PeriodsChosen, StartReason, StepChoice
from idhazh.contracts.knobs.gardener import GITHUB_RERUN_DAYS, CompactionPolicy
from idhazh.gardener import schedule
from idhazh.gardener.tasks._compact_tree import CompactTree
from idhazh.gardener.tasks._monthly_period import days_of, first_kept_month, shift


def choose(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
) -> PeriodsChosen:
    """Every step's periods for this wake, from the marks `tree` read and the declaration."""
    keep_line = first_kept_month(
        now=now, daily_keep_days=policy.daily_keep_days, window=policy.monthly_window
    )
    return PeriodsChosen(
        ledger=tree.ledger,
        daily_mark=tree.daily_through,
        monthly_mark=tree.monthly_through,
        yearly_mark=tree.yearly_through,
        newest_eligible_day=newest_due(policy, now=now),
        newest_closable_month=schedule.newest_eligible_month(
            now=now, after_days=policy.daily_keep_days
        ),
        keep_line=keep_line,
        newest_packable_year=None
        if policy.monthly_keep_days is None
        else schedule.newest_eligible_year(now=now, after_days=policy.monthly_keep_days),
        cap=policy.max_periods_per_run,
        operator_range=operator_range,
        month_deletes_dry_run=policy.month_deletes_dry_run,
        drops=_drops(
            tree, keep_line=keep_line, cap=policy.max_periods_per_run, operator_range=operator_range
        ),
        years=_years(tree, policy, now=now, operator_range=operator_range),
        months=_months(tree, policy, now=now, operator_range=operator_range),
        days=_days(tree, policy, now=now, keep_line=keep_line, operator_range=operator_range),
        rerun_span=_rerun_span(tree, now=now, operator_range=operator_range),
    )


def first_run_months(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
) -> list[str]:
    """The months a day step with no mark looks back over for its oldest raw day; none with one.

    The operator range's months, or the month that holds the newest due day and
    the `lookback` months before it. The pass names their raw folders before it
    chooses. The keep line is the choice's to apply, so a raw day behind the
    line is still seen, and the choice can say the line moved the start.
    """
    if tree.daily_through is not None:
        return []
    if operator_range is not None:
        return month_partition.months_between(*operator_range)
    newest = newest_due(policy, now=now)[:7]
    return month_partition.months_between(shift(newest, -policy.lookback_periods), newest)


def newest_due(policy: CompactionPolicy, *, now: datetime) -> str:
    """The newest UTC day at least `compact_after_days` whole days past its end, at `now`."""
    return schedule.newest_eligible(now=now, after_days=policy.compact_after_days).isoformat()


def _day_after(day: str, count: int) -> str:
    """The UTC day `count` days after this one."""
    return (date.fromisoformat(day) + timedelta(days=count)).isoformat()


def _year_after(year: str, count: int) -> str:
    """The UTC year `count` years after this one, or before it when negative."""
    return f"{int(year) + count:04d}"


def _whole_years(first: str, last: str) -> tuple[str, str]:
    """The first and last UTC year a range of months holds whole, January to December.

    A range that holds no whole year gives a pair that runs backward.
    """
    start = first[:4] if first.endswith("-01") else _year_after(first[:4], 1)
    end = last[:4] if last.endswith("-12") else _year_after(last[:4], -1)
    return start, end


def _reached(daily_mark: str | None) -> str | None:
    """The newest month whose last day the daily mark has reached, or None with no mark."""
    if daily_mark is None:
        return None
    month = daily_mark[:7]
    return month if daily_mark == days_of(month)[-1] else shift(month, -1)


def _span(
    start: str,
    why: StartReason,
    ready: str | None,
    *,
    bounds: tuple[str, str] | None,
    cap: int,
    after: Callable[[str, int], str],
) -> StepChoice:
    """The periods one step may take from `start`: ready, inside the operator's bounds, to the cap.

    `ready` is the newest period the step may take on this wake, or None when it
    may take none. `bounds` are the operator range's first and last period at
    the step's grain, and `after` counts periods of that grain forward. A pair
    that runs backward holds no whole period, so the step takes nothing and
    refuses nothing.
    """
    end = ready
    if bounds is not None:
        first, last = bounds
        if first > last or start > last:
            return StepChoice(start=StartReason.OPERATOR_RANGE)
        if start < first:
            if ready is not None and start <= ready:
                return StepChoice(
                    start=StartReason.OPERATOR_RANGE,
                    stopped_because=StopReason.DEFERRED,
                    resume_from=start,
                )
            return StepChoice(start=StartReason.OPERATOR_RANGE)
        end = None if ready is None else min(ready, last)
    if end is None or end < start:
        return StepChoice(start=why)
    capped = after(start, cap - 1)
    if capped < end:
        return StepChoice(
            start=why,
            first=start,
            last=capped,
            stopped_because=StopReason.CEILING,
            resume_from=after(capped, 1),
        )
    return StepChoice(start=why, first=start, last=end)


def _drops(
    tree: CompactTree,
    *,
    keep_line: str | None,
    cap: int,
    operator_range: tuple[str, str] | None,
) -> StepChoice | None:
    """The month entries the drop step may take: older than the keep line, in range, to the cap.

    None when the monthly window keeps every month. The start is the oldest
    entry past the line, or the oldest inside the operator range when the range
    moved it, and the next entry past the cap is where the next wake starts.
    """
    if keep_line is None:
        return None
    if not tree.monthly:
        return StepChoice(start=StartReason.NONE)
    past = sorted(month for month in tree.monthly if month < keep_line)
    ranged = (
        past
        if operator_range is None
        else [month for month in past if operator_range[0] <= month <= operator_range[1]]
    )
    why = StartReason.OLDEST_INDEXED if ranged[:1] == past[:1] else StartReason.OPERATOR_RANGE
    if not ranged:
        return StepChoice(start=why)
    taken = ranged[:cap]
    if len(ranged) > cap:
        return StepChoice(
            start=why,
            first=taken[0],
            last=taken[-1],
            stopped_because=StopReason.CEILING,
            resume_from=ranged[cap],
        )
    return StepChoice(start=why, first=taken[0], last=taken[-1])


def _years(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
) -> StepChoice | None:
    """The years the year step may pack: from its mark, ready, in range, to the cap.

    None when the declaration packs no year. A year is ready once it is at least
    `monthly_keep_days` whole days past its end and the monthly mark is strictly
    past its December.
    """
    if policy.monthly_keep_days is None:
        return None
    if tree.yearly_through is not None:
        start, why = _year_after(tree.yearly_through, 1), StartReason.MARK
    elif tree.monthly:
        start, why = min(tree.monthly)[:4], StartReason.OLDEST_INDEXED
    else:
        return StepChoice(start=StartReason.NONE)
    newest = schedule.newest_eligible_year(now=now, after_days=policy.monthly_keep_days)
    past = None if tree.monthly_through is None else _year_after(tree.monthly_through[:4], -1)
    return _span(
        start,
        why,
        None if past is None else min(past, newest),
        bounds=None if operator_range is None else _whole_years(*operator_range),
        cap=policy.max_periods_per_run,
        after=_year_after,
    )


def _months(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
) -> StepChoice:
    """The months the month step may close: from its mark, ready, in range, to the cap."""
    if tree.monthly_through is not None:
        start, why = shift(tree.monthly_through, 1), StartReason.MARK
    elif tree.daily:
        start, why = min(tree.daily)[:7], StartReason.OLDEST_INDEXED
    else:
        return StepChoice(start=StartReason.NONE)
    reached = _reached(tree.daily_through)
    newest = schedule.newest_eligible_month(now=now, after_days=policy.daily_keep_days)
    ready = None if reached is None else min(reached, newest)
    return _span(
        start, why, ready, bounds=operator_range, cap=policy.max_periods_per_run, after=shift
    )


def _days(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    keep_line: str | None,
    operator_range: tuple[str, str] | None,
) -> StepChoice:
    """The new days the day step may pack: from its mark, or where a first run starts.

    A first run starts at the oldest raw day in the months it looks back over.
    """
    if tree.daily_through is not None:
        start, why = _day_after(tree.daily_through, 1), StartReason.MARK
    else:
        looked = set(first_run_months(tree, policy, now=now, operator_range=operator_range))
        found = sorted(day for day in tree.raw_days if day[:7] in looked)
        if not found:
            return StepChoice(start=StartReason.NONE)
        start, why = found[0], StartReason.OLDEST_RAW_DAY
        if keep_line is not None and not policy.month_deletes_dry_run and start[:7] < keep_line:
            kept = [day for day in found if day[:7] >= keep_line]
            if not kept:
                return StepChoice(start=StartReason.KEEP_LINE)
            start, why = kept[0], StartReason.KEEP_LINE
    return _span(
        start,
        why,
        newest_due(policy, now=now),
        bounds=None if operator_range is None else month_partition.day_bounds(*operator_range),
        cap=policy.max_periods_per_run,
        after=_day_after,
    )


def _rerun_span(
    tree: CompactTree, *, now: datetime, operator_range: tuple[str, str] | None
) -> tuple[str, str] | None:
    """The packed days whose raw folders the day step names, because a re-run may write there.

    GitHub lets a run be re-run for `GITHUB_RERUN_DAYS` days, and a re-run
    writes into the day its run first wrote, so the span runs from that many
    days before the wake's day to the daily mark.
    """
    if tree.daily_through is None:
        return None
    first = (now.astimezone(UTC).date() - timedelta(days=GITHUB_RERUN_DAYS)).isoformat()
    last = tree.daily_through
    if operator_range is not None:
        lowest, highest = month_partition.day_bounds(*operator_range)
        first, last = max(first, lowest), min(last, highest)
    return (first, last) if first <= last else None
