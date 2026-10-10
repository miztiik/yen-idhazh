"""Which committed span traces are too old for anybody to open?

A trace is the file an operator opens to walk one recent run step by step, and
the lasting record of a run is the span rollup beside it, so a trace past its
window is deleted whole rather than folded - a fold would invent a total nobody
reads. A trace is kept while it is less than the window's days old, so the last
that-many days survive. A trace dated after the wake stays, and a file whose
path names no day is left alone.

Nothing drops the day folders here, because the pass this replaced never did.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION
OWNED_LEDGERS = (LedgerName.TRACES,)


def run(context: TaskContext) -> Pass:
    """Take every trace at least the window's days old, in path order."""
    from datetime import timedelta

    from idhazh import ledger, telemetry
    from idhazh.gardener import named_trees, retention_files

    first_kept = retention_files.first_kept_day(
        context.policy.window,
        context.today,
        days_back=lambda days: context.today - timedelta(days=days - 1),
    )
    tree = retention_files.owned_tree(
        context, ledger.tree_root(context.state_dir, LedgerName.TRACES)
    )

    def aged() -> list[retention_files.Aged]:
        if tree is None or first_kept is None:
            return []
        found: list[retention_files.Aged] = []
        for path in named_trees.files_named(context.listing, tree, ".jsonl"):
            published = telemetry.trace_date(path, tree)
            if published is not None and published < first_kept:
                found.append(retention_files.Aged(path=path, day=published.isoformat()))
        return found

    return retention_files.take_files(
        context,
        aged(),
        collection=ledger.tree_relpath(LedgerName.TRACES),
        first_kept=first_kept,
    )
