"""What does a fixture compaction task write, so a shard has a file of its own to land?

It names the folder it owns and fetches it, the way a compaction names the
periods it reads as it runs and then fetches them, then writes one summary file
inside it, naming the day, and deletes nothing. That is the shape a compaction
has - it reads files and writes files - without any of a compaction's
arithmetic, which the runner does not look at.
"""

from dataclasses import replace

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.COMPACTION


def run(context: TaskContext) -> Pass:
    folder = (context.policy.owns or ())[0]
    context.listing.name([folder]).fetch([folder])
    written = f"{folder}/{context.today.isoformat()}.summary"
    if not context.policy.dry_run:
        target = context.repo_root / written
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"compacted on {context.today.isoformat()}\n", encoding="ascii")
    nothing = Pass(
        collection=folder,
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
    return replace(nothing, written=(written,))
