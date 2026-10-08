"""Which indexed UTC years expire on this wake, and which exact files they remove.

**The step says what it chose once, before it deletes anything**, as one
`ExpiredYearsChosen` event: the expired years this pass takes, or none. A range
a person names that would skip an older indexed year is refused at the oldest
indexed year (`CompactTree.refuse`), and the step takes nothing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from idhazh import ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.gardener_events import CompactionStep, ExpiredYearsChosen
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.gardener import event_log
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop
from idhazh.gardener.tasks._monthly_period import shift


def expires_at(year: str, months: int) -> datetime:
    """The UTC year-end instant plus exactly `months` calendar months."""
    month = shift(f"{int(year) + 1:04d}-01", months)
    return datetime.combine(date.fromisoformat(f"{month}-01"), time.min, tzinfo=UTC)


def drop(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
) -> tuple[Stop, ...]:
    """Delete at most the cap's indexed years, oldest first, and preserve their progress."""
    if not policy.yearly_prune_enable or policy.yearly_keep_months is None:
        return ()
    due = [
        year for year in sorted(tree.yearly) if now >= expires_at(year, policy.yearly_keep_months)
    ]
    if operator_range is not None:
        # Expiry is a prefix: skipping an older year would make the mark hide live rows.
        due = [
            year
            for year in due
            if operator_range[0] <= f"{year}-01" and f"{year}-12" <= operator_range[1]
        ]
        if due and any(year < due[0] for year in tree.yearly):
            return (tree.refuse(CompactionStep.EXPIRE_YEARS, min(tree.yearly)),)
    years = due[: policy.max_periods_per_run]
    paths = [
        ledger.compact_path(tree.state_dir, tree.ledger, Period.YEARLY, year, fmt=fmt)
        for year in years
        for fmt in Format
    ]
    tree.listing = tree.listing.name(paths)
    event_log.emit(ExpiredYearsChosen(ledger=tree.ledger, years=years))
    for year in years:
        for fmt in Format:
            path = ledger.compact_path(tree.state_dir, tree.ledger, Period.YEARLY, year, fmt=fmt)
            if tree.listing.holds(path):
                tree.delete(path)
        del tree.yearly[year]
        tree.expired_through = year
        tree.mark_index(Period.YEARLY)
    if years:
        tree.work_out_marks()
    return (Stop(StopReason.CEILING, due[len(years)]),) if len(due) > len(years) else ()
