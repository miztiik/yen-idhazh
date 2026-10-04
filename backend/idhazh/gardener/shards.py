"""Which shard runs which gardener task at a wake, split the way the plan job splits it?

The plan job cannot import this: it runs `backend/utilities/gardener_shards.py`
with nothing of ours installed. This is the typed twin, read through the
validated declarations, and a test holds the two to one payload for one config.

**The split is round-robin over sorted names.** Every task the matrix runs -
every active one whose kind is not `history`, which runs in a job of its own -
is sorted by name and dealt to shard `position % shard_count`, where
`shard_count` is the smaller of `shards` and the number of tasks. So the same
declarations always give the same shards, no shard is ever empty, and every
task sits in exactly one. How much work a task holds is not read here: one
owned folder can hold one file or ten thousand, so counting folders would
balance nothing.

**The plan names tasks and no folders.** A shard checks out only its code and
config, and lists the files under the folders its tasks own or read from the
commit, so the plan job has nothing to say about folders.
"""

from __future__ import annotations

import json

from idhazh.config import GardenerSettings
from idhazh.contracts.gardener_plan import GardenerPlan, Matrix, MatrixLeg, ShardPlan
from idhazh.contracts.knobs.gardener import TaskKind, TaskLifecycleStatus, TaskPolicy


def runs_in_the_matrix(policy: TaskPolicy) -> bool:
    """Whether a wake's matrix runs this task: active, and not the history task."""
    return policy.lifecycle_status is TaskLifecycleStatus.ACTIVE and policy.kind != TaskKind.HISTORY


def plan(settings: GardenerSettings) -> GardenerPlan:
    """One wake's shards, and the matrix that runs them."""
    names = sorted(name for name, policy in settings.tasks.items() if runs_in_the_matrix(policy))
    count = min(settings.config.shards, len(names))
    dealt: list[list[str]] = [[] for _ in range(count)]
    for position, name in enumerate(names):
        dealt[position % count].append(name)
    shards = tuple(
        ShardPlan(index=index, task_names=tuple(held)) for index, held in enumerate(dealt)
    )
    return GardenerPlan(
        any_active_task=bool(shards),
        shard_count=count,
        shards=shards,
        matrix=Matrix(
            include=tuple(MatrixLeg(shard=s.index, task_names=s.task_names) for s in shards)
        ),
    )


def payload(planned: GardenerPlan) -> str:
    """The plan as the one line a workflow reads: compact, keys sorted, ASCII."""
    return json.dumps(planned.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)


def fullest(planned: GardenerPlan) -> ShardPlan | None:
    """The shard with the most tasks, the lowest index among equals. None on an empty wake."""
    if not planned.shards:
        return None
    return max(planned.shards, key=lambda shard: (len(shard.task_names), -shard.index))
