"""Which counterfactual score files does no tuning read open again?

The lens tuning reads this ledger back over `lens_weights.window_days`, through
`day_partition.days_in_window`: the anchor day and that many days before it. A
file dated before the oldest day that names answers no question, so this task
takes it, one writer's file at a time, and the empty folders it leaves go with
it. `config.load_gardener` refuses a window shorter than the knob the tuning
reads.

A day dated after the wake is newer than the window and stays, the same
property the seen task holds.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take every counterfactual file dated before the oldest day the window keeps."""
    from datetime import date

    from idhazh import day_partition, day_shards, ledger
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import named_trees, retention_files

    today = context.today.isoformat()
    first_kept = retention_files.first_kept_day(
        context.policy.window,
        context.today,
        days_back=lambda days: date.fromisoformat(min(day_partition.days_in_window(today, days))),
    )
    which = LedgerName.COUNTERFACTUAL_SCORES
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, which))
    boundary = first_kept.isoformat() if first_kept is not None else ""
    files = (
        named_trees.shard_files(context.listing, tree) if tree is not None and boundary else ()
    )
    aged = (
        retention_files.Aged(path=path, day=day_shards.date_of(path))
        for path in files
        if day_shards.date_of(path) < boundary
    )
    return retention_files.take_files(
        context,
        aged,
        collection=ledger.tree_relpath(which),
        first_kept=first_kept,
        after_delete=day_partition.drop_empty_day_dirs,
    )
