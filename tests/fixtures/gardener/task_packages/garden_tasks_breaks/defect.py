"""What does a task do when its own code is wrong? It raises, before any member."""

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    raise KeyError(f"no member of {context.policy.owns} carries created_at")
