"""When must one shard stop, and how does the tenant learn it?

The council owns both clocks because the council owns the runner: the job
timeout, the checkout, the install and the weights restore are the venue's, and
no tenant can see any of them. So what crosses to a tenant is one instant rather
than two knobs. A tenant handed an instant needs no config block and no config
reader to stop on time, which is what lets a judge with neither still be
stopped.

The instant is a `time.monotonic()` reading and not a clock time, so a host
whose wall clock moves cannot shorten or extend a shard.

**Nothing here checks it.** Only the tenant knows what a unit of work is and
where stopping leaves a readable result, so the council hands the instant over
and reads back whatever outcome the tenant reports.

This module takes the council's own knob block rather than the whole settings
object, so it reaches no config block a judge owns.
"""

from __future__ import annotations

from typing import Final

from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council.tenancy import ShardResult, Tenant

#: A unit conversion, not a knob. Both clocks are minutes because a person sets
#: them, and the deadline is seconds because the monotonic clock is.
SECONDS_A_MINUTE: Final = 60


def compute_shard_deadline(council: CouncilConfig, *, started: float) -> float:
    """The monotonic instant a shard must stop by.

    `started` is when the shard's own process began, and the caller reads it
    because only the process knows: the job's clock started before a checkout, an
    install and a weights restore that this reading is not about.

    A margin at least as long as the bound leaves the shard no time at all, which
    is what a margin that large means. The floor is what stops it reading as a
    deadline that had already passed before the shard began.
    """
    minutes = max(council.shard_timeout_minutes - council.shard_wrap_up_minutes, 0)
    return started + minutes * SECONDS_A_MINUTE


def run_shard_under_the_clock(
    tenant: Tenant,
    *,
    date: DateStamp,
    run_id: RunId,
    shard: int,
    shards: int,
    council: CouncilConfig,
    started: float,
) -> ShardResult:
    """Run one shard of a tenant's work under the council's own clock.

    The one place the venue's clock meets a tenant. The tenant is handed the
    instant and nothing else about it, and what comes back is returned whole: the
    council files the outcome the tenant reported and never infers one from its
    own clock.
    """
    return tenant.run_shard(
        date=date,
        run_id=run_id,
        shard=shard,
        shards=shards,
        deadline=compute_shard_deadline(council, started=started),
    )
