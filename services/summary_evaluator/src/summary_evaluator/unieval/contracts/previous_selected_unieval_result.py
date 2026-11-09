"""Which applicable-score results preserve their original unmeasured errors?"""

from typing import Literal, Self

from pydantic import model_validator

from summary_evaluator.shared.contracts.base import Sha256, Uuid4
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.previous_unieval_result import PreviousUnievalError
from summary_evaluator.unieval.contracts.unieval_contract import (
    DIMENSIONS,
    RelevanceSkipReason,
    UnievalScoringContract,
)
from summary_evaluator.unieval.contracts.unieval_request import EffectiveUnievalControls
from summary_evaluator.unieval.contracts.unieval_result import (
    UnievalModelIdentity,
    UnievalScores,
    UnievalTimings,
    UnievalWork,
)


class PreviousSelectedUnievalResult(UnievalScoringContract):
    version: Literal["2026-11-08"]
    status: Literal["complete", "partial", "failed"]
    execution_id: Uuid4
    request_id: Uuid4 | None
    correlation_id: Uuid4 | None
    reference_summary_sha256: Sha256 | None
    relevance_skip_reason: RelevanceSkipReason | None
    model: UnievalModelIdentity | None
    worker: WorkerIdentity | None
    effective_settings: EffectiveUnievalControls | None
    scores: UnievalScores
    work: UnievalWork
    timings_ms: UnievalTimings
    errors: tuple[PreviousUnievalError, ...]

    @model_validator(mode="after")
    def require_observed_scores(self) -> Self:
        expected_skip: RelevanceSkipReason | None = None
        if self.effective_settings is not None:
            expected_skip = (
                "disabled" if not self.effective_settings.evaluate_relevance
                else "reference_not_supplied" if self.reference_summary_sha256 is None
                else None
            )
        if self.relevance_skip_reason != expected_skip:
            raise ValueError("A relevance skip requires the resolved selection and reference")
        if self.relevance_skip_reason is not None and (
            self.scores.relevance is not None
            or self.work.relevance.planned is not None
            or self.work.relevance.completed != 0
            or any(error.dimension == "relevance" for error in self.errors)
        ):
            raise ValueError("Skipped relevance cannot claim work, scores or failures")
        scores = [
            getattr(self.scores, dimension) for dimension in DIMENSIONS
            if dimension != "relevance" or self.relevance_skip_reason is None
        ]
        has_score = any(score is not None for score in scores)
        expected = (
            "complete"
            if all(score is not None for score in scores) and not self.errors
            else ("partial" if has_score else "failed")
        )
        if self.status != expected or (self.status != "complete" and not self.errors):
            raise ValueError("Status must describe all applicable dimensions and errors")
        if has_score and (
            self.model is None
            or self.worker is None
            or self.effective_settings is None
        ):
            raise ValueError("A score requires the observed model, worker and valid inputs")
        if self.scores.relevance is not None and self.reference_summary_sha256 is None:
            raise ValueError("A relevance score requires an independent reference")
        for dimension in DIMENSIONS:
            if getattr(self.scores, dimension) is not None:
                work = getattr(self.work, dimension)
                if work.planned is None or work.completed != work.planned:
                    raise ValueError("A score requires every planned comparison")
                if any(error.dimension == dimension for error in self.errors):
                    raise ValueError("A failed dimension cannot carry a final score")
        return self
