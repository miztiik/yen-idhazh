"""Which named module runs each configured gardener task?

`discover` imports only each active or paused declaration's named module and
the module for its kind as a fallback. `bind` selects the named module first.
No task-package directory is listed.

**The committed config names the task set.** A task runs only when its name is
in `config/idhazh_gardener.json` and its declaration validates. The runner's
pre-flight refuses a declaration that has no module.

**A config value never names a module.** The folder is fixed in code and the
names that choose inside it are closed words - a task's name and a `TaskKind` -
so text from a file cannot choose which code runs (Guardrail #11).

**Every fault stops the shard before anything runs.** A named module that
raises on import, a declaration nothing serves, and a module whose kind
disagrees with the declaration it serves are each raised as `DiscoveryError`,
and the runner exits 2 on it. None is caught and skipped, because a skipped
task is a task that silently stopped deleting.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType, ModuleType
from typing import Final

from idhazh.contracts.knobs.gardener import TaskKind, TaskLifecycleStatus, TaskPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

#: The mandatory names a task module holds; OWNED_LEDGERS optionally declares ledger ownership.
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
    owned_ledgers: tuple[LedgerName, ...] = ()


def _module_name(task: str) -> str:
    """The stem a task's own module has: its name, with hyphens as underscores."""
    return task.replace("-", "_")


def discover(
    package: ModuleType, tasks: Mapping[str, TaskPolicy]
) -> Mapping[str, TaskModule]:
    """Import only the modules named by active or paused task declarations.

    The package is a parameter so a test can hand in a package of its own.
    A declaration names the only task module to try and its kind names the
    shared fallback. No package directory is listed.
    """
    declarations = tuple(
        sorted(
            (
                (name, policy.kind.value)
                for name, policy in tasks.items()
                if policy.lifecycle_status is not TaskLifecycleStatus.RETIRED
            )
        )
    )
    return _discovered(package.__name__, declarations)


@cache
def _discovered(
    package_name: str, declarations: tuple[tuple[str, str], ...]
) -> Mapping[str, TaskModule]:
    found: dict[str, TaskModule] = {}
    for task_name, kind_name in declarations:
        for stem in dict.fromkeys((_module_name(task_name), kind_name)):
            if stem.startswith(PRIVATE_PREFIX):
                continue
            qualified = f"{package_name}.{stem}"
            try:
                module = importlib.import_module(qualified)
            except ModuleNotFoundError as error:
                if error.name == qualified:
                    continue
                raise DiscoveryError(
                    f"{qualified} raised while it was imported, so no task in this shard runs "
                    "until it imports cleanly"
                ) from error
            except Exception as error:
                raise DiscoveryError(
                    f"{qualified} raised while it was imported, so no task in this shard runs "
                    "until it imports cleanly"
                ) from error
            kind = getattr(module, KIND_NAME, None)
            run = getattr(module, RUN_NAME, None)
            if not isinstance(kind, TaskKind) or not callable(run):
                raise DiscoveryError(
                    f"{qualified} declares no task. A task module holds {KIND_NAME}, a "
                    f"TaskKind, and {RUN_NAME}, which takes a TaskContext and returns a Pass"
                )
            declared = getattr(module, "OWNED_LEDGERS", ())
            if not isinstance(declared, tuple) or any(
                not isinstance(which, LedgerName) for which in declared
            ):
                raise DiscoveryError(f"{qualified}.OWNED_LEDGERS must be a tuple of LedgerName")
            found[stem] = TaskModule(stem=stem, kind=kind, run=run, owned_ledgers=declared)
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
