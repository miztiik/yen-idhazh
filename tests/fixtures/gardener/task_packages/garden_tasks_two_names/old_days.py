"""One of two modules whose stems both name the task `old-days`: this one with an underscore."""

from fixture_day_files import day_files

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    return day_files(context, context.policy.owns or ())
