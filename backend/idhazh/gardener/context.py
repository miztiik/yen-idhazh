"""What does a gardener task receive when the runner calls it?

Everything a task may know about the run it is part of, and nothing it could
use to reach outside what it owns. The policy is its own validated declaration;
the rest is the run's identity, the two roots it works under, the folders the
runner has already decided it may walk, and the listing of the files under the
folders it owns or reads, which is where a task learns what is there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import TaskPolicy
from idhazh.gardener.file_listing import FileListing


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
    #: The commit this checkout is at. A file the task writes through the ledger
    #: door names it, so the file can be traced to the code that wrote it.
    git_sha: str
    #: The repository-relative folders this task walks, in the order it walks
    #: them, every one present in the checkout. The runner works them out before
    #: the task runs - a declared folder the commit does not hold yet is left out,
    #: and a complement task gets the folders nothing else claims - so a task
    #: never lists `state/` to decide for itself what is its own.
    owned_folders: tuple[str, ...]
    #: Every file under the folders this task owns or reads, and what each
    #: weighs. A task lists its members from here and never from the disk, and
    #: fetches a folder through it before it opens a file inside.
    listing: FileListing
    #: The inclusive period range this task may read on this run: the range a
    #: person named, the first and last month a ledger migration packs, or else
    #: the scheduled window the runner built, or None. A compaction has no
    #: scheduled window, because each of its steps chooses its own periods, so
    #: for a compaction this is a named range, which only limits that choice,
    #: or None on a scheduled wake.
    period_range: tuple[str, str] | None = None
