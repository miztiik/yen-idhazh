"""Which host-fingerprint months does no published machine shard reach any more?

A row here is one job's silicon on one run - the machine the platform handed us
and what its model server counted - and every job of every run writes one, so
the tree grows every run and nothing else bounds it (Guardrail #12). A month
past the window is deleted whole rather than folded: a total over a month that
far back names no machine, and the month that matters is already published
under `frontend/public/machine/`. The ledger files by day and the window counts
months, so a month's day files go together, oldest month first.
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

    which = LedgerName.HOST_FINGERPRINT
    first_month = retention_files.first_kept_month(context.policy.window, context.today)
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, which))
    return retention_files.take_files(
        context,
        retention_files.whole_months_before(tree, first_month),
        collection=ledger.tree_relpath(which),
        first_kept=retention_files.first_day_of(first_month),
        after_delete=day_partition.drop_empty_day_dirs,
    )
