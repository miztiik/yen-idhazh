"""A tenant the council can really resolve, built for one test and thrown away.

Not a mock (Guardrail #7). It is a package on disk with a `tenant` module in it,
found the way a real judge is found and imported the way a real judge is
imported. Every member of the protocol is there and every one of them computes
what it returns; what the object does with the work is record it, because what
these tests ask is what the venue handed over rather than what a judge did with
it.

A package on disk rather than an object passed in, because the thing under test
is the import: an object handed straight to the resolver would skip the one step
that can go wrong.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Final

#: What a tenant module binds, and what the resolver reads off it.
TENANT_SOURCE: Final = '''
"""One tenant, declared the way a judge declares itself."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_invocation import (
    JudgeSchedule, PreparationReceipt, ScheduleRequest, ShardReport,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh import atomic_write
from idhazh.council import session
from idhazh.council.tenancy import ShardResult

JUDGE_ID = "{slug}"


@dataclass
class PaperTenant:
    """Write named tasks, process each admitted part, and record the handoff."""

    judge_id: str = JUDGE_ID
    shard_count: int = {shard_count}
    committed_paths: tuple[str, ...] = {committed_paths}
    handed: list[float] = field(default_factory=list)
    ran: list[tuple[str, str, int, int]] = field(default_factory=list)
    prepared: list[str] = field(default_factory=list)
    settled: list[str] = field(default_factory=list)
    asked: list[tuple[DateStamp, ...]] = field(default_factory=list)

    def schedule(self, *, request: ScheduleRequest) -> JudgeSchedule:
        self.asked.append(request.window)
        older = tuple(sorted((day for day in request.window if day != request.anchor_date), reverse=True))
        return JudgeSchedule(dates=(request.anchor_date,) + older[:request.max_older_dates])

    def publication_inputs(self, *, date: DateStamp) -> tuple[str, ...]:
        return ()

    def prepare(self, *, date: DateStamp, run_id: RunId, shards: int) -> ShardResult:
        self.prepared.append(date)
        path = session.unit_file(date, slot="tasks", judge_id=self.judge_id, suffix=".json")
        atomic_write.write_atomic(path, str(shards))
        return ShardResult(outcome=ShardOutcome.COMPLETED, files=(session.artifact_path(path),))

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
        prepared: PreparationReceipt,
    ) -> ShardResult:
        self.handed.append(deadline)
        self.ran.append((date, run_id, shard, shards))
        task = session.unit_file(
            date, slot="tasks", judge_id=self.judge_id, suffix=".json")
        width = int(task.read_text(encoding="utf-8"))
        if width != shards:
            raise ValueError("task width differs from the dispatched width")
        path = session.unit_file(date, slot="verdicts", judge_id=self.judge_id,
                                 shard=shard, suffix=".json")
        atomic_write.write_atomic(path, str(shard))
        return ShardResult(outcome=ShardOutcome.COMPLETED, files=(session.artifact_path(path),))

    def settle(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        state_dir: Path,
        identity: WriterIdentity,
        prepared: PreparationReceipt,
        reports: tuple[ShardReport, ...],
    ) -> ShardResult:
        self.settled.append(date)
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


TENANT = PaperTenant()
'''

#: Importing any unrequested neighbor is the failure this makes visible.
UNIMPORTABLE_SOURCE: Final = 'raise RuntimeError("an unrequested package was imported")\n'

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
from pathlib import Path

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_invocation import (
    JudgeSchedule, PreparationReceipt, ScheduleRequest, ShardReport,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh import atomic_write
from idhazh.council import session
from idhazh.council.tenancy import ShardResult

JUDGE_ID = "{slug}"

#: The units that die before they report anything back.
DEAD_UNITS = {dead_units}

#: How every unit that does report ends, and what it says the model cost.
OUTCOME = ShardOutcome("{outcome}")

MODEL_CALLS = {model_calls}


@dataclass
class ScriptedTenant:
    """Process named tasks while exercising explicit failure and deadline boundaries."""

    judge_id: str = JUDGE_ID
    shard_count: int = {shard_count}
    committed_paths: tuple[str, ...] = ()

    def schedule(self, *, request: ScheduleRequest) -> JudgeSchedule:
        older = tuple(sorted((day for day in request.window if day != request.anchor_date), reverse=True))
        return JudgeSchedule(dates=(request.anchor_date,) + older[:request.max_older_dates])

    def publication_inputs(self, *, date: DateStamp) -> tuple[str, ...]:
        return ()

    def prepare(self, *, date: DateStamp, run_id: RunId, shards: int) -> ShardResult:
        path = session.unit_file(date, slot="tasks", judge_id=self.judge_id, suffix=".json")
        atomic_write.write_atomic(path, str(shards))
        return ShardResult(outcome=ShardOutcome.COMPLETED, files=(session.artifact_path(path),))

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
        prepared: PreparationReceipt,
    ) -> ShardResult:
        if shard in DEAD_UNITS:
            raise RuntimeError("this unit died before it reported anything back")
        task = session.unit_file(date, slot="tasks", judge_id=self.judge_id, suffix=".json")
        if int(task.read_text(encoding="utf-8")) != shards:
            raise ValueError("task width differs from the dispatched width")
        path = session.unit_file(date, slot="verdicts", judge_id=self.judge_id,
                                 shard=shard, suffix=".json")
        atomic_write.write_atomic(path, str(shard))
        return ShardResult(outcome=OUTCOME, model_calls=MODEL_CALLS,
                           files=(session.artifact_path(path),))

    def settle(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        state_dir: Path,
        identity: WriterIdentity,
        prepared: PreparationReceipt,
        reports: tuple[ShardReport, ...],
    ) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


TENANT = ScriptedTenant()
'''

#: A tenant that is behind on a named set of nights and on no others.
#:
#: `TENANT_SOURCE` answers the whole window, which says nothing about a union of
#: two different answers. This one intersects the window it is handed with what
#: the test wrote, which is what a real tenant does: it answers about its own
#: ledger and stays inside the window it was asked about. A tenant that moved in
#: later is the same object with a shorter list.
BEHIND_SOURCE: Final = '''
"""One tenant that is behind on the nights a test says it is behind on."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_invocation import (
    JudgeSchedule, PreparationReceipt, ScheduleRequest, ShardReport,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
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

    def schedule(self, *, request: ScheduleRequest) -> JudgeSchedule:
        owed = tuple(sorted((night for night in request.window
                            if night in BEHIND_ON and night != request.anchor_date), reverse=True))
        return JudgeSchedule(dates=(request.anchor_date,) + owed[:request.max_older_dates] + UNASKED)

    def publication_inputs(self, *, date: DateStamp) -> tuple[str, ...]:
        return ()

    def prepare(self, *, date: DateStamp, run_id: RunId, shards: int) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)

    def run_shard(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        shard: int,
        shards: int,
        deadline: float,
        prepared: PreparationReceipt,
    ) -> ShardResult:
        raise ValueError("no tasks were prepared")

    def settle(
        self,
        *,
        date: DateStamp,
        run_id: RunId,
        state_dir: Path,
        identity: WriterIdentity,
        prepared: PreparationReceipt,
        reports: tuple[ShardReport, ...],
    ) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


TENANT = BelatedTenant()
'''


def a_venue(
    root: Path,
    *,
    package: str,
    slugs: Mapping[str, tuple[int, tuple[str, ...]]],
    quiet_neighbour: str = "",
    poisoned_neighbour: str = "",
    source: str = TENANT_SOURCE,
) -> None:
    """Write a package of tenants under `root`, one subpackage a slug.

    `slugs` maps a slug to its shard width and the ledger paths it commits.
    `quiet_neighbour`, when named, is a subpackage that declares no tenant and
    raises if anything imports it.
    `poisoned_neighbour` declares a tenant module that raises on import.
    """
    (root / package).mkdir(parents=True, exist_ok=True)
    (root / package / "__init__.py").write_text("", encoding="utf-8", newline="\n")
    for slug, (shard_count, committed_paths) in slugs.items():
        inside = root / package / slug.replace("-", "_")
        inside.mkdir(parents=True, exist_ok=True)
        (inside / "__init__.py").write_text("", encoding="utf-8", newline="\n")
        (inside / "tenant.py").write_text(
            source.format(
                slug=slug, shard_count=shard_count, committed_paths=repr(committed_paths)
            ),
            encoding="utf-8",
            newline="\n",
        )
    if quiet_neighbour:
        neighbour = root / package / quiet_neighbour
        neighbour.mkdir(parents=True, exist_ok=True)
        (neighbour / "__init__.py").write_text(UNIMPORTABLE_SOURCE, encoding="utf-8", newline="\n")
    if poisoned_neighbour:
        neighbour = root / package / poisoned_neighbour.replace("-", "_")
        neighbour.mkdir(parents=True, exist_ok=True)
        (neighbour / "__init__.py").write_text("", encoding="utf-8", newline="\n")
        (neighbour / "tenant.py").write_text(UNIMPORTABLE_SOURCE, encoding="utf-8", newline="\n")


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
