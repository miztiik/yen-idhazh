"""Which days of the eval ledger's ID folder may go, and whose closed days does its task fold?

None may go. The index is what a run dedupes against, and an observation key
carries no date, so a dropped day would make every measurement in it new again.
The window is `forever`, and a window that keeps every month takes nothing. The
task's one live action is the fold of the index's closed days into one
`settled.csv` each (`closed_day_fold`). The eval rows themselves are the
`summary-quality-evals` compaction's, and it keeps every month too.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take every index day of every month older than the oldest month the window keeps."""
    from idhazh import day_partition, ledger
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import retention_files

    which = LedgerName.SUMMARY_QUALITY_EVALS_INDEX
    first_month = retention_files.first_kept_month(context.policy.window, context.today)
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, which))
    return retention_files.take_files(
        context,
        retention_files.whole_months_before(context.listing, tree, first_month),
        collection=ledger.tree_relpath(which),
        first_kept=retention_files.first_day_of(first_month),
        after_delete=day_partition.drop_empty_day_dirs,
    )
