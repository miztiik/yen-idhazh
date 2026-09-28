"""A module named for the task `old-days` that declares itself a compaction.

The declaration it would serve is a retention task, so binding the two would
hand a compaction module a declaration it cannot read.
"""

from fixture_day_files import day_files

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.COMPACTION


def run(context: TaskContext) -> Pass:
    return day_files(context, context.policy.owns or ())
