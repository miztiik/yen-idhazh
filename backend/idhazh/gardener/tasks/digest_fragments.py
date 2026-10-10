"""Which per-run blocks of a published day can no run of that day need any more?

A block is one run's half of a published day, and the day is assembled out of
every block of its date. While the date can still gain a run the blocks are
live; once the day is past the window the day itself keeps, they are a second
full copy of every story with no reader and no writer. So a day's blocks go once
it is older than the window, one file at a time with the folders it leaves
empty. The published day is never touched here or anywhere.

The window is counted in whole days back from the wake, the day before the
first kept day being the last one taken, as the visual-prune task counts the
thirty-day months `retention.image_months` names. `config.load_gardener` refuses
a window that would include today, so this never selects a day a concurrent
assemble is still writing into.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION
OWNED_LEDGERS = (LedgerName.DIGEST_FRAGMENTS,)


def run(context: TaskContext) -> Pass:
    """Take every block of every day before the first day the window keeps, oldest day first."""
    from datetime import date, timedelta

    from idhazh import day_partition, ledger
    from idhazh.gardener import named_trees, retention_files

    first_kept = retention_files.first_kept_day(
        context.policy.window,
        context.today,
        days_back=lambda days: context.today - timedelta(days=days),
    )
    which = LedgerName.DIGEST_FRAGMENTS
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, which))
    candidate_days = (
        day_partition.days_before(first_kept, context.policy.lookback_periods + 1)
        if context.period_range is None and first_kept is not None
        else []
    )
    if context.period_range is not None:
        start, end = context.period_range
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if first > last:
            raise ValueError("digest-fragments backlog range starts after it ends")
        if first_kept is None or last >= first_kept:
            raise ValueError(
                "digest-fragments backlog range must end before the kept-day boundary"
            )
        candidate_days = [
            first + timedelta(days=offset) for offset in range((last - first).days + 1)
        ]
    aged = [
        retention_files.Aged(path=path, day=day.published.isoformat())
        for day in (
            named_trees.dated_days(
                context.listing,
                tree,
                candidate_days,
            )
            if tree is not None
            else ()
        )
        for path in day.files
    ]
    return retention_files.take_files(
        context,
        aged,
        collection=ledger.tree_relpath(which),
        first_kept=first_kept,
        after_delete=day_partition.drop_empty_day_dirs,
    )
