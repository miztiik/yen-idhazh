"""How does a test run one shipped retention task over a tree of its own?

Through the task's own module and the committed declaration, with only the
knobs a test names changed - `dry_run`, the window, the ceiling - so a test
exercises the task as it ships. The folders the task walks are worked out by
the runner's own `folders_of`, from the tree the test built.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Final

from conftest import CONFIG_DIR
from pydantic import TypeAdapter

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import TaskPolicy
from idhazh.gardener import registry, runner
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.one_at_a_time import Pass

from .._garden import COMMITTED_DECLARATIONS, named_task_modules
from ._oracle_tree import REMOVALS, RUN_ID, TODAY

#: A commit the record names. No test here reads git.
GIT_SHA: Final = "0" * 40

_POLICY: Final[TypeAdapter[TaskPolicy]] = TypeAdapter(TaskPolicy)


def declared() -> dict[str, TaskPolicy]:
    """The named committed declarations the integration fixtures exercise."""
    folder = CONFIG_DIR / "gardener"
    return {
        path.stem: _POLICY.validate_json(path.read_text(encoding="utf-8"))
        for path in (folder / name for name in COMMITTED_DECLARATIONS)
    }


def committed_folders(root: Path, tasks: dict[str, TaskPolicy]) -> frozenset[str]:
    """What `git ls-tree` would list for this tree: each named folder, and every child of state."""
    state = root / ledger.STATE_DIRNAME
    children = (
        {child.relative_to(root).as_posix() for child in state.iterdir() if child.is_dir()}
        if state.is_dir()
        else set()
    )
    named = {
        folder
        for policy in tasks.values()
        for folder in (*(policy.owns or ()), *policy.reads)
        if (root / folder).is_dir()
    }
    return frozenset(children | named)


def context_for(
    name: str,
    root: Path,
    *,
    today: date = TODAY,
    period_range: tuple[str, str] | None = None,
    **changed: Any,
) -> TaskContext:
    """The context the runner would hand this task over `root`, with these knobs changed."""
    tasks = declared()
    policy = tasks[name]
    if changed:
        policy = _POLICY.validate_python({**policy.model_dump(mode="json"), **changed})
        tasks[name] = policy
    folders = runner.folders_of(name, tasks, root, committed_folders(root, tasks))
    return TaskContext(
        state_dir=root / ledger.STATE_DIRNAME,
        repo_root=root,
        today=today,
        policy=policy,
        run_id=RUN_ID,
        attempt=1,
        job=ServerJob.RUN_TASKS,
        shard=0,
        git_sha=GIT_SHA,
        owned_folders=folders.walk,
        listing=FileListing.from_disk(root, runner.listed_folders(policy, folders)),
        period_range=period_range,
    )


def run_task(
    name: str,
    root: Path,
    *,
    today: date = TODAY,
    period_range: tuple[str, str] | None = None,
    **changed: Any,
) -> Pass:
    """Run one shipped task, found the way the runner finds it."""
    policy = declared()[name]
    held = registry.bind(name, policy.kind, named_task_modules())
    return held.run(context_for(name, root, today=today, period_range=period_range, **changed))


def oracle() -> dict[str, Any]:
    """What each old pass removed and wrote over the oracle tree, recorded before it went."""
    recorded: dict[str, Any] = json.loads(REMOVALS.read_text(encoding="utf-8"))
    return recorded
