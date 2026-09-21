"""A tenant the council can really resolve, built for one test and thrown away.

Not a mock (Guardrail #7). It is a package on disk with a `tenant` module in it,
found the way a real judge is found and imported the way a real judge is
imported. Every member of the protocol is there and every one of them computes
what it returns; what the object does with the work is record it, because what
these tests ask is what the venue handed over rather than what a judge did with
it.

A package on disk rather than an object passed in, because the thing under test
is the search: an object handed straight to the resolver would skip the one step
that can go wrong.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Final

#: What a tenant module binds, and what the search reads off it.
TENANT_SOURCE: Final = '''
"""One tenant, declared the way a judge declares itself."""

from __future__ import annotations

from dataclasses import dataclass, field

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.council.tenancy import ShardResult

JUDGE_ID = "{slug}"


@dataclass
class PaperTenant:
    """A tenant that files nothing and remembers what the venue handed it."""

    judge_id: str = JUDGE_ID
    shard_count: int = {shard_count}
    committed_paths: tuple[str, ...] = {committed_paths}
    handed: list[float] = field(default_factory=list)
    ran: list[tuple[str, str, int, int]] = field(default_factory=list)
    prepared: list[str] = field(default_factory=list)
    settled: list[str] = field(default_factory=list)

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        return tuple(window)

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        self.prepared.append(date)
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
    ) -> ShardResult:
        self.handed.append(deadline)
        self.ran.append((date, run_id, shard, shards))
        return ShardResult(outcome=ShardOutcome.COMPLETED)

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        self.settled.append(date)
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


TENANT = PaperTenant()
'''

#: A package that declares no tenant and refuses to be imported at all. The
#: search is supposed to walk past it on the listing, so importing it is the
#: failure this makes visible.
UNIMPORTABLE_SOURCE: Final = 'raise RuntimeError("the search imported a package with no tenant")\n'

#: A tenant whose units end the way a night under test needs them to.
#:
#: Not a mock either. It computes every answer it gives; what a test chooses is
#: the shape of the night - which unit dies before it reports, how the rest end,
#: and whether the tenant ran a model at all. A mock would hand back a plausible
#: row it never built, which is the failure mode this whole file exists to stay
#: clear of (Guardrail #7).
SCRIPTED_SOURCE: Final = '''
"""One tenant whose units end the way a test needs them to."""

from __future__ import annotations

from dataclasses import dataclass

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.council.tenancy import ShardResult

JUDGE_ID = "{slug}"

#: The units that die before they report anything back.
DEAD_UNITS = {dead_units}

#: How every unit that does report ends, and what it says the model cost.
OUTCOME = ShardOutcome("{outcome}")

MODEL_CALLS = {model_calls}


@dataclass
class ScriptedTenant:
    """A tenant that files nothing of its own and reports what it was written to."""

    judge_id: str = JUDGE_ID
    shard_count: int = {shard_count}
    committed_paths: tuple[str, ...] = ()

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        return tuple(window)

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.COMPLETED)

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
    ) -> ShardResult:
        if shard in DEAD_UNITS:
            raise RuntimeError("this unit died before it reported anything back")
        return ShardResult(outcome=OUTCOME, model_calls=MODEL_CALLS)

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


TENANT = ScriptedTenant()
'''

#: A tenant that is behind on a named set of nights and on no others.
#:
#: `TENANT_SOURCE` answers the whole window, which says nothing about a union of
#: two different answers. This one intersects the window it is handed with what
#: the test wrote, which is what a real tenant does: it answers about its own
#: store and stays inside the window it was asked about. A tenant that moved in
#: later is the same object with a shorter list.
BEHIND_SOURCE: Final = '''
"""One tenant that is behind on the nights a test says it is behind on."""

from __future__ import annotations

from dataclasses import dataclass

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.council.tenancy import ShardResult

JUDGE_ID = "{slug}"

#: The nights this tenant never counted. Answered only where the council asked.
BEHIND_ON = {behind_on}

#: A night this tenant answers with whether the council asked about it or not,
#: which is the tenant bug the plan refuses by name.
UNASKED = {unasked}


@dataclass
class BelatedTenant:
    """A tenant that files nothing and knows only which nights it owes."""

    judge_id: str = JUDGE_ID
    shard_count: int = {shard_count}
    committed_paths: tuple[str, ...] = ()

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        owed = tuple(night for night in window if night in BEHIND_ON)
        return owed + UNASKED

    def prepare(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
    ) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.COMPLETED)

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


TENANT = BelatedTenant()
'''


def a_venue(
    root: Path,
    *,
    package: str,
    slugs: Mapping[str, tuple[int, tuple[str, ...]]],
    quiet_neighbour: str = "",
) -> None:
    """Write a package of tenants under `root`, one subpackage a slug.

    `slugs` maps a slug to its shard width and the store paths it commits.
    `quiet_neighbour`, when named, is a subpackage that declares no tenant and
    raises if anything imports it.
    """
    (root / package).mkdir(parents=True, exist_ok=True)
    (root / package / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    for slug, (shard_count, committed_paths) in slugs.items():
        inside = root / package / slug.replace("-", "_")
        inside.mkdir(parents=True, exist_ok=True)
        (inside / "__init__.py").write_text("", encoding="utf-8", newline="\n")
        (inside / "tenant.py").write_text(
            TENANT_SOURCE.format(
                slug=slug, shard_count=shard_count, committed_paths=repr(committed_paths)
            ),
            encoding="utf-8",
            newline="\n",
        )
    if quiet_neighbour:
        neighbour = root / package / quiet_neighbour
        neighbour.mkdir(parents=True, exist_ok=True)
        (neighbour / "__init__.py").write_text(
            UNIMPORTABLE_SOURCE, encoding="utf-8", newline="\n"
        )


def a_scripted_venue(
    root: Path,
    *,
    package: str,
    slug: str,
    shard_count: int,
    dead_units: tuple[int, ...] = (),
    outcome: str = "completed",
    model_calls: int | None = None,
) -> None:
    """Write one tenant under `root` whose units end the way this test needs.

    `dead_units` names the unit numbers that raise before reporting. `outcome`
    is how every unit that does report ends, and `model_calls` is what it says
    the model cost - `None` for a tenant that has no model at all.
    """
    (root / package).mkdir(parents=True, exist_ok=True)
    (root / package / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    inside = root / package / slug.replace("-", "_")
    inside.mkdir(parents=True, exist_ok=True)
    (inside / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    (inside / "tenant.py").write_text(
        SCRIPTED_SOURCE.format(
            slug=slug,
            shard_count=shard_count,
            dead_units=repr(dead_units),
            outcome=outcome,
            model_calls=repr(model_calls),
        ),
        encoding="utf-8",
        newline="\n",
    )


def a_belated_venue(
    root: Path,
    *,
    package: str,
    slug: str,
    behind_on: tuple[str, ...],
    unasked: tuple[str, ...] = (),
    shard_count: int = 1,
) -> None:
    """Write one tenant under `root` that owes the nights `behind_on` names.

    It answers only where the council asked, so a night outside the window it is
    handed is simply not reported. `unasked` is the tenant bug: a date it names
    whether the council asked about it or not.
    """
    (root / package).mkdir(parents=True, exist_ok=True)
    (root / package / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    inside = root / package / slug.replace("-", "_")
    inside.mkdir(parents=True, exist_ok=True)
    (inside / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    (inside / "tenant.py").write_text(
        BEHIND_SOURCE.format(
            slug=slug,
            behind_on=repr(behind_on),
            unasked=repr(unasked),
            shard_count=shard_count,
        ),
        encoding="utf-8",
        newline="\n",
    )


def forget(package: str) -> None:
    """Drop a written package out of the interpreter it was imported into.

    A temporary directory is gone by the next test and a stale entry in
    `sys.modules` would still resolve, so the next test would read a tenant it
    never wrote.
    """
    for name in [module for module in sys.modules if module.split(".")[0] == package]:
        del sys.modules[name]
    importlib.invalidate_caches()


def written(package: str, slug: str) -> ModuleType:
    """The tenant module a test wrote, so it can read what the venue handed it."""
    return importlib.import_module(f"{package}.{slug.replace('-', '_')}.tenant")
