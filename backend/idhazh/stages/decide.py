"""Apply the Row #7 rule to whatever was measured, and record it.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is not a worker").
"""

from __future__ import annotations

from idhazh import (
    config,
)
from idhazh.contracts.validation_row import (
    ValidationVerdict,
)
from idhazh.evals import golden, validation, writer
from idhazh.stages import common
from idhazh.stages.common import LOG


def stage_decide(*, settings: config.Settings, date: str, commit_sha: str, runner: str) -> int:
    """Apply the Row #7 rule to whatever was measured, and record it.

    Returns non-zero on a switch. That verdict is an ESCALATE, and a green build
    would let it pass unread.
    """
    results = golden.results_in(common.VALIDATION_ROOT)
    if not results:
        raise SystemExit("no model was validated, so there is nothing to decide")

    incumbent_id = settings.models.summarize.id
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
        measured_on=date,
        commit_sha=commit_sha,
        runner=runner,
    )
    writer.append_validation(config.REPO_ROOT / golden.ledger_relpath(date), rows)

    LOG.info("verdict=%s winner=%s", decision.verdict.value, decision.winner)
    LOG.info("%s", decision.detail)
    if decision.verdict is ValidationVerdict.SWITCH_AND_PAUSE:
        LOG.error("ESCALATE: a model switch changes a persisted contract and needs sign-off")
        return 2
    return 0
