"""What a publication check is, and how the ones on disk are found.

A check declares one module-level `CHECK` (or a `CHECKS` tuple), and this
module binds every one of them by name. Nothing here reads a day or decides
what is wrong with one - that is a check's own job, and the runner's.

Four wiring faults are raised rather than logged, because a gate that quietly
ran three of its four rules is a gate nobody can trust: a module that will not
import, a module declaring no check, two modules claiming one name, and a check
naming a ledger the ledger door has no entry for.

The discovery follows `idhazh.council.registry`, which finds judges the same
way and for the same reason.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any, Final, NamedTuple

from idhazh.contracts.base import Contract
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.ledger_name import LedgerName
from idhazh.ledger import door_contract

#: The package every check module sits in. One name, so a move is one edit.
CHECKS_PACKAGE: Final = "idhazh.publication_checks.checks"

#: What a check module declares. `CHECK` is the single-rule spelling and
#: `CHECKS` the plural one; a module may use either and nothing may use neither.
SINGLE_ATTRIBUTE: Final = "CHECK"
PLURAL_ATTRIBUTE: Final = "CHECKS"


class PublicationCheckError(RuntimeError):
    """A framework wiring fault, raised before any check runs.

    It is not a broken day. A broken day is a fault the gate reports and the
    run exits 1 on; this says the gate itself is mis-wired, which the CLI
    reports as exit 2 so an operator can tell "the day is wrong" from "the
    thing that checks days is wrong".
    """


class CheckScope(StrEnum):
    """Which of the two things a check is handed.

    `DAY` gets every committed day in scope, already parsed. `TREE` gets the
    published tree and the months this run touched - for a payload that is not
    a day at all, like the console's own month shards.
    """

    DAY = "day"
    TREE = "tree"


@dataclass(frozen=True)
class CommittedDay:
    """One committed day, read once and handed to every DAY check.

    `raw` is the JSON object, because `DigestView.project` reads the object
    rather than the model. `day` is the validated model, or `None` when the
    object fails `digest-day.schema.json` - a check that needs the model skips
    those days, and the runner has already reported the parse fault.
    """

    date: str
    path: Path
    payload: bytes
    raw: dict[str, Any]
    day: DigestDay | None


@dataclass(frozen=True)
class DayContext:
    """Everything a DAY check may read: the days, and the two roots under them."""

    digest_root: Path
    public_root: Path
    days: tuple[CommittedDay, ...]


@dataclass(frozen=True)
class TreeContext:
    """Everything a TREE check may read.

    `months` names the months this run touched, as `YYYY-MM`. `None` means
    every month on disk, which is the sweep a contract change takes.
    """

    root: Path
    months: frozenset[str] | None


class CheckResult(NamedTuple):
    """What a check hands back: sentences about what is wrong, and rows to file.

    `rows` stays empty unless the check declares a ledger. A check that emits
    rows with no ledger has nowhere to file them, which the runner refuses.
    """

    faults: tuple[str, ...] = ()
    rows: tuple[Contract, ...] = ()


@dataclass(frozen=True)
class Check:
    """One rule, as the framework sees it.

    `scope` is what says which context `run` is handed, so `run` is typed on
    whichever of the two it wants and the pairing is enforced once, by the
    runner, rather than by a narrowing in every check that cannot fail.

    `ledger` is how a check persists a measurement rather than only a verdict.
    It is `None` on every rule shipped today - the hook is live so that the
    first check that needs one adds a field rather than a subsystem.
    """

    name: str
    scope: CheckScope
    run: Callable[[Any], CheckResult]
    ledger: LedgerName | None = None


def _declared(module: ModuleType) -> tuple[Check, ...]:
    """Every check one module declares, or a refusal naming the module."""
    found = [c for c in (getattr(module, SINGLE_ATTRIBUTE, None),) if isinstance(c, Check)]
    found += [c for c in getattr(module, PLURAL_ATTRIBUTE, ()) if isinstance(c, Check)]
    if not found:
        raise PublicationCheckError(
            f"{module.__name__} declares no {SINGLE_ATTRIBUTE}/{PLURAL_ATTRIBUTE} of type Check"
        )
    return tuple(found)


def discover() -> tuple[Check, ...]:
    """Every check on disk, bound by name, in a fixed order.

    Sorted twice on purpose: the modules are walked in name order and the
    result is returned in check-name order, so two runs over one tree report
    their faults in the same sequence and a diff of two logs is readable.
    """
    package = importlib.import_module(CHECKS_PACKAGE)
    bound: dict[str, Check] = {}
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda m: m.name):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{CHECKS_PACKAGE}.{info.name}")
        for check in _declared(module):
            if check.name in bound:
                raise PublicationCheckError(
                    f"two modules declare check {check.name!r}: "
                    f"{bound[check.name].run.__module__} and {module.__name__}"
                )
            bound[check.name] = check
    return tuple(bound[name] for name in sorted(bound))


def validate_registry(registry: Sequence[Check]) -> None:
    """Refuse a check that names a ledger nothing can write into.

    A ledger the ledger door has no entry for has no key and no row contract,
    so the first row would fail at the write - after the gate had already
    passed the day. The wiring is checked before any check runs, so the
    failure names the check rather than a row.
    """
    for check in registry:
        if check.ledger is None:
            continue
        try:
            door_contract(check.ledger)
        except (KeyError, ValueError) as error:
            raise PublicationCheckError(
                f"{check.name} names ledger {check.ledger!r} with no ledger-door entry"
            ) from error
