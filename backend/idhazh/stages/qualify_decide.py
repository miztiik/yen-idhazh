"""Merge the shards, run the gates this run can ask, and say which number failed.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from idhazh import (
    assemble,
    config,
    ledger,
    run_context,
)
from idhazh.contracts.base import ServerJob, fit_field
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
from idhazh.evals import qualification_summary, qualify, validation
from idhazh.stages import common
from idhazh.stages.common import LOG
from idhazh.stages.decide import DECIDE_SHARD


def stage_qualify_decide(
    *, settings: config.Settings, date: str, run_id: str, job_budget_minutes: float, runner: str
) -> int:
    """Merge the shards, run the gates this run can ask, and say which number failed.

    Returns non-zero when a gate fails. The verdict is an ESCALATE either way -
    adopting a model changes a persisted contract - so this writes the evidence
    and stops rather than switching anything itself.

    Every gate is asked of every run, and a report missing one is refused.
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
        server=settings.models.summarize.server,
        run=settings.app.run,
        budget_=qualify.Budget(
            job_budget_minutes=job_budget_minutes,
            slowest_shard_seconds=max(shard.elapsed_seconds for shard in shards),
            slowest_item_seconds=max(
                (o.summarize_seconds for shard in shards for o in shard.observations), default=0.0
            ),
        ),
        required_canaries=len(sorted(common.CANARY_DIR.glob("*.json"))),
        thinking=settings.models.summarize.thinks,
    )
    shortfalls = qualify.corpus_shortfalls(
        frozen.items, summarize=settings.app.summarize, evaluation=evaluation
    )
    for shortfall in shortfalls:
        LOG.warning("the corpus is thinner than the config asks for: %s", shortfall)

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
        corpus_shortfalls=shortfalls,
        diagnostics=[
            *qualify.stratification(frozen.items, summarize=settings.app.summarize),
            *qualify.wording_spread(
                frozen.observations,
                sampling=settings.models.summarize.sampling,
                repeats=frozen.repeats,
            ),
            *qualify.diagnostics(frozen, evaluation=evaluation),
        ],
        qualified=not failed,
        detail=(
            "; ".join(f"{o.gate.value} measured {o.measured} against {o.threshold}" for o in failed)
            or f"every gate passed on {len(frozen.items)} frozen articles"
        ),
    )
    assemble.write_atomic(common.QUALIFICATION_ROOT / "report.json", report.to_json())
    assemble.write_atomic(
        common.QUALIFICATION_ROOT / "report.md",
        qualification_summary.render_report(report),
    )

    mean_hhem = (
        sum(score.hhem for score in frozen.scores) / len(frozen.scores) if frozen.scores else 0.0
    )
    # This dispatch's own segment, never the day file. Two candidates can be
    # dispatched at once and both judge the same day, so the run id in the
    # filename is what keeps their verdicts off one path. The state root is the
    # one the config names, so a qualification writes nothing a published day
    # is built from.
    ledger.write_segment(
        common.STATE_ROOT,
        ledger.SegmentLedger.VALIDATION,
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
                date=date,
                run_id=run_id,
                commit_sha=report.commit_sha,
                runner=fit_field(
                    runner, model=ValidationRow, field="runner", absent=validation.UNNAMED_RUNNER
                ),
                verdict=(
                    ValidationVerdict.QUALIFIED
                    if report.qualified
                    else ValidationVerdict.NOT_QUALIFIED
                ),
                detail=fit_field(
                    report.detail, model=ValidationRow, field="detail", absent=validation.UNSTATED
                ),
            )
        ],
        run_id=run_id,
        attempt=run_context.run_attempt(),
        job=ServerJob.DECIDE,
        shard=DECIDE_SHARD,
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
