"""How are ordered body-free events written with visible delivery failures?"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TextIO

from pydantic import TypeAdapter

from .contracts.base import SCHEMA_VERSION, ContextIdentity, Operation
from .contracts.error_detail import ErrorDetail
from .contracts.evaluation_event import EvaluationEvent, EventDetails
from .contracts.server_event import ApiDiagnosticData, ServerEvent
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
        self.stream.write(self.format(record) + "\n")
        self.stream.flush()


class JsonEventFormatter(logging.Formatter):
    """Serialize a validated envelope instead of formatting arbitrary messages."""

    def format(self, record: logging.LogRecord) -> str:
        if not isinstance(record.msg, ServerEvent):
            raise ValueError("Only validated server events may be logged")
        return record.msg.model_dump_json()


class DiagnosticFileHandler(logging.FileHandler):
    """Mark a failed optional mirror without using logging's traceback fallback."""

    def __init__(self, path: Path, writer: EventWriter) -> None:
        super().__init__(path, mode="a", encoding="utf-8")
        self.writer = writer

    def handleError(self, record: logging.LogRecord) -> None:
        self.writer.mark_log_unavailable()

    def emit(self, record: logging.LogRecord) -> None:
        if self.writer.log_available:
            super().emit(record)


class EventWriter:
    """Own one isolated standard-library logger for validated JSONL records."""

    def __init__(
        self,
        settings: LoggingSettings,
        stream: TextIO | None = None,
        *,
        directory: Path | None = None,
        run_id: str | None = None,
        attempt: int = 1,
        started_at: datetime | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logging.Logger("hhem_evaluator.events", logging.getLevelName(settings.level))
        self.logger.propagate = False
        self.stderr_handler = StrictEventHandler(sys.stderr if stream is None else stream)
        self.stderr_handler.setFormatter(JsonEventFormatter())
        self.logger.addHandler(self.stderr_handler)
        self.log_file: str | None = None
        self.log_available = False
        self.file_handler: DiagnosticFileHandler | None = None
        if directory is not None:
            identity = TypeAdapter(ContextIdentity).validate_python(run_id or create_execution_id())
            if type(attempt) is not int or attempt < 1:
                raise ValueError("The log attempt must be a positive integer")
            instant = started_at or datetime.now(UTC)
            offset = instant.utcoffset()
            if offset is None or offset.total_seconds() != 0:
                raise ValueError("The log start instant must use UTC")
            day = instant.strftime("%Y_%m_%d")
            self.log_file = f"fastapi-server_{day}_{identity}_{attempt}.log"
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.file_handler = DiagnosticFileHandler(directory / self.log_file, self)
                self.file_handler.setFormatter(JsonEventFormatter())
                self.log_available = True
                self.logger.addHandler(self.file_handler)
            except (OSError, ValueError):
                self.mark_log_unavailable()

    def write(self, event: EvaluationEvent) -> None:
        self.write_server_event(ServerEvent.from_evaluation(event), event.operation)

    def write_server_event(self, event: ServerEvent, operation: Operation = "service") -> None:
        try:
            event.encode_json_line(self.settings.max_event_bytes)
            self.logger.log(logging.getLevelName(event.data.level), event)
        except (OSError, ValueError, UnicodeError):
            raise EvaluationFailure(ErrorDetail.from_code("LOGGING_FAILED", operation)) from None

    def diagnostic(self, data: ApiDiagnosticData) -> None:
        self.write_server_event(ServerEvent.diagnostic(data))

    def mark_log_unavailable(self) -> None:
        self.log_available = False
        warning = ServerEvent.diagnostic(
            ApiDiagnosticData(
                component="log",
                action="unavailable",
                level="WARNING",
                code="LOG_FILE_UNAVAILABLE",
                log_file=self.log_file,
            )
        )
        record = self.logger.makeRecord(self.logger.name, logging.WARNING, "", 0, warning, (), None)
        self.stderr_handler.handle(record)

    def close(self) -> None:
        if self.file_handler is not None:
            self.logger.removeHandler(self.file_handler)
            try:
                self.file_handler.close()
            except (OSError, ValueError):
                if self.log_available:
                    self.mark_log_unavailable()


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
