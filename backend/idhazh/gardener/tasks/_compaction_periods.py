"""Which periods each compaction step may take on this wake.

Each step chooses from the ledger's own marks, the wake's UTC day and its
declaration, never from folders a planner named for another step, so no step
is offered a period from before its ledger began. The choice reads no file:
it is made before any step runs, logged once, and handed to each step as its
parameters (`PeriodsChosen`).

**The month step takes the months after its mark.** It starts at the month
after the monthly mark; with no mark, at the oldest month an index names; with
nothing indexed, nowhere. It takes consecutive months, each at least
`daily_keep_days` whole days past its end and each one whose last day the daily
mark has reached, at most `max_periods_per_run` of them. A month in that span
that a raw day still waits in is held when the step comes to it, once its raw
folder is named; whether a day waits is a file, not a mark.

**An operator range limits the choice and never makes a step skip a period.**
A range that ends before the step's first month leaves nothing to take. A range
that starts after it, while that first month is ready to close, is refused at
that month, so the person widens the range rather than finding the month left
open. Whether that month is ready is read from the calendar and the marks
alone, so the refusal reads nothing outside the range.

Every rule counts whole days after a period's own end, from 00:00 UTC on the
wake's day, so every wake of one UTC day chooses the same (CLAUDE.md section 2).
"""

from __future__ import annotations

from datetime import datetime

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.gardener_events import PeriodsChosen, StartReason, StepChoice
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.gardener import schedule
from idhazh.gardener.tasks._compact_tree import CompactTree
from idhazh.gardener.tasks._monthly_period import days_of, shift


def choose(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
) -> PeriodsChosen:
    """Every step's periods for this wake, from the marks `tree` read and the declaration."""
    return PeriodsChosen(
        ledger=tree.ledger,
        daily_mark=tree.daily_through,
        monthly_mark=tree.monthly_through,
        yearly_mark=tree.yearly_through,
        newest_closable_month=schedule.newest_eligible_month(
            now=now, after_days=policy.daily_keep_days
        ),
        cap=policy.max_periods_per_run,
        operator_range=operator_range,
        month_deletes_dry_run=policy.month_deletes_dry_run,
        months=_months(tree, policy, now=now, operator_range=operator_range),
    )


def _reached(daily_mark: str | None) -> str | None:
    """The newest month whose last day the daily mark has reached, or None with no mark."""
    if daily_mark is None:
        return None
    month = daily_mark[:7]
    return month if daily_mark == days_of(month)[-1] else shift(month, -1)


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
    elif tree.monthly:
        start, why = min(tree.monthly), StartReason.OLDEST_INDEXED
    elif tree.daily:
        start, why = min(tree.daily)[:7], StartReason.OLDEST_INDEXED
    else:
        return StepChoice(start=StartReason.NONE)
    reached = _reached(tree.daily_through)
    newest = schedule.newest_eligible_month(now=now, after_days=policy.daily_keep_days)
    ready = None if reached is None else min(reached, newest)
    end = ready
    if operator_range is not None:
        first, last = operator_range
        if start > last:
            return StepChoice(start=StartReason.OPERATOR_RANGE)
        if start < first:
            if ready is not None and start <= ready:
                return StepChoice(
                    start=StartReason.OPERATOR_RANGE,
                    stopped_because=StopReason.FAILED,
                    resume_from=start,
                )
            return StepChoice(start=StartReason.OPERATOR_RANGE)
        end = None if ready is None else min(ready, last)
    if end is None or end < start:
        return StepChoice(start=why)
    capped = shift(start, policy.max_periods_per_run - 1)
    if capped < end:
        return StepChoice(
            start=why,
            first=start,
            last=capped,
            stopped_because=StopReason.CEILING,
            resume_from=shift(capped, 1),
        )
    return StepChoice(start=why, first=start, last=end)
