"""What does a task do when its own code is wrong? It raises, before any member.

Its message quotes a row the way fetched text could reach an exception, so a
test can show that no line, summary or command a shard prints repeats it.
"""

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    raise KeyError(
        f"no member of {context.policy.owns} carries created_at; one row read "
        "'Breaking: click https://example.invalid/now'"
    )
