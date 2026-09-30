"""Which span-rollup months does nothing read any more, and whose closed days does it fold?

A row here is one span's total on one shard of one run, and every work shard of
every run files its own, so a day holds one file per shard until the day is
closed and folded into one `settled.csv` (`closed_day_fold`). That fold is this
task's only live action: its window is `forever`, because nobody has yet said
how long these rows are wanted, and a window that keeps every month takes
nothing. A month past a window, once one is declared, goes whole: the ledger
files by day and the window counts months, so a month's day files go together,
oldest month first.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take every day file of every month older than the oldest month the window keeps."""
    from idhazh import day_partition, ledger
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import retention_files

    which = LedgerName.SPAN_ROLLUP
    first_month = retention_files.first_kept_month(context.policy.window, context.today)
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, which))
    return retention_files.take_files(
        context,
        retention_files.whole_months_before(context.listing, tree, first_month),
        collection=ledger.tree_relpath(which),
        first_kept=retention_files.first_day_of(first_month),
        after_delete=day_partition.drop_empty_day_dirs,
    )
