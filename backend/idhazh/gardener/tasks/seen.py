"""Which seen day files will the planner never open again?

The planner reads first sightings back over `collect.seen_window_days`, through
`day_partition.days_in_window`: the anchor day and that many days before it. A
day file older than the oldest day that names is invisible to the planner, so
this task takes it, and the empty folders it leaves go with it.
`config.load_gardener` refuses a window shorter than the knob the planner reads,
so this never takes a day the planner still opens.

A day dated after the wake is newer than the window and stays: a run handed an
older `--date` must not delete the day the next one appends to.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take every seen day file older than the oldest day the window keeps, oldest first."""
    from datetime import date

    from idhazh import day_partition, ledger
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import named_trees, retention_files

    today = context.today.isoformat()
    first_kept = retention_files.first_kept_day(
        context.policy.window,
        context.today,
        days_back=lambda days: date.fromisoformat(min(day_partition.days_in_window(today, days))),
    )
    tree = retention_files.owned_tree(context, ledger.tree_root(context.state_dir, LedgerName.SEEN))
    boundary = first_kept.isoformat() if first_kept is not None else ""
    aged = (
        retention_files.Aged(path=day, day=day_partition.date_of(day))
        for day in (
            named_trees.day_files(context.listing, tree) if tree is not None and boundary else ()
        )
        if day_partition.date_of(day) < boundary
    )
    return retention_files.take_files(
        context,
        aged,
        collection=ledger.tree_relpath(LedgerName.SEEN),
        first_kept=first_kept,
        after_delete=day_partition.drop_empty_day_dirs,
    )
