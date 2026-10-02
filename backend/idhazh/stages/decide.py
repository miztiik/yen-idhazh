"""Apply the Row #7 rule to whatever was measured, and record it.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from typing import Final

from idhazh import (
    config,
    ledger,
    run_context,
)
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.validation_row import (
    ValidationVerdict,
)
from idhazh.evals import golden, validation
from idhazh.stages import common
from idhazh.stages.common import LOG

#: The decider runs once for a whole comparison, so it is shard 0 of one.
DECIDE_SHARD = 0

#: The name the verdict file this stage writes through the ledger door carries
#: as its producer: this module's own dotted name, less the package.
PRODUCER: Final = __name__.partition(".")[2]


def stage_decide(
    *, settings: config.Settings, date: str, run_id: str, commit_sha: str, runner: str
) -> int:
    """Apply the Row #7 rule to whatever was measured, and record it.

    Returns non-zero on a switch. That verdict is an ESCALATE, and a green build
    would let it pass unread.
    """
    results = golden.results_in(common.VALIDATION_ROOT)
    if not results:
        raise SystemExit("no model was validated, so there is nothing to decide")

    incumbent_id = settings.models.summarizer.id
    measurements = [
        validation.Measurement(
            model_id=result.model_id,
            leaderboard_hhem=result.leaderboard_hhem,
            measured_hhem=result.measured_hhem,
            articles=result.articles,
        )
        for result in results
    ]
    incumbent = next((m for m in measurements if m.model_id == incumbent_id), None)
    if incumbent is None:
        raise SystemExit(f"the configured model {incumbent_id} was never validated")
    challengers = [m for m in measurements if m.model_id != incumbent_id]

    decision = validation.decide(incumbent, challengers, evaluation=settings.app.evaluation)
    rows = validation.to_rows(
        incumbent,
        challengers,
        decision,
        date=date,
        run_id=run_id,
        commit_sha=commit_sha,
        runner=runner,
    )
    # Filed through the ledger door as this execution's own work unit, so two
    # comparisons judged on one date never replace each other. The state root is
    # the one the config names - so a trial run leaves nothing in the tree a
    # published day is built from.
    ledger.persist(
        common.STATE_ROOT,
        rows,
        ledger=LedgerName.CANDIDATE_MODELS,
        covers=date,
        identity=WriterIdentity(
            run_id=run_id,
            attempt=run_context.run_attempt(),
            job=ServerJob.DECIDE,
            shard=DECIDE_SHARD,
            producer=PRODUCER,
            git_sha=commit_sha,
        ),
    )

    LOG.info("verdict=%s winner=%s", decision.verdict.value, decision.winner)
    LOG.info("%s", decision.detail)
    if decision.verdict is ValidationVerdict.SWITCH_AND_PAUSE:
        LOG.error("ESCALATE: a model switch changes a persisted contract and needs sign-off")
        return 2
    return 0
