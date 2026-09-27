"""What does a gardener task receive when the runner calls it?

Everything a task may know about the run it is part of, and nothing it could
use to reach outside what it owns. The policy is its own validated declaration;
the rest is the run's identity and the two roots it works under.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import TaskPolicy


@dataclass(frozen=True, slots=True)
class TaskContext:
    """One task's view of the wake that runs it."""

    #: The state root the task reads and writes under.
    state_dir: Path
    #: The checkout the task's `owns` folders are relative to.
    repo_root: Path
    #: The UTC day of the wake. A task measures age from it, never from a clock.
    today: date
    #: The task's own declaration, validated with every other one.
    policy: TaskPolicy
    run_id: str
    attempt: int
    job: ServerJob
    shard: int
