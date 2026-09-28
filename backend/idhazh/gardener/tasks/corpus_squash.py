"""What does the corpus squash do that needs no git? It records the day the squash ran.

The squash itself - the boundary, the new root, the replay and the push - is git,
and `backend/utilities/corpus_history.py` runs it, because nothing under
`backend/idhazh/` may start a process (`backend/tests/test_canaries.py`). What is
left for this module is the one piece of state that turns a force-push a day into
one a cadence: `last_run` in `corpus/corpus.meta.json`, written through its
contract. That program binds this module through the registry, as a shard binds
its tasks, and calls `run` after the replay and before the push.

`idhazh.corpus` is imported inside `run` because importing it loads an HTTP
client, and discovery imports every task module in every shard.
"""

from __future__ import annotations

from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.HISTORY


def run(context: TaskContext) -> Pass:
    """Write the wake's day into `last_run`. A dry run names the file and writes nothing."""
    from idhazh import corpus

    meta = f"{corpus.CORPUS_ROOT_RELPATH}/{corpus.META_FILENAME}"
    if not context.policy.dry_run:
        corpus.record_run(
            context.repo_root / corpus.CORPUS_ROOT_RELPATH, date=context.today.isoformat()
        )
    return Pass(
        collection=corpus.CORPUS_ROOT_RELPATH,
        since=None,
        until=None,
        ceiling=context.policy.max_deletes_per_run,
        dry_run=context.policy.dry_run,
        seen=0,
        selected=0,
        taken=(),
        written=(meta,),
        bytes_freed=0,
        stopped_because=StopReason.EXHAUSTED,
        resume_from=None,
    )
