"""Which original four-score results remain readable without changing their meaning?"""

from typing import Literal, Self

from pydantic import model_validator

from summary_evaluator.shared.contracts.base import (
    Count,
    PositiveCount,
    Sha256,
    Uuid4,
)
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode, ErrorPolicy
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_contract import (
    DIMENSIONS,
    Dimension,
    SourceMode,
    UnievalContract,
)
from summary_evaluator.unieval.contracts.unieval_result import (
    UnievalModelIdentity,
    UnievalScores,
    UnievalTimings,
    UnievalWork,
)

PreviousUnievalErrorCode = ErrorCode | Literal[
    "SUMMARY_SENTENCE_TOO_LONG",
    "COHERENCE_INPUT_TOO_LONG",
    "RELEVANCE_INPUT_TOO_LONG",
    "CONSISTENCY_INPUT_TOO_LONG",
    "COMPARISON_LIMIT_EXCEEDED",
    "TOKENIZER_FAILED",
]
PREVIOUS_POLICIES: dict[PreviousUnievalErrorCode, ErrorPolicy] = {
    code: policy for code, policy in ERROR_POLICIES.items()
}
PREVIOUS_POLICIES.update({
    "SUMMARY_SENTENCE_TOO_LONG": ErrorPolicy(
        400, "A complete summary sentence exceeds the configured prompt allowance."
    ),
    "COHERENCE_INPUT_TOO_LONG": ErrorPolicy(
        400, "The complete source and summary exceed the coherence prompt allowance."
    ),
    "RELEVANCE_INPUT_TOO_LONG": ErrorPolicy(
        400, "The complete reference and summary exceed the relevance prompt allowance."
    ),
    "CONSISTENCY_INPUT_TOO_LONG": ErrorPolicy(
        400, "The complete consistency prompt exceeds the configured allowance."
    ),
    "COMPARISON_LIMIT_EXCEEDED": ErrorPolicy(
        400, "The evaluation exceeds the configured comparison allowance."
    ),
    "TOKENIZER_FAILED": ErrorPolicy(
        500, "The declared local text resources could not be used."
    ),
})


class PreviousUnievalError(UnievalContract):
    code: PreviousUnievalErrorCode
    dimension: Dimension | None
    index: Count | None
    message: str

    @model_validator(mode="after")
    def require_declared_message(self) -> Self:
        if self.message != PREVIOUS_POLICIES[self.code].message:
            raise ValueError("The error requires its fixed safe message")
        return self


class PreviousUnievalControls(UnievalContract):
    consistency_source_mode: SourceMode
    max_input_tokens: PositiveCount
    source_window_tokens: PositiveCount
    source_overlap_tokens: Count
    max_source_windows: PositiveCount
    max_comparisons: PositiveCount

    @model_validator(mode="after")
    def require_finite_geometry(self) -> Self:
        if self.source_overlap_tokens >= self.source_window_tokens:
            raise ValueError("Source overlap must be smaller than its target window")
        return self


class PreviousEffectiveUnievalControls(PreviousUnievalControls):
    source_budget_tokens: PositiveCount | None


class PreviousUnievalResult(UnievalContract):
    version: Literal["2026-11-04"]
    status: Literal["complete", "partial", "failed"]
    execution_id: Uuid4
    request_id: Uuid4 | None
    correlation_id: Uuid4 | None
    reference_summary_sha256: Sha256 | None
    model: UnievalModelIdentity | None
    worker: WorkerIdentity | None
    effective_settings: PreviousEffectiveUnievalControls | None
    scores: UnievalScores
    work: UnievalWork
    timings_ms: UnievalTimings
    errors: tuple[PreviousUnievalError, ...]

    @model_validator(mode="after")
    def require_observed_scores(self) -> Self:
        scores = [getattr(self.scores, dimension) for dimension in DIMENSIONS]
        has_score = any(score is not None for score in scores)
        expected = (
            "complete"
            if all(score is not None for score in scores) and not self.errors
            else ("partial" if has_score else "failed")
        )
        if self.status != expected or (self.status != "complete" and not self.errors):
            raise ValueError("Status must describe all four actual dimensions and errors")
        if has_score and (
            self.model is None
            or self.worker is None
            or self.reference_summary_sha256 is None
            or self.effective_settings is None
        ):
            raise ValueError("A score requires the observed model, worker and valid inputs")
        for dimension in DIMENSIONS:
            if getattr(self.scores, dimension) is not None:
                work = getattr(self.work, dimension)
                if work.planned is None or work.completed != work.planned:
                    raise ValueError("A score requires every planned comparison")
                if any(error.dimension == dimension for error in self.errors):
                    raise ValueError("A failed dimension cannot carry a final score")
        return self
