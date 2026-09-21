"""Does a shard learn when to stop from a council with no judge in it?

Every tenant in this file is declared here, so the venue's clock is gated
without a judge in the repository and without a judge's test module. Nothing
here imports `idhazh.similarity` or any judge contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from conftest import CONFIG_DIR

from idhazh import config
from idhazh.contracts.base import DateStamp, RunId
from idhazh.contracts.council_shard_outcome import ShardOutcome
from idhazh.contracts.knobs.council import CouncilConfig
from idhazh.council.deadline import (
    SECONDS_A_MINUTE,
    compute_shard_deadline,
    run_shard_under_the_clock,
)
from idhazh.council.tenancy import ShardResult, Tenant

#: The date and run the fake shards are asked about. Any valid pair does: this
#: module is about the clock, and the tenant passes both straight through.
A_DATE: DateStamp = "2026-09-20"
A_RUN: RunId = "2026-09-20-1"


@dataclass(frozen=True)
class StopwatchTenant:
    """A tenant that does no work and remembers the instant it was handed.

    A fixture rather than a mock (Guardrail #7). It stands in for nobody: it
    records the one value under test and reports the outcome it was built with,
    so a council that quietly computed a second deadline of its own would fail
    here rather than pass.
    """

    outcome: ShardOutcome = ShardOutcome.STOPPED_ON_DEADLINE
    handed: list[float] = field(default_factory=list)

    judge_id: str = "stopwatch-tenant"
    shard_count: int = 1
    committed_paths: tuple[str, ...] = ()

    def nights_outstanding(self, *, window: tuple[DateStamp, ...]) -> tuple[DateStamp, ...]:
        """It is behind on nothing: it counts nothing."""
        return ()

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
        self.handed.append(deadline)
        return ShardResult(outcome=self.outcome)

    def settle(self, *, date: DateStamp, run_id: RunId) -> ShardResult:
        return ShardResult(outcome=ShardOutcome.NOTHING_TO_DO)


def _committed_clocks() -> CouncilConfig:
    """The council block as the repository commits it, read inside each test."""
    return config.load(CONFIG_DIR).app.council


def test_the_deadline_leaves_the_margin_the_council_asked_for() -> None:
    """The deadline sits one margin before the instant the platform would kill the job.

    The job's clock and the process's clock are not the same clock. The platform
    starts counting at provisioning and the process starts after a checkout, a
    weights restore, a checksum verify and a health poll, so the kill lands one
    preamble later than `started` plus the bound. Driven from whatever the
    committed block says rather than from a number written here, so raising any
    of the three clocks moves the deadline and never this test.
    """
    council = _committed_clocks()
    started = 1_000.0
    preamble = council.shard_preamble_minutes * SECONDS_A_MINUTE
    killed_at = started - preamble + council.shard_timeout_minutes * SECONDS_A_MINUTE

    deadline = compute_shard_deadline(council, started=started)

    assert killed_at - deadline == council.shard_wrap_up_minutes * SECONDS_A_MINUTE


def test_the_window_shrinks_by_what_the_job_spent_before_the_process_began() -> None:
    """The defect the preamble exists for, held in the direction it failed.

    Subtracting only the reserve gave a deadline that landed AFTER the
    platform's own kill whenever the model was slow to load - so on the one
    night the reserve was for, it protected nothing. The two clocks below differ
    only in the preamble, and the window has to differ by exactly that.
    """
    started = 1_000.0
    short = CouncilConfig(
        shard_timeout_minutes=200, shard_preamble_minutes=0, shard_wrap_up_minutes=12
    )
    long = CouncilConfig(
        shard_timeout_minutes=200, shard_preamble_minutes=13, shard_wrap_up_minutes=12
    )

    lost = compute_shard_deadline(short, started=started) - compute_shard_deadline(
        long, started=started
    )

    assert lost == 13 * SECONDS_A_MINUTE


def test_a_margin_as_long_as_the_bound_leaves_no_time_at_all() -> None:
    """The floor, and what it is for.

    Without it a preamble and a margin longer than the bound give a deadline
    behind the start instant, which reads as a shard that ran out of clock
    before it began. With it the shard has nothing left, which is what two
    clocks that large mean.
    """
    started = 1_000.0
    exact = CouncilConfig(
        shard_timeout_minutes=30, shard_preamble_minutes=0, shard_wrap_up_minutes=30
    )
    beyond = CouncilConfig(
        shard_timeout_minutes=30, shard_preamble_minutes=10, shard_wrap_up_minutes=90
    )

    assert compute_shard_deadline(exact, started=started) == started
    assert compute_shard_deadline(beyond, started=started) == started


def test_the_tenant_is_handed_the_instant_the_council_computed() -> None:
    """One instant crosses, and it is the council's own.

    The tenant is handed no knob and reads no config block, which is what makes a
    judge replaceable here by four lines that count what they were given.
    """
    council = _committed_clocks()
    tenant = StopwatchTenant()
    started = 4_242.0

    run_shard_under_the_clock(
        tenant,
        date=A_DATE,
        run_id=A_RUN,
        shard=2,
        shards=4,
        council=council,
        started=started,
    )

    assert tenant.handed == [compute_shard_deadline(council, started=started)]


@pytest.mark.parametrize(
    "reported",
    [ShardOutcome.COMPLETED, ShardOutcome.STOPPED_ON_DEADLINE, ShardOutcome.NOTHING_TO_DO],
)
def test_the_council_files_the_outcome_the_tenant_reported(reported: ShardOutcome) -> None:
    """The council checks the clock it set for nobody, including itself.

    The start instant here is far enough in the past that the deadline has long
    gone, and the outcome that comes back is still the tenant's. Only the tenant
    knows whether a half-finished unit was abandoned or never started, so a
    council that read its own clock would file the wrong answer on every shard
    that finished early.
    """
    tenant = StopwatchTenant(outcome=reported)

    result = run_shard_under_the_clock(
        tenant,
        date=A_DATE,
        run_id=A_RUN,
        shard=0,
        shards=1,
        council=_committed_clocks(),
        started=-1_000_000.0,
    )

    assert result.outcome is reported


def test_the_stopwatch_tenant_is_a_tenant() -> None:
    """A structural protocol is satisfied by shape, and mypy is what checks it.

    The assignment is the assertion. Without it the fake could drift out of the
    protocol and every test above would keep passing against a shape no judge
    could present.
    """
    tenant: Tenant = StopwatchTenant()

    assert tenant.judge_id == "stopwatch-tenant"
    assert tenant.nights_outstanding(window=(A_DATE,)) == ()
