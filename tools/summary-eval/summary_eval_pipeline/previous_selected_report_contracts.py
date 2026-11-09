"""Which selected-score reports preserve their original phases and receipt bytes?"""

from typing import Literal, Self

from pydantic import ConfigDict, ValidationInfo, model_validator
from summary_evaluator.shared.contracts.base import OutcomeStatus

from .contracts import PipelineError
from .previous_selected_phase_contracts import PhaseEvidence
from .run_contracts import GenerationReceipt, PreparedRun
from .scorer_evidence import EvidenceContract


class PipelineEvidence(EvidenceContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": "2026-11-08",
            "readCompatibility": "read frozen shared and independent reports by exact version",
            "changelog": [
                {"version": "2026-11-08", "change": "Complete and disclose applicable scores."},
                {"version": "2026-11-07", "change": "Keep independent maintained scorer APIs."},
            ],
        }
    )
    version: Literal["2026-11-08"]
    status: OutcomeStatus
    prepared: PreparedRun | None
    generation: GenerationReceipt | None
    generation_phase: PhaseEvidence | None
    evaluation_phase: PhaseEvidence | None
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_same_run(self, info: ValidationInfo) -> Self:
        generated, phase, evaluated = (
            self.generation, self.generation_phase, self.evaluation_phase
        )
        if generated is not None and (
            self.prepared is None or self.prepared.status != "complete"
            or generated.run != self.prepared.run
            or generated.selected != self.prepared.selected
            or generated.source_sha256 != self.prepared.source_sha256
            or generated.reference_summary_sha256 != self.prepared.reference_summary_sha256
            or generated.evaluate_relevance != self.prepared.evaluate_relevance
        ):
            raise ValueError("Generation requires this run's completed preparation")
        if self.prepared is not None and self.prepared.status != "complete" and (
            generated is not None or phase is not None or evaluated is not None
        ):
            raise ValueError("Incomplete preparation cannot claim model phases")
        for observed, name in ((phase, "generation"), (evaluated, "evaluation")):
            if observed is not None and (
                observed.phase != name
                or (
                    self.prepared is None
                    or observed.run != self.prepared.run
                    or observed.reference_summary_sha256 != self.prepared.reference_summary_sha256
                    or observed.evaluate_relevance != self.prepared.evaluate_relevance
                )
            ):
                raise ValueError("Every phase must retain this run and independent reference")
        hashes = {
            observed.generation_sha256 for observed in (phase, evaluated)
            if observed is not None and observed.generation_sha256 is not None
        }
        saved_hash = (
            info.context.get("generation_sha256") if isinstance(info.context, dict) else None
        )
        if len(hashes) > 1 or (saved_hash is not None and hashes and hashes != {saved_hash}):
            raise ValueError("Every phase must retain the exact saved generation bytes")
        if evaluated is not None and (
            evaluated.evaluation is not None or evaluated.unieval is not None
        ) and (
            generated is None or generated.status != "complete"
            or phase is None or phase.shutdown.llama_stopped is not True
            or phase.scorer_apis
        ):
            raise ValueError("Scoring requires the saved answer and confirmed native shutdown")
        score = evaluated is not None and (
            (evaluated.evaluation is not None and evaluated.evaluation.hhem is not None)
            or (
                evaluated.unieval is not None
                and any(
                    value is not None for value in evaluated.unieval.scores.model_dump().values()
                )
            )
        )
        complete = (
            generated is not None and generated.status == "complete"
            and phase is not None and phase.status == "complete"
            and evaluated is not None and evaluated.status == "complete"
            and not self.errors
        )
        if self.status != ("complete" if complete else "partial" if score else "failed"):
            raise ValueError("Combined status must retain every phase failure")
        return self
