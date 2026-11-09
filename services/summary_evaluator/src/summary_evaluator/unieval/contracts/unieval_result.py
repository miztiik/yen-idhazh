"""Which completed dimensions and source-work evidence may leave the UniEval worker?"""

from typing import Literal, Self

from pydantic import Field, model_validator

from summary_evaluator.shared.contracts.base import (
    CommitId,
    Count,
    Milliseconds,
    ModelReference,
    NonblankText,
    PositiveCount,
    Score,
    Sha256,
    Uuid4,
)
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_contract import (
    DIMENSIONS,
    RelevanceSkipReason,
    UnievalContract,
    UnievalResultContract,
    UnievalResultVersion,
    UnievalVersion,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError, UnievalHealthErrorCode
from summary_evaluator.unieval.contracts.unieval_request import EffectiveUnievalControls


class UnievalRuntimeVersions(UnievalContract):
    python: NonblankText = Field(max_length=128)
    pytorch: NonblankText = Field(max_length=128)
    transformers: NonblankText = Field(max_length=128)
    tokenizers: NonblankText = Field(max_length=128)
    nltk: NonblankText = Field(max_length=128)


class UnievalModelIdentity(UnievalContract):
    reference: ModelReference
    configured_revision: CommitId
    loaded_revision: CommitId
    tokenizer_revision: CommitId
    reference_code_revision: CommitId
    runtime_versions: UnievalRuntimeVersions

    @model_validator(mode="after")
    def require_loaded_selection(self) -> Self:
        if self.configured_revision != self.loaded_revision:
            raise ValueError("Loaded weights must match the configured revision")
        if self.tokenizer_revision != self.loaded_revision:
            raise ValueError("The tokenizer must come from the selected snapshot")
        return self


class SourceSpan(UnievalContract):
    start: Count
    end: PositiveCount

    @model_validator(mode="after")
    def require_forward_span(self) -> Self:
        if self.start >= self.end:
            raise ValueError("Source spans must be nonempty and forward")
        return self


class DimensionWork(UnievalContract):
    planned: PositiveCount | None = None
    completed: Count = 0

    @model_validator(mode="after")
    def require_complete_plan(self) -> Self:
        if self.completed and self.planned is None:
            raise ValueError("Completed work requires a plan")
        if self.planned is not None and self.completed > self.planned:
            raise ValueError("Completed work cannot exceed its plan")
        return self


class UnievalWork(UnievalContract):
    fluency: DimensionWork = Field(default_factory=DimensionWork)
    coherence: DimensionWork = Field(default_factory=DimensionWork)
    consistency: DimensionWork = Field(default_factory=DimensionWork)
    relevance: DimensionWork = Field(default_factory=DimensionWork)
    summary_sentences: PositiveCount | None = None
    source_characters: PositiveCount | None = None
    source_spans: tuple[SourceSpan, ...] = ()

    @model_validator(mode="after")
    def require_source_coverage(self) -> Self:
        if self.source_spans:
            if self.source_characters is None or self.source_spans[0].start != 0:
                raise ValueError("A source plan must begin at the source start")
            end = 0
            start = -1
            for span in self.source_spans:
                if span.start > end or span.start <= start or span.end <= end:
                    raise ValueError("Source spans must advance without a gap")
                start, end = span.start, span.end
            if end != self.source_characters:
                raise ValueError("A source plan must cover the complete source")
        return self

    def require_refusal_index(self, error: UnievalError) -> None:
        if error.input_tokens is None:
            return
        comparisons: int | None = 1
        if error.dimension == "fluency" or (
            error.dimension == "consistency" and error.code == "SUMMARY_SENTENCE_TOO_LONG"
        ):
            comparisons = self.summary_sentences
        elif error.dimension == "consistency":
            comparisons = (
                self.summary_sentences * len(self.source_spans)
                if self.summary_sentences is not None else None
            )
        if (
            error.dimension is None
            or error.index is None
            or comparisons is None
            or error.index >= comparisons
        ):
            raise ValueError("A measured refusal requires its actual comparison index")


class UnievalScores(UnievalContract):
    fluency: Score | None = None
    coherence: Score | None = None
    consistency: Score | None = None
    relevance: Score | None = None


class UnievalTimings(UnievalContract):
    queue_wait: Milliseconds | None = None
    scoring: Milliseconds | None = None
    total: Milliseconds | None = None


class UnievalResult(UnievalResultContract):
    version: UnievalResultVersion
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
    errors: tuple[UnievalError, ...]

    @model_validator(mode="after")
    def require_observed_scores(self) -> Self:
        if any(
            error.code == "MODEL_INPUT_TOO_LONG"
            or (
                error.allowed_tokens is not None
                and (
                    self.effective_settings is None
                    or error.allowed_tokens != self.effective_settings.max_input_tokens
                )
            )
            for error in self.errors
        ):
            raise ValueError("Input refusals require public dimensions and resolved allowances")
        if any(error.code == "WINDOW_BUDGET_INSUFFICIENT" for error in self.errors) and (
            self.effective_settings is None
            or self.effective_settings.consistency_source_mode != "all_source_windows"
            or self.work.consistency.planned is not None
            or self.work.source_spans
        ):
            raise ValueError("Window geometry requires a refused explicit source-window plan")
        for error in self.errors:
            self.work.require_refusal_index(error)
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


class UnievalHealth(UnievalContract):
    version: UnievalVersion
    service_instance_id: Uuid4
    status: Literal["loading", "ready", "stopping", "failed"]
    model: UnievalModelIdentity | None
    worker: WorkerIdentity | None
    queue_depth: Count
    queue_capacity: PositiveCount
    failure_code: UnievalHealthErrorCode | None

    @model_validator(mode="after")
    def require_ready_identity(self) -> Self:
        if self.queue_depth > self.queue_capacity:
            raise ValueError("Queue depth cannot exceed its configured capacity")
        if self.status == "ready" and (
            self.model is None or self.worker is None or self.failure_code is not None
        ):
            raise ValueError("Ready requires an observed loaded model and worker")
        if self.status == "failed" and self.failure_code is None:
            raise ValueError("Failed health requires a reason")
        return self
