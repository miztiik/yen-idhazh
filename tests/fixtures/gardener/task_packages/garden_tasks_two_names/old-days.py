"""One of two modules whose stems both name the task `old-days`: this one with a hyphen."""

# The hyphen in this file's name is the defect the test needs, so the name rule is waived.
# ruff: noqa: N999

from fixture_day_files import day_files

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    return day_files(context, context.policy.owns or ())
