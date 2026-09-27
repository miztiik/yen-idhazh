"""Does every declared task find exactly one module, and does every module serve a task?

The registry has no list to keep in step: a task is a module in `tasks/` and a
declaration in `config/gardener/`, and the runner's pre-flight holds the two
against each other both ways before anything runs. Each way it can go wrong is
driven here from a real package of real task modules under
`tests/fixtures/gardener/task_packages/`, and each one has to stop the shard -
none may be caught and skipped, because a skipped task is a task that silently
stopped deleting.

Nothing here touches the network or the committed archive. The one committed
input is the configuration, read once to check that what ships binds.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from pydantic import TypeAdapter

from idhazh import config
from idhazh.contracts.knobs.gardener import TaskKind, TaskLifecycleStatus, TaskPolicy
from idhazh.gardener import registry, runner
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass
from idhazh.gardener.registry import DiscoveryError, TaskModule

from ._garden import GARDENER_FIXTURES, TASK_PACKAGES, task_package

pytestmark = pytest.mark.contract

#: Libraries a task module may use inside `run` and never at module scope.
HEAVY: tuple[str, ...] = (
    "pyarrow",
    "duckdb",
    "urllib.request",
    "http.client",
    "requests",
    "httpx",
    "urllib3",
    "aiohttp",
)


def declared(*paths: Path) -> dict[str, TaskPolicy]:
    """Fixture declarations, validated one at a time, keyed by file stem."""
    adapter: TypeAdapter[TaskPolicy] = TypeAdapter(TaskPolicy)
    return {path.stem: adapter.validate_json(path.read_text(encoding="utf-8")) for path in paths}


def runner_garden() -> dict[str, TaskPolicy]:
    return declared(*sorted((GARDENER_FIXTURES / "runner").glob("*.json")))


def test_the_shipped_package_declares_no_task() -> None:
    """Row by row, tasks arrive with their modules. Today the folder holds none."""
    assert registry.discover() == {}


def test_finding_the_tasks_loads_no_heavy_library() -> None:
    """Discovery imports every task module, so a module-scope import is paid by every shard.

    Checked in a fresh interpreter, because this process has imported pyarrow
    long before this test runs. The fixture package is discovered as well as
    the shipped one, so the check reads real modules rather than an empty folder.
    """
    body = (
        "import importlib, sys\n"
        "from idhazh.gardener import registry\n"
        "registry.discover()\n"
        "found = registry.discover(importlib.import_module('garden_tasks_ok'))\n"
        "assert found, 'the fixture package declared no task, so this checks nothing'\n"
        f"heavy = {HEAVY!r}\n"
        "loaded = sorted(n for n in sys.modules for h in heavy if n == h or n.startswith(h + '.'))\n"
        "sys.exit('discovery loaded ' + ', '.join(loaded) if loaded else 0)\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", body],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ
        | {"PYTHONPATH": os.pathsep.join((str(REPO_ROOT / "backend"), str(TASK_PACKAGES)))},
        cwd=str(REPO_ROOT),
    )
    assert done.returncode == 0, done.stderr or done.stdout


def _a_run(context: TaskContext) -> Pass:
    raise AssertionError("bind hands back a module; it never runs one")


def test_a_task_binds_to_its_own_module_before_the_one_for_its_kind() -> None:
    """Two lookups and no third: the module named for the task, else the one named for its kind."""
    own = TaskModule(stem="old_days", kind=TaskKind.RETENTION, run=_a_run)
    shared = TaskModule(stem="retention", kind=TaskKind.RETENTION, run=_a_run)
    modules = {"old_days": own, "retention": shared}

    assert registry.bind("old-days", TaskKind.RETENTION, modules) is own
    assert registry.bind("seen", TaskKind.RETENTION, modules) is shared
    with pytest.raises(DiscoveryError, match=r"tasks/traces\.py nor tasks/compaction\.py"):
        registry.bind("traces", TaskKind.COMPACTION, modules)


def test_two_modules_that_would_serve_one_task_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """`old-days.py` and `old_days.py` both answer to the task `old-days`. Neither wins."""
    package = task_package("garden_tasks_two_names", monkeypatch)
    with pytest.raises(DiscoveryError) as refusal:
        registry.discover(package)
    assert "old-days" in str(refusal.value) and "old_days" in str(refusal.value)


def test_a_module_that_raises_on_import_stops_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-raised with its own traceback attached, never skipped."""
    package = task_package("garden_tasks_bad_import", monkeypatch)
    with pytest.raises(DiscoveryError, match="raised while it was imported") as refusal:
        registry.discover(package)
    assert isinstance(refusal.value.__cause__, ImportError)


def test_a_module_that_declares_no_task_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    package = task_package("garden_tasks_no_task", monkeypatch)
    with pytest.raises(DiscoveryError, match="helper declares no task"):
        registry.discover(package)


def test_a_module_whose_kind_disagrees_with_its_declaration_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retention declaration handed to a compaction module would be read as the wrong shape."""
    modules = registry.discover(task_package("garden_tasks_wrong_kind", monkeypatch))
    tasks = declared(GARDENER_FIXTURES / "breaks" / "old-days.json")
    with pytest.raises(DiscoveryError, match=r"is a retention task and tasks/old_days\.py serves"):
        runner.preflight(tasks, modules)


def test_every_declaration_is_served_and_every_module_serves_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two-way check, asserted both ways over a garden that passes it."""
    modules = registry.discover(task_package("garden_tasks_ok", monkeypatch))
    tasks = runner_garden()

    bound = runner.preflight(tasks, modules)

    assert set(bound) == set(tasks), "a declaration went unserved"
    assert {held.stem for held in bound.values()} == set(modules), "a module serves nothing"
    assert bound["compact-gardener"].stem == "compaction"
    assert bound["old-days"].stem == bound["rehearsal"].stem == "retention"


def test_a_declaration_no_module_serves_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = registry.discover(task_package("garden_tasks_ok", monkeypatch))
    tasks = runner_garden() | declared(GARDENER_FIXTURES / "garden" / "history.json")
    with pytest.raises(DiscoveryError, match=r"history\.json is served by no module"):
        runner.preflight(tasks, modules)


def test_a_module_no_declaration_uses_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    modules = registry.discover(task_package("garden_tasks_ok", monkeypatch))
    tasks = declared(GARDENER_FIXTURES / "runner" / "old-days.json")
    with pytest.raises(DiscoveryError, match=r"tasks/compaction\.py serves no active or paused"):
        runner.preflight(tasks, modules)


def test_a_retired_declaration_needs_no_module_and_keeps_none_in_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retired task never runs, so it neither needs a module nor keeps one alive."""
    modules = registry.discover(task_package("garden_tasks_ok", monkeypatch))
    garden = runner_garden()
    retired = garden["compact-gardener"].model_copy(
        update={"lifecycle_status": TaskLifecycleStatus.RETIRED}
    )
    history = declared(GARDENER_FIXTURES / "garden" / "history.json")["history"]
    tasks = {
        **garden,
        "history": history.model_copy(update={"lifecycle_status": TaskLifecycleStatus.RETIRED}),
    }
    assert set(runner.preflight(tasks, modules)) == set(garden)

    with pytest.raises(DiscoveryError, match=r"tasks/compaction\.py serves no active or paused"):
        runner.preflight({**tasks, "compact-gardener": retired}, modules)


def test_what_ships_binds_both_ways() -> None:
    """The committed declarations against the committed modules: the check every shard makes.

    This is the test that fails a pull request which adds a declaration without
    its module, or a module without its declaration, before any wake runs it.
    """
    settings = config.load_gardener()
    bound = runner.preflight(settings.tasks, registry.discover())
    assert set(bound) == {
        name
        for name, policy in settings.tasks.items()
        if policy.lifecycle_status is not TaskLifecycleStatus.RETIRED
    }
