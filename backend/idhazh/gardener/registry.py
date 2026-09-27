"""Which module runs each gardener task, found by name in one folder and never listed?

Two functions and nothing else. `discover` imports every module in
`idhazh.gardener.tasks` and keeps the ones that declare a task. `bind` answers
which of them runs one declaration, in two lookups: the module named for the
task, else the one named for its kind.

**There is no list of tasks to keep in step.** A task joins the gardener when
its module lands in `tasks/` and its declaration lands in `config/gardener/`,
and the runner's pre-flight refuses either one arriving without the other.

**A config value never names a module.** The folder is fixed in code and the
names that choose inside it are closed words - a task's name and a `TaskKind` -
so text from a file cannot choose which code runs (Guardrail #11).

**Every fault stops the shard before anything runs.** A module that raises on
import, one that declares no task, two modules that would serve one name, a
declaration nothing serves, and a module whose kind disagrees with the
declaration it serves are each raised as `DiscoveryError`, and the runner exits 2
on it. None is caught and skipped, because a skipped task is a task that
silently stopped deleting.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType, ModuleType
from typing import Final

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener import tasks as shipped_tasks
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

#: The two names a task module holds, and all it holds.
KIND_NAME: Final = "KIND"
RUN_NAME: Final = "run"

#: A stem that opens with this is a helper beside the tasks, never a task.
PRIVATE_PREFIX: Final = "_"


class DiscoveryError(Exception):
    """A task the runner cannot serve. It exits 2 before any task runs."""


@dataclass(frozen=True, slots=True)
class TaskModule:
    """One module in `tasks/`: its file's stem, the kind it serves, and what runs it."""

    stem: str
    kind: TaskKind
    run: Callable[[TaskContext], Pass]


def _module_name(task: str) -> str:
    """The stem a task's own module has: its name, with hyphens as underscores."""
    return task.replace("-", "_")


def discover(package: ModuleType = shipped_tasks) -> Mapping[str, TaskModule]:
    """Every task module in the package, by stem, in sorted order. Imported once a process.

    The package is a parameter so a test can hand in a package of its own. Nothing
    in config or on a command line reaches it.
    """
    return _discovered(package.__name__)


@cache
def _discovered(package_name: str) -> Mapping[str, TaskModule]:
    package = importlib.import_module(package_name)
    found: dict[str, TaskModule] = {}
    serves: dict[str, str] = {}
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda info: info.name):
        stem = info.name
        if stem.startswith(PRIVATE_PREFIX) or info.ispkg:
            continue
        name = _module_name(stem)
        if name in serves:
            raise DiscoveryError(
                f"{package_name}.{serves[name]} and {package_name}.{stem} would both serve "
                f"a task called {name}. Rename one: two modules may not serve one name"
            )
        try:
            module = importlib.import_module(f"{package_name}.{stem}")
        except Exception as error:
            raise DiscoveryError(
                f"{package_name}.{stem} raised while it was imported, so no task in this "
                "shard runs until it imports cleanly"
            ) from error
        kind = getattr(module, KIND_NAME, None)
        run = getattr(module, RUN_NAME, None)
        if not isinstance(kind, TaskKind) or not callable(run):
            raise DiscoveryError(
                f"{package_name}.{stem} declares no task. A task module holds {KIND_NAME}, a "
                f"TaskKind, and {RUN_NAME}, which takes a TaskContext and returns a Pass"
            )
        serves[name] = stem
        found[stem] = TaskModule(stem=stem, kind=kind, run=run)
    return MappingProxyType(found)


def bind(name: str, kind: TaskKind, modules: Mapping[str, TaskModule]) -> TaskModule:
    """The module that runs one declaration: named for the task, else named for its kind."""
    own, shared = _module_name(name), kind.value
    held = modules.get(own) or modules.get(shared)
    if held is None:
        raise DiscoveryError(
            f"config/gardener/{name}.json is served by no module: there is neither "
            f"tasks/{own}.py nor tasks/{shared}.py"
        )
    if held.kind is not kind:
        raise DiscoveryError(
            f"config/gardener/{name}.json is a {kind.value} task and tasks/{held.stem}.py "
            f"serves {held.kind.value}. A module runs the kind it declares, or it would be "
            "handed a declaration it cannot read"
        )
    return held
