"""What does a history task report when there is no history to rewrite yet? An exhausted pass."""

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.HISTORY


def run(context: TaskContext) -> Pass:
    return Pass(
        collection=(context.policy.owns or ("history",))[0],
        since=None,
        until=None,
        ceiling=context.policy.max_deletes_per_run,
        dry_run=context.policy.dry_run,
        seen=0,
        selected=0,
        taken=(),
        written=(),
        bytes_freed=0,
        stopped_because=StopReason.EXHAUSTED,
        resume_from=None,
    )
