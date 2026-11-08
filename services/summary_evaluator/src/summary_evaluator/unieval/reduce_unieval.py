"""How does parent-owned progress become only fully completed UniEval scores?"""

import hashlib
import time
from dataclasses import dataclass, field

from local_api_host.propagate_trace_context import OperationMetadata, create_root_operation

from summary_evaluator.shared.contracts.base import OutcomeStatus
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.contracts.unieval_contract import (
    DIMENSIONS,
    UNIEVAL_SCORING_VERSION,
    Dimension,
    RelevanceSkipReason,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_request import (
    EffectiveUnievalControls,
    UnievalRequest,
)
from summary_evaluator.unieval.contracts.unieval_result import (
    DimensionWork,
    UnievalModelIdentity,
    UnievalResult,
    UnievalScores,
    UnievalTimings,
    UnievalWork,
)
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    RequestPacket,
    UnievalPrediction,
    UnievalPrepared,
)
from summary_evaluator.unieval.fail_unieval import UnievalFailure
from summary_evaluator.unieval.resolve_unieval_selection import resolve_unieval_selection


@dataclass
class UnievalState:
    operation_metadata: OperationMetadata = field(default_factory=create_root_operation)
    execution_id: str = field(default_factory=create_execution_id)
    received_at: float = field(default_factory=time.monotonic)
    request: UnievalRequest | None = None
    reference_hash: str | None = None
    relevance_skip_reason: RelevanceSkipReason | None = None
    model: UnievalModelIdentity | None = None
    worker: WorkerIdentity | None = None
    effective: EffectiveUnievalControls | None = None
    work: UnievalWork = field(default_factory=UnievalWork)
    values: dict[Dimension, list[float]] = field(default_factory=dict)
    processed: dict[Dimension, int] = field(default_factory=dict)
    scores: UnievalScores = field(default_factory=UnievalScores)
    errors: list[UnievalError] = field(default_factory=list)
    queue_ms: float | None = None
    scoring_ms: float | None = None
    prepared: bool = False
    queue_operation: OperationMetadata | None = None
    evaluation_operation: OperationMetadata | None = None

    def set_request(self, request: UnievalRequest) -> None:
        self.request = request.model_copy(
            update={
                "request_id": request.request_id or create_execution_id(),
                "correlation_id": request.correlation_id or create_execution_id(),
            }
        )
        self.reference_hash = (
            hashlib.sha256(request.reference_summary_text.encode("utf-8")).hexdigest()
            if request.reference_summary_text is not None else None
        )

    def accept_plan(self, packet: UnievalPrepared, settings: UnievalSettings) -> None:
        self.require_issued_operation(packet)
        if self.prepared or self.request is None:
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        controls, relevance_skip_reason = resolve_unieval_selection(
            self.request, settings.scoring
        )
        if (
            packet.effective_settings.model_dump(exclude={"source_budget_tokens"})
            != controls.model_dump()
            or packet.relevance_skip_reason != relevance_skip_reason
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        work = packet.work
        total = 0
        for dimension in DIMENSIONS:
            dimension_work = getattr(work, dimension)
            if dimension_work.completed:
                raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
            planned = dimension_work.planned
            if dimension == "relevance" and relevance_skip_reason is not None:
                if planned is not None or any(
                    error.dimension == "relevance" for error in packet.errors
                ):
                    raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
                continue
            if planned is None:
                if not any(error.dimension in (dimension, None) for error in packet.errors):
                    raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
                continue
            expected = (
                work.summary_sentences
                if dimension == "fluency"
                else (work.summary_sentences or 0) * len(work.source_spans)
                if dimension == "consistency"
                else 1
            )
            if planned != expected:
                raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
            total += planned
        if (
            total > settings.scoring.max_comparisons
            or len(work.source_spans) > settings.scoring.max_source_windows
            or (
                work.source_characters is not None
                and work.source_characters != len(self.request.source_text)
            )
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        if (
            packet.effective_settings.consistency_source_mode == "full_source_prompt"
            and work.consistency.planned is not None
            and len(work.source_spans) != 1
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        if packet.effective_settings.source_budget_tokens is not None and (
            packet.effective_settings.source_budget_tokens > settings.scoring.source_window_tokens
            or packet.effective_settings.source_budget_tokens
            <= settings.scoring.source_overlap_tokens
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        self.work, self.effective = work, packet.effective_settings
        self.relevance_skip_reason = relevance_skip_reason
        self.errors.extend(packet.errors)
        self.values = {dimension: [] for dimension in DIMENSIONS}
        self.processed = dict.fromkeys(DIMENSIONS, 0)
        self.prepared = True

    def accept_prediction(self, packet: UnievalPrediction) -> None:
        self.require_issued_operation(packet)
        dimension = packet.dimension
        work = getattr(self.work, dimension)
        if (
            not self.prepared
            or work.planned is None
            or packet.index != self.processed[dimension]
            or packet.index >= work.planned
            or (packet.score is None) == (packet.error is None)
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        expected_sentence: int | None = None
        expected_source: int | None = None
        if dimension == "fluency":
            expected_sentence = packet.index
        elif dimension == "consistency":
            expected_sentence, expected_source = divmod(packet.index, len(self.work.source_spans))
        if (packet.sentence_index, packet.source_index) != (expected_sentence, expected_source):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
        self.processed[dimension] += 1
        if packet.error is not None:
            if packet.error.dimension != dimension or packet.error.index != packet.index:
                raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
            self.errors.append(packet.error)
        else:
            if packet.score is None:
                raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))
            self.values[dimension].append(packet.score)
            updated = DimensionWork(planned=work.planned, completed=work.completed + 1)
            self.work = self.work.model_copy(update={dimension: updated})
        if (
            self.processed[dimension] == work.planned
            and len(self.values[dimension]) == work.planned
        ):
            values = self.values[dimension]
            if dimension == "consistency":
                width = len(self.work.source_spans)
                values = [
                    max(values[start : start + width]) for start in range(0, len(values), width)
                ]
            self.scores = self.scores.model_copy(update={dimension: sum(values) / len(values)})

    def require_finished(self) -> None:
        if not self.prepared or any(
            self.processed[dimension] != (getattr(self.work, dimension).planned or 0)
            for dimension in DIMENSIONS
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))

    def require_issued_operation(self, packet: RequestPacket) -> None:
        if (
            self.evaluation_operation is None
            or packet.operation_metadata != self.evaluation_operation
            or packet.execution_id != self.execution_id
        ):
            raise UnievalFailure(UnievalError.from_code("WORKER_PROTOCOL_FAILED"))

    def result(self) -> UnievalResult:
        completed = [
            getattr(self.scores, dimension) is not None for dimension in DIMENSIONS
            if dimension != "relevance" or self.relevance_skip_reason is None
        ]
        status: OutcomeStatus = (
            "complete"
            if all(completed) and not self.errors
            else "partial"
            if any(completed)
            else "failed"
        )
        return UnievalResult(
            version=UNIEVAL_SCORING_VERSION,
            status=status,
            execution_id=self.execution_id,
            request_id=self.request.request_id if self.request else None,
            correlation_id=self.request.correlation_id if self.request else None,
            reference_summary_sha256=self.reference_hash,
            relevance_skip_reason=self.relevance_skip_reason,
            model=self.model,
            worker=self.worker,
            effective_settings=self.effective,
            scores=self.scores,
            work=self.work,
            timings_ms=UnievalTimings(
                queue_wait=self.queue_ms,
                scoring=self.scoring_ms,
                total=(time.monotonic() - self.received_at) * 1000,
            ),
            errors=tuple(self.errors),
        )
