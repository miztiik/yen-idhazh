"""How does a test run one shipped retention task over a tree of its own?

Through the task's own module and the committed declaration, with only the
knobs a test names changed - `dry_run`, the window, the ceiling - so a test
exercises the task as it ships. Or through a declaration the test built whole,
with the first year a ledger can hold named beside it, so no committed knob of
the task can move what that test expects. The folders the task walks are
worked out by the runner's own `folders_of`, from the tree the test built. The
listing names those folders whole, or, for a test that asks for a wake, only
the paths the runner names for a scheduled wake: a retention task's window, or
a compaction's marks.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Final

from conftest import CONFIG_DIR, FIXTURES_DIR
from pydantic import TypeAdapter

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import GardenerConfig, TaskPolicy
from idhazh.gardener import registry, runner
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.period_inputs import paths_for_task, scheduled_range

from .._garden import COMMITTED_DECLARATIONS, named_task_modules
from ._oracle_tree import REMOVALS, RUN_ID, TODAY

#: A commit the record names. No test here reads git.
GIT_SHA: Final = "0" * 40

_POLICY: Final[TypeAdapter[TaskPolicy]] = TypeAdapter(TaskPolicy)


def declared() -> dict[str, TaskPolicy]:
    """The named committed declarations the integration fixtures exercise."""
    folder = CONFIG_DIR / "gardener"
    held = {
        path.stem: _POLICY.validate_json(path.read_text(encoding="utf-8"))
        for path in (folder / name for name in COMMITTED_DECLARATIONS)
    }
    # Packing tests need a stable non-yearly policy; deployment choices have
    # their own config tests.
    visual = json.loads(
        (FIXTURES_DIR / "gardener" / "garden" / "compact-gardener.json").read_text(
            encoding="utf-8"
        )
    )
    visual.update(
        ledger="visual-prunes",
        owns=["state/raw/visual-prunes", "state/compact/visual-prunes"],
        yearly_keep_months=None,
        yearly_prune_enable=False,
    )
    held["compact-visual-prunes"] = _POLICY.validate_python(visual)
    return held


def first_ledger_year() -> str:
    """The first UTC year a ledger can hold, as the committed `config/idhazh_gardener.json` says."""
    knobs = (CONFIG_DIR / "idhazh_gardener.json").read_text(encoding="utf-8")
    return GardenerConfig.model_validate_json(knobs).first_ledger_year


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
        for folder in (*policy.owns, *policy.reads)
        if (root / folder).is_dir()
    }
    return frozenset(children | named)


def context_for(
    name: str,
    root: Path,
    *,
    today: date = TODAY,
    period_range: tuple[str, str] | None = None,
    wake: bool = False,
    **changed: Any,
) -> TaskContext:
    """The context the runner would hand this task over `root`, with these knobs changed.

    With `wake`, it is what a scheduled wake hands it: the window the runner
    schedules for `today`, where the task has one, and a listing that names only
    the paths the runner names for that wake, so a step that reads anything else
    has to name it first.
    """
    tasks = declared()
    if changed:
        tasks[name] = _POLICY.validate_python({**tasks[name].model_dump(mode="json"), **changed})
    return _context(
        name,
        tasks,
        root,
        today=today,
        period_range=period_range,
        wake=wake,
        first_year=first_ledger_year(),
    )


def _context(
    name: str,
    tasks: dict[str, TaskPolicy],
    root: Path,
    *,
    today: date,
    period_range: tuple[str, str] | None,
    wake: bool,
    first_year: str,
) -> TaskContext:
    """The context the runner would hand `tasks[name]` over `root`."""
    if wake and period_range is not None:
        raise ValueError("a wake reads the window the runner schedules, not a named range")
    policy = tasks[name]
    folders = runner.folders_of(name, tasks, root, committed_folders(root, tasks))
    listed = runner.listed_folders(policy, folders)
    if wake:
        period_range = scheduled_range(name, policy, today)
        named = paths_for_task(root, name, policy, period_range, today=today)
    else:
        named = tuple(root / folder for folder in listed)
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
        listing=FileListing.from_disk(root, listed, paths=named),
        first_ledger_year=first_year,
        period_range=period_range,
    )


def run_task(
    name: str,
    root: Path,
    *,
    today: date = TODAY,
    period_range: tuple[str, str] | None = None,
    wake: bool = False,
    **changed: Any,
) -> Pass:
    """Run one shipped task, found the way the runner finds it."""
    policy = declared()[name]
    held = registry.bind(name, policy.kind, named_task_modules())
    return held.run(
        context_for(name, root, today=today, period_range=period_range, wake=wake, **changed)
    )


def run_declared(
    name: str, declaration: TaskPolicy, root: Path, *, today: date, first_year: str
) -> Pass:
    """Run one task at a scheduled wake on `today`, over a declaration the test built.

    `first_year` is the first UTC year a ledger can hold. Neither it nor any
    knob of the task is read from `config/`.
    """
    held = registry.bind(name, declaration.kind, named_task_modules())
    return held.run(
        _context(
            name,
            {name: declaration},
            root,
            today=today,
            period_range=None,
            wake=True,
            first_year=first_year,
        )
    )


def oracle() -> dict[str, Any]:
    """What each old pass removed and wrote over the oracle tree, recorded before it went."""
    recorded: dict[str, Any] = json.loads(REMOVALS.read_text(encoding="utf-8"))
    return recorded
