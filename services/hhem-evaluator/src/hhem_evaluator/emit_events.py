"""How are ordered body-free events written with visible delivery failures?"""

import logging
import sys
from datetime import UTC, datetime
from typing import Literal, TextIO

from .contracts.base import SCHEMA_VERSION, Operation
from .contracts.error_detail import ErrorDetail
from .contracts.evaluation_event import EvaluationEvent, EventDetails
from .contracts.service_settings import LoggingSettings, StartupContext
from .fail_evaluation import EvaluationFailure
from .resolve_ids import create_event_id, create_execution_id

type EventPhase = Literal["started", "completed", "failed", "cancelled"]
type EventLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class StrictEventHandler(logging.Handler):
    """Propagate write and flush errors instead of invoking logging's fallback."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self.stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        self.stream.write(record.getMessage() + "\n")
        self.stream.flush()


class EventWriter:
    """Own one isolated standard-library logger for validated JSONL records."""

    def __init__(self, settings: LoggingSettings, stream: TextIO | None = None) -> None:
        self.settings = settings
        self.logger = logging.Logger("hhem_evaluator.events", logging.getLevelName(settings.level))
        self.logger.propagate = False
        self.logger.addHandler(StrictEventHandler(sys.stderr if stream is None else stream))

    def write(self, event: EvaluationEvent) -> None:
        try:
            line = (
                event.encode_json_line(self.settings.max_event_bytes).decode("utf-8").rstrip("\n")
            )
            self.logger.log(logging.getLevelName(event.level), line)
        except Exception:
            raise EvaluationFailure(
                ErrorDetail.from_code("LOGGING_FAILED", event.operation)
            ) from None


class EventEmitter:
    """Keep sequence, actual causal links and operation IDs in the parent only."""

    def __init__(
        self,
        writer: EventWriter,
        context: StartupContext,
        execution_id: str | None = None,
    ) -> None:
        self.writer = writer
        self.context = context
        self.execution_id = execution_id or create_execution_id()
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
    ) -> str:
        if self.logging_failed:
            raise EvaluationFailure(ErrorDetail.from_code("LOGGING_FAILED", operation))
        self.sequence += 1
        if phase == "started" or operation not in self.operations:
            self.operations[operation] = create_execution_id()
        configured = self.writer.settings.level
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
            self.writer.write(event)
        except EvaluationFailure:
            self.logging_failed = True
            raise
        self.last_event_id = event.event_id
        return event.event_id
