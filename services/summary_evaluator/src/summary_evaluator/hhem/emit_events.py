"""How are HHEM sequences and causal event identities retained by the parent?"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from local_api_host.propagate_trace_context import OperationMetadata, create_child_operation

from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION, Operation
from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent, EventDetails
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.hhem.resolve_ids import create_event_id
from summary_evaluator.shared.contracts.service_settings import LoggingSettings, StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.fail_runtime import RuntimeFailure

type EventPhase = Literal["started", "completed", "failed", "cancelled"]

type EventLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class EventEmitter:
    """Keep sequence, actual causal links and operation IDs in the parent only."""

    def __init__(
        self,
        writer: Callable[[EvaluationEvent, OperationMetadata], None],
        context: StartupContext,
        logging: LoggingSettings,
        execution_id: str | None = None,
        *,
        operation_metadata: OperationMetadata,
        root_operation: Literal["request", "service"] = "request",
    ) -> None:
        self.writer = writer
        self.context = context
        self.logging = logging
        self.execution_id = execution_id or create_execution_id()
        self.operation_metadata = operation_metadata
        self.root_operation = root_operation
        self.operation_contexts: dict[Operation, OperationMetadata] = {
            root_operation: operation_metadata
        }
        self.request_id: str | None = None
        self.correlation_id: str | None = None
        self.sequence = 0
        self.last_event_id: str | None = None
        self.operations: dict[Operation, str] = {}
        self.logging_failed = False

    def emit(
        self,
        operation: Operation,
        phase: EventPhase,
        details: EventDetails,
        *,
        cause: str | None = None,
        operation_metadata: OperationMetadata | None = None,
    ) -> str:
        if self.logging_failed:
            raise EvaluationFailure(ErrorDetail.from_code("LOGGING_FAILED", operation))
        self.sequence += 1
        if phase == "started" or operation not in self.operations:
            self.operations[operation] = create_execution_id()
        if operation_metadata is not None:
            self.operation_contexts[operation] = operation_metadata
        elif operation != self.root_operation and (
            phase == "started" or operation not in self.operation_contexts
        ):
            self.operation_contexts[operation] = create_child_operation(self.operation_metadata)
        configured = self.logging.level
        level: EventLevel = (
            "ERROR" if phase in ("failed", "cancelled") and configured != "CRITICAL" else configured
        )
        event = EvaluationEvent(
            version=SCHEMA_VERSION,
            event_id=create_event_id(self.execution_id, self.sequence),
            execution_id=self.execution_id,
            sequence=self.sequence,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            caused_by_event_id=cause,
            run_id=self.context.run_id,
            pipeline_name=self.context.pipeline_name,
            task_name=self.context.task_name,
            operation_id=self.operations[operation],
            operation=operation,
            phase=phase,
            occurred_at=datetime.now(UTC),
            level=level,
            details=details,
        )
        try:
            self.writer(event, self.operation_contexts[operation])
        except RuntimeFailure as failure:
            self.logging_failed = True
            raise EvaluationFailure(ErrorDetail.from_code(failure.code, operation)) from None
        self.last_event_id = event.event_id
        return event.event_id
