"""What does a task do when the service it lists from is down? It raises, before any member."""

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    raise ConnectionError(f"the listing service for {context.policy.owns} did not answer")
