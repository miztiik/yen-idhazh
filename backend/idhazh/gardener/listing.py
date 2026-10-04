"""What does an operator read when they ask the gardener what it would do?

Two listings, each a list of lines and nothing else: every declared task, and a
wake's shards. Both read validated settings and print; neither runs a task.
"""

from __future__ import annotations

from idhazh.config import GardenerSettings
from idhazh.contracts.gardener_plan import GardenerPlan
from idhazh.contracts.knobs.gardener import ForeverWindow, TaskPolicy, Window
from idhazh.gardener import shards


def _window(window: Window) -> str:
    if isinstance(window, ForeverWindow):
        return "forever"
    return f"{window.value} {window.unit}"


def _owns(policy: TaskPolicy) -> str:
    return ", ".join(policy.owns) or "no folder"


def tasks(settings: GardenerSettings) -> list[str]:
    """One line a task: its status, its kind, how long it keeps, what it owns and what it reads."""
    if not settings.tasks:
        return ["no task is declared: config/gardener/ holds no declaration"]
    return [
        f"{name}: {policy.lifecycle_status.value} {policy.kind}, keeps "
        f"{_window(policy.window)}, {'reports only' if policy.dry_run else 'deletes'}, "
        f"owns {_owns(policy)}"
        + (f", reads {', '.join(policy.reads)}" if policy.reads else "")
        for name, policy in settings.tasks.items()
    ]


def plan(planned: GardenerPlan) -> list[str]:
    """One line a shard - the tasks it runs - and the fullest shard."""
    fullest = shards.fullest(planned)
    if fullest is None:
        return ["this wake runs no shard: no active task is one the matrix runs"]
    lines = [f"{planned.shard_count} shards"]
    lines += [
        f"  shard {shard.index}: {', '.join(shard.task_names)}" for shard in planned.shards
    ]
    lines.append(f"fullest: shard {fullest.index}, with {len(fullest.task_names)} tasks")
    return lines
