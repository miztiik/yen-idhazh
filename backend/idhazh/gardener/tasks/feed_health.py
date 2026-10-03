"""Which feed-health months does no quarantine and no console read reach any more?

A row here is one feed's result on one run. The quarantine reads a month back
and the console at most `console.max_window_days`, so nothing asks a month older
than the window for anything, and a total of what a feed did that long ago has
no reader - so a month past the window is deleted whole, never folded. The
ledger files by day and the window counts months, so a month's day files go
together or not at all, oldest month first, with the folders they leave empty.

`state/raw/feed-retirements/` is not in this tree and never a candidate: a
retirement is an address a server said was gone, with no age of its own.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take every day file of every month older than the oldest month the window keeps."""
    from idhazh import day_partition, ledger, month_partition
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import retention_files

    which = LedgerName.FEED_HEALTH
    first_month = retention_files.first_kept_month(context.policy.window, context.today)
    if context.period_range is not None:
        start, end = context.period_range
        requested = month_partition.months_between(start, end)
        if first_month is None or requested[-1] >= first_month:
            raise ValueError(
                f"backlog range {start} through {end} must end before kept-month "
                f"boundary {first_month}"
            )
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, which))
    return retention_files.take_files(
        context,
        retention_files.whole_months_before(context.listing, tree, first_month),
        collection=ledger.tree_relpath(which),
        first_kept=retention_files.first_day_of(first_month),
        after_delete=day_partition.drop_empty_day_dirs,
    )
