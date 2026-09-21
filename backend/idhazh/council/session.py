"""What does the council do with the tenants it is hosting tonight?

Three units of work, in the order a night runs them: pick the work, run one
shard of it, and settle what came back. Each one resolves the slugs the config
names and calls the matching member on every tenant it got.

Nothing here reads a result by name. What a tenant hands back crosses whole, so
a venue hosting a judge with a funnel and a judge with none runs the same code
for both.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from idhazh import config
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council.deadline import run_shard_under_the_clock
from idhazh.council.registry import tenant, tenants
from idhazh.council.tenancy import ShardResult, Tenant

_log: Final = logging.getLogger(__name__)

#: Where one night's work lands before a later job collects it. The council
#: names the root because the council is what carries it between jobs as an
#: artifact; what a tenant puts inside it is the tenant's own business.
COUNCIL_ROOT_RELPATH: Final = "backend/var/council"

COUNCIL_ROOT: Final = config.REPO_ROOT / COUNCIL_ROOT_RELPATH

#: The two things the venue moves between jobs: what a date's work was picked
#: from, and what the units measured on their way out.
SELECTION_DIRNAME: Final = "selection"

METRICS_DIRNAME: Final = "metrics"


def scratch_root(date: DateStamp) -> Path:
    """The directory one date's work is written under, on whichever runner runs it."""
    return COUNCIL_ROOT / date


def prepare(council: CouncilConfig, *, date: DateStamp, run_id: RunId) -> tuple[ShardResult, ...]:
    """Pick the work, once a date, before any shard runs.

    In the order the config names the tenants, because a venue that ran them in
    an order it never declared could not be re-run into the same state.
    """
    return tuple(
        _reported("prepare", date, host.judge_id, host.prepare(date=date, run_id=run_id))
        for host in _hosted(council, date)
    )


def settle(council: CouncilConfig, *, date: DateStamp, run_id: RunId) -> tuple[ShardResult, ...]:
    """Count, fit, or do nothing, once a date after every shard has reported."""
    return tuple(
        _reported("settle", date, host.judge_id, host.settle(date=date, run_id=run_id))
        for host in _hosted(council, date)
    )


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
    return _reported(
        f"shard {shard} of {shards}",
        date,
        slug,
        run_shard_under_the_clock(
            tenant(slug),
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


def _reported(unit: str, date: DateStamp, slug: str, result: ShardResult) -> ShardResult:
    _log.info("council %s for %s on %s ended %s", unit, slug, date, result.outcome.value)
    return result
