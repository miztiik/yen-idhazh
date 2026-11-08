"""How does parent-owned progress preserve only fully completed comparison scores?"""

import asyncio
import time
from dataclasses import dataclass, field

from local_api_host.propagate_trace_context import create_child_operation

from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION, Comparison
from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.evaluate_request import EffectiveSettings, EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_event import EventDetails
from summary_evaluator.hhem.contracts.evaluation_progress import (
    EvaluationTimings,
    EvaluationWindows,
    WindowCounts,
    WindowDetail,
    WindowDetails,
)
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity
from summary_evaluator.hhem.contracts.worker_contract import HHEM_WORKER_VERSION
from summary_evaluator.hhem.contracts.worker_message import ScoreWindow
from summary_evaluator.hhem.emit_events import EventEmitter
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.hhem.maintain_worker import WorkerSupervisor
from summary_evaluator.hhem.plan_windows import WordWindow
from summary_evaluator.shared.contracts.base import OutcomeStatus
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity


@dataclass
class EvaluationState:
    """Retain one in-flight request, never a cache of completed responses."""

    emitter: EventEmitter
    received_at: float
    request: EvaluateRequest | None = None
    effective: EffectiveSettings | None = None
    primary_plan: tuple[WordWindow, ...] | None = None
    full_plan: tuple[WordWindow, ...] | None = None
    primary_details: list[WindowDetail] = field(default_factory=list)
    full_details: list[WindowDetail] = field(default_factory=list)
    primary_score: float | None = None
    full_score: float | None = None
    full_reused: bool = False
    queue_wait_ms: float | None = None
    primary_ms: float | None = None
    full_ms: float | None = None
    model: ModelIdentity | None = None
    worker: WorkerIdentity | None = None
    errors: list[ErrorDetail] = field(default_factory=list)
    recovery_started: bool = False
    recovery_task: asyncio.Task[None] | None = None
    deadline: float | None = None

    def result(self, terminal_event_id: str | None) -> EvaluationResult:
        status: OutcomeStatus = (
            "complete"
            if not self.errors
            else ("partial" if self.primary_score is not None else "failed")
        )
        optional: dict[str, WindowDetails] = {}
        if self.effective is not None and self.effective.include_window_details:
            optional["window_details"] = WindowDetails(
                primary=tuple(self.primary_details),
                full=(
                    tuple(self.primary_details if self.full_reused else self.full_details)
                    if self.full_plan is not None
                    else None
                ),
            )
        return EvaluationResult(
            version=SCHEMA_VERSION,
            status=status,
            execution_id=self.emitter.execution_id,
            request_id=self.emitter.request_id,
            correlation_id=self.emitter.correlation_id,
            terminal_event_id=terminal_event_id,
            hhem=self.primary_score,
            hhem_full=self.full_score,
            hhem_delta=(
                self.primary_score - self.full_score
                if self.primary_score is not None and self.full_score is not None
                else None
            ),
            effective_settings=self.effective,
            windows=EvaluationWindows(
                primary=(
                    WindowCounts(planned=len(self.primary_plan), scored=len(self.primary_details))
                    if self.primary_plan is not None
                    else None
                ),
                full=(
                    WindowCounts(planned=len(self.full_plan), scored=len(self.full_details))
                    if self.full_plan is not None
                    else None
                ),
                full_reused_primary=self.full_reused,
            ),
            model=self.model,
            worker=self.worker,
            timings_ms=EvaluationTimings(
                queue_wait=self.queue_wait_ms,
                primary_scoring=self.primary_ms,
                full_scoring=self.full_ms,
                total=(time.monotonic() - self.received_at) * 1000,
            ),
            errors=tuple(self.errors),
            **optional,
        )

    def forget_text(self) -> None:
        self.request = None
        self.primary_plan = None
        self.full_plan = None


async def score_comparison(
    state: EvaluationState, worker: WorkerSupervisor, comparison: Comparison
) -> None:
    plan = state.primary_plan if comparison == "primary" else state.full_plan
    if plan is None or state.request is None or state.worker is None:
        raise EvaluationFailure(ErrorDetail.from_code("INTERNAL_ERROR", comparison))
    details = state.primary_details if comparison == "primary" else state.full_details
    cause = state.emitter.emit(
        comparison,
        "started",
        EventDetails(window_count=len(plan)),
        cause=state.emitter.last_event_id,
    )
    started = time.monotonic()
    try:
        for window in plan:
            check_deadline(state, comparison, window.index)
            command = ScoreWindow(
                version=HHEM_WORKER_VERSION,
                operation_metadata=create_child_operation(
                    state.emitter.operation_contexts[comparison]
                ),
                kind="score_window",
                execution_id=state.emitter.execution_id,
                generation=state.worker.generation,
                comparison=comparison,
                window_index=window.index,
                start_word=window.start_word,
                end_word=window.end_word,
                source_text=window.text,
                summary_text=state.request.summary_text,
            )
            outcome = await worker.score(command)
            check_deadline(state, comparison, window.index)
            if outcome.error is not None:
                raise EvaluationFailure(outcome.error)
            if outcome.score is None:
                raise EvaluationFailure(
                    ErrorDetail.from_code(
                        "INVALID_MODEL_OUTPUT", comparison, window_index=window.index
                    )
                )
            details.append(
                WindowDetail(
                    index=window.index,
                    start_word=window.start_word,
                    end_word=window.end_word,
                    score=outcome.score,
                )
            )
        score = max(window.score for window in details)
        if comparison == "primary":
            state.primary_score = score
        else:
            state.full_score = score
        state.emitter.emit(
            comparison,
            "completed",
            EventDetails(window_count=len(plan), scored_window_count=len(details), score=score),
            cause=cause,
        )
    finally:
        elapsed = (time.monotonic() - started) * 1000
        if comparison == "primary":
            state.primary_ms = elapsed
        else:
            state.full_ms = elapsed


async def score_windows(state: EvaluationState, worker: WorkerSupervisor) -> None:
    await score_comparison(state, worker, "primary")
    if state.effective is None or not state.effective.hhem_full:
        return
    request = state.request
    if request is None:
        raise EvaluationFailure(ErrorDetail.from_code("INTERNAL_ERROR", "full"))
    check_deadline(state, "full")
    if request.source_text == request.full_source_text:
        state.full_reused = True
        state.full_score = state.primary_score
        cause = state.emitter.emit(
            "full",
            "started",
            EventDetails(window_count=len(state.primary_details)),
            cause=state.emitter.last_event_id,
        )
        state.emitter.emit(
            "full",
            "completed",
            EventDetails(score=state.full_score, scored_window_count=0),
            cause=cause,
        )
        return
    await score_comparison(state, worker, "full")


def check_deadline(
    state: EvaluationState, comparison: Comparison, window_index: int | None = None
) -> None:
    if state.deadline is None:
        raise EvaluationFailure(ErrorDetail.from_code("INTERNAL_ERROR", comparison))
    if time.monotonic() >= state.deadline:
        raise EvaluationFailure(
            ErrorDetail.from_code("EVALUATION_TIMEOUT", comparison, window_index=window_index)
        )
