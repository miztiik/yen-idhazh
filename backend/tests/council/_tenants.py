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
