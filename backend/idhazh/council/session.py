"""What does the council do with the tenants it is hosting tonight?

Three units of work, in the order a night runs them: pick the work, run one
shard of it, and settle what came back. Each one resolves the slugs the config
names and calls the matching member on every tenant it got.

**The council owns the invocation, so it owns the outcome.** It starts the
clock, calls the tenant, and files its own row on the way out - so the venue's
record of a unit exists whether or not the tenant remembered to write anything
of its own. The cost cells on that row come off what the tenant handed back and
none of them is read out of a tenant's store.

Nothing here reads a result by name beyond those. What a tenant hands back
crosses whole, so a venue hosting a judge with a funnel and a judge with none
runs the same code for both.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import (
    SELECTION_UNIT,
    SETTLEMENT_UNIT,
    CouncilShardOutcome,
)
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council import metrics_sink
from idhazh.council.deadline import run_shard_under_the_clock
from idhazh.council.registry import tenant, tenants
from idhazh.council.tenancy import ShardResult, Tenant

_log: Final = logging.getLogger(__name__)

#: Where one night's work lands before a later job collects it. The council
#: names the root because the council is what carries it between jobs as an
#: artifact; what a tenant puts inside it is the tenant's own business.
COUNCIL_ROOT_RELPATH: Final = "backend/var/council"

COUNCIL_ROOT: Final = config.REPO_ROOT / COUNCIL_ROOT_RELPATH

#: The three slots the venue names inside the root it carries: what a date's
#: work was picked from, what the units measured on their way out, and the
#: venue's own record of how each of those units ended. A tenant may name a slot
#: of its own beside them - what the venue guarantees is the carrying, not the
#: list of names.
SELECTION_DIRNAME: Final = "selection"

METRICS_DIRNAME: Final = "metrics"

OUTCOMES_DIRNAME: Final = "outcomes"

#: How a recorded instant is spelled. The contract pins the shape, and this is
#: the one place a council row is stamped with it.
STARTED_AT_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"


def scratch_root(date: DateStamp) -> Path:
    """The directory one date's work is written under, on whichever runner runs it."""
    return COUNCIL_ROOT / date


def outcomes_dir(date: DateStamp) -> Path:
    """Where one date's council rows wait for the job that commits them.

    Beside the tenants' own uploads rather than inside one of them. The venue's
    record of a unit has to survive a tenant that wrote nothing, so it cannot
    live under a directory a tenant owns.
    """
    return scratch_root(date) / OUTCOMES_DIRNAME


def unit_dir(date: DateStamp, *, slot: str, judge_id: str) -> Path:
    """The one directory a tenant's files for a later job sit in.

    Under the root the council carries, because a path outside it reaches no
    other job at all: the runner that wrote it is thrown away when its job ends.
    The slug is a directory level for the reason `metrics_sink` makes it one - a
    reader lists a directory holding one tenant's files and can never take a
    second tenant's for its own.
    """
    return scratch_root(date) / slot / metrics_sink.checked_slug(judge_id)


def unit_file(
    date: DateStamp,
    *,
    slot: str,
    judge_id: str,
    shard: int | None = None,
    suffix: str = ".csv",
) -> Path:
    """What one unit calls the file it leaves inside that directory.

    `ledger.segment_name`'s grammar carrying the council's own identity: the
    elements hyphen-joined, the shard last and two digits wide, so the name says
    which date, which tenant and which unit wrote it wherever the file is read.
    Spelled here rather than taken from that helper, which asks for a run attempt
    the council never reads and a `ServerJob` none of this workflow's jobs is a
    member of - a name carrying an invented cell names nothing.

    Eight units of one date write eight names, so nothing they do concurrently
    can land on one path.

    **`shard` is None for the unit that picks the work.** A date has one draw and
    every unit of that date reads it, so a number there would claim a writer that
    never existed.
    """
    unit = "" if shard is None else f"-{shard:02d}"
    name = f"{date}-{metrics_sink.checked_slug(judge_id)}{unit}{suffix}"
    return unit_dir(date, slot=slot, judge_id=judge_id) / name


def shard_width(council: CouncilConfig, host: Tenant) -> int:
    """How many ways one tenant's work splits tonight.

    The tenant's own answer, narrowed by what the venue is willing to fan out
    to. Named here rather than computed twice: the matrix builds the cells from
    it and the two units that run once a date record it, so a second spelling
    would let a night's rows disagree with the night's own shape.
    """
    return min(host.shard_count, council.shards)


def prepare(council: CouncilConfig, *, date: DateStamp, run_id: RunId) -> tuple[ShardResult, ...]:
    """Pick the work, once a date, before any shard runs.

    In the order the config names the tenants, because a venue that ran them in
    an order it never declared could not be re-run into the same state.
    """
    return tuple(
        _recorded(
            host.judge_id,
            unit="prepare",
            date=date,
            run_id=run_id,
            shard=SELECTION_UNIT,
            shards=shard_width(council, host),
            work=partial(host.prepare, date=date, run_id=run_id),
        )
        for host in _hosted(council, date)
    )


def settle(
    council: CouncilConfig, *, date: DateStamp, run_id: RunId, state_dir: Path
) -> tuple[ShardResult, ...]:
    """Count, fit, or do nothing, once a date after every shard has reported.

    Then collect the night's own rows into the council's store, which is the one
    place in the night that writes under `state/`. The collect runs on the way
    out whatever the tenants did, so a tenant that died still leaves the venue
    holding the record of every unit that reported before it.
    """
    hosted = _hosted(council, date)
    try:
        return tuple(
            _recorded(
                host.judge_id,
                unit="settle",
                date=date,
                run_id=run_id,
                shard=SETTLEMENT_UNIT,
                shards=shard_width(council, host),
                work=partial(host.settle, date=date, run_id=run_id),
            )
            for host in hosted
        )
    finally:
        _collect(hosted, date=date, state_dir=state_dir)


def run_shard(
    council: CouncilConfig,
    *,
    slug: str,
    date: DateStamp,
    run_id: RunId,
    shard: int,
    shards: int,
    started: float,
) -> ShardResult:
    """One shard of one tenant's work, stopped on the council's own clock.

    One slug rather than every hosted tenant: a cell of the matrix is one
    invocation, so two tenants sharing a job would each be handed the whole span
    the venue meant for one of them.
    """
    host = tenant(slug)
    return _recorded(
        host.judge_id,
        unit=f"shard {shard} of {shards}",
        date=date,
        run_id=run_id,
        shard=shard,
        shards=shards,
        work=partial(
            run_shard_under_the_clock,
            host,
            date=date,
            run_id=run_id,
            shard=shard,
            shards=shards,
            council=council,
            started=started,
        ),
    )


def _hosted(council: CouncilConfig, date: DateStamp) -> tuple[Tenant, ...]:
    """The tenants this night hosts, said out loud so an empty night is readable."""
    hosted = tenants(council.tenants)
    if not hosted:
        _log.info("no tenant is registered, so %s is a night the council hosts nobody", date)
    return hosted


def _recorded(
    judge_id: str,
    *,
    unit: str,
    date: DateStamp,
    run_id: RunId,
    shard: int,
    shards: int,
    work: Callable[[], ShardResult],
) -> ShardResult:
    """Run one unit of hosted work and file the council's own row on the way out.

    The row is filed in a `finally`, so it survives anything that goes wrong
    after the tenant handed its result back.

    **A unit that never handed one back files nothing**, and that is the design
    rather than a gap. The outcome vocabulary has three members and none of them
    says "this died"; what says it is the missing row, read against the `shards`
    cell its siblings carry. A unit the platform killed leaves the same gap, so
    an operator reads one signal and not two.
    """
    began = datetime.now(UTC).strftime(STARTED_AT_FORMAT)
    started = time.monotonic()
    produced: ShardResult | None = None
    try:
        produced = work()
        return produced
    finally:
        if produced is not None:
            _file(
                produced,
                judge_id=judge_id,
                date=date,
                run_id=run_id,
                shard=shard,
                shards=shards,
                began=began,
                seconds=time.monotonic() - started,
            )
            _log.info(
                "council %s for %s on %s ended %s", unit, judge_id, date, produced.outcome.value
            )


def _file(
    result: ShardResult,
    *,
    judge_id: str,
    date: DateStamp,
    run_id: RunId,
    shard: int,
    shards: int,
    began: str,
    seconds: float,
) -> Path:
    """Write the venue's own row where the job that commits it will find it.

    Through the capability a tenant's own row ships on, so the night has one
    shipping path and not two. The four cost cells are copied off what the
    tenant handed back and read out of nothing else - a tenant with no model
    hands back nulls, and null is not zero.
    """
    row = CouncilShardOutcome.model_validate(
        {
            "date": date,
            "run_id": run_id,
            "judge_id": judge_id,
            "shard": shard,
            "shards": shards,
            "outcome": result.outcome,
            "started_at": began,
            "seconds_spent": seconds,
            "model_calls": result.model_calls,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "model_seconds": result.model_seconds,
        }
    )
    return metrics_sink.ship_judge_metrics(
        row, judge_id=judge_id, shard=shard, out_dir=outcomes_dir(date)
    )


def _collect(hosted: Sequence[Tenant], *, date: DateStamp, state_dir: Path) -> int:
    """Append every row tonight's units filed into the council's own day file.

    What it reads is one directory a tenant, holding one file a unit, so it
    costs what the night fanned out to rather than what the archive has piled up
    (Guardrail #12).
    """
    recorded = [
        row
        for host in hosted
        for row in metrics_sink.shipped_rows(
            outcomes_dir(date), judge_id=host.judge_id, contract=CouncilShardOutcome
        )
    ]
    landed = ledger.append_council_shard_outcomes(state_dir, date, recorded)
    _log.info("the council recorded %d units of its own work on %s", landed, date)
    return landed
