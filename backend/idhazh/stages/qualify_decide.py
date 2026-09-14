"""Merge the shards, run the eleven gates, and say which number failed.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from idhazh import (
    assemble,
    config,
)
from idhazh.contracts.qualification import (
    GateStatus,
    QualificationReport,
    QualificationShard,
    corpus_digest,
)
from idhazh.contracts.validation_row import (
    LeaderboardProvenance,
    ValidationRow,
    ValidationVerdict,
)
from idhazh.evals import golden, qualify, writer
from idhazh.stages import common
from idhazh.stages.common import LOG


def stage_qualify_decide(
    *, settings: config.Settings, date: str, job_budget_minutes: float, runner: str
) -> int:
    """Merge the shards, run the eleven gates, and say which number failed.

    Returns non-zero when a gate fails. The verdict is an ESCALATE either way -
    adopting a model changes a persisted contract - so this writes the evidence
    and stops rather than switching anything itself.
    """
    paths = sorted(common.QUALIFICATION_ROOT.glob("shard-*.json"))
    shards = [QualificationShard.read(path) for path in paths]
    if not shards:
        raise SystemExit("no qualification shard was written, so there is nothing to decide")

    evaluation = settings.app.evaluation
    frozen, outcomes = qualify.gates(
        shards,
        evaluation=evaluation,
        summarize=settings.app.summarize,
        inference=settings.models.summarize.inference,
        run=settings.app.run,
        budget_=qualify.Budget(
            job_budget_minutes=job_budget_minutes,
            slowest_shard_seconds=max(shard.elapsed_seconds for shard in shards),
            slowest_item_seconds=max(
                (o.summarize_seconds for shard in shards for o in shard.observations), default=0.0
            ),
        ),
        required_canaries=len(sorted(common.CANARY_DIR.glob("*.json"))),
        turns=settings.models.summarize.turns,
    )
    shortfalls = qualify.corpus_shortfalls(frozen.items, summarize=settings.app.summarize)
    if shortfalls:
        # Not a gate. These describe the measuring stick, and a thin corpus is a
        # run to repeat rather than a model to reject.
        for shortfall in shortfalls:
            LOG.error("corpus is not adequate: %s", shortfall)
        raise SystemExit("the frozen corpus does not meet the registered definition")

    failed = [outcome for outcome in outcomes if outcome.status is GateStatus.FAILED]
    report = QualificationReport(
        version=QualificationReport.schema_version(),
        date=date,
        commit_sha=shards[0].commit_sha,
        runner=runner,
        candidate=shards[0].candidate,
        scorer=shards[0].scorer,
        corpus_digest=corpus_digest(frozen.items),
        corpus_items=len(frozen.items),
        planned=frozen.planned,
        repeats=frozen.repeats,
        scored=len(frozen.scores),
        gates=outcomes,
        diagnostics=[
            *qualify.stratification(frozen.items, summarize=settings.app.summarize),
            *qualify.diagnostics(frozen, evaluation=evaluation),
        ],
        qualified=not failed,
        detail=(
            "; ".join(f"{o.gate.value} measured {o.measured} against {o.threshold}" for o in failed)
            or f"every gate passed on {len(frozen.items)} frozen articles"
        ),
    )
    assemble.write_atomic(common.QUALIFICATION_ROOT / "report.json", report.to_json())

    mean_hhem = (
        sum(score.hhem for score in frozen.scores) / len(frozen.scores) if frozen.scores else 0.0
    )
    writer.append_validation(
        config.REPO_ROOT / golden.ledger_relpath(date),
        [
            ValidationRow(
                version=ValidationRow.schema_version(),
                model_id=report.candidate.model_id,
                is_incumbent=report.candidate.model_id == settings.models.summarize.id,
                selected=report.qualified,
                leaderboard_hhem=None,
                leaderboard_provenance=LeaderboardProvenance.NOT_REPORTED,
                measured_hhem=mean_hhem,
                articles=max(len(frozen.scores), 1),
                measured_on=date,
                commit_sha=report.commit_sha,
                runner=runner,
                verdict=(
                    ValidationVerdict.QUALIFIED
                    if report.qualified
                    else ValidationVerdict.NOT_QUALIFIED
                ),
                detail=report.detail,
            )
        ],
    )

    for outcome in outcomes:
        LOG.info(
            "gate %s %s measured=%s threshold=%s source=%s",
            outcome.gate.value,
            outcome.status.value,
            outcome.measured,
            outcome.threshold,
            outcome.source,
        )
    for diagnostic in report.diagnostics:
        LOG.info("diagnostic %s=%s n=%s", diagnostic.name, diagnostic.value, diagnostic.denominator)
    if failed:
        LOG.error("ESCALATE: %s", report.detail)
        return 2
    LOG.info("qualified model=%s corpus=%s", report.candidate.model_id, report.corpus_digest[:12])
    return 0
