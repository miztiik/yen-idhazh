"""How are validated application envelopes delivered to their configured logs?"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_root_operation,
    write_trace_context,
)
from pydantic import TypeAdapter

from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.serve_http.contracts.server_event import (
    ApiDiagnosticData,
    DiagnosticComponent,
    ServerEvent,
)
from summary_evaluator.shared.contracts.base import ContextIdentity
from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.service_settings import LoggingSettings
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.shared.write_event_records import StrictEventHandler


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
        operation = getattr(record, "operation_metadata", None)
        if not isinstance(operation, OperationMetadata):
            raise RuntimeFailure("LOGGING_FAILED")
        self.writer.mark_log_unavailable(operation)

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
        scorer: ApiComponent | None = None,
        service_operation: OperationMetadata | None = None,
        propagate_trace_context: bool = False,
    ) -> None:
        self.settings = settings
        self.service_operation = service_operation or create_root_operation()
        self.bind_trace_mode(propagate_trace_context)
        self.logger = logging.Logger(
            "summary_evaluator.events", logging.getLevelName(settings.level)
        )
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
            role = f"fastapi-server_{scorer}" if scorer is not None else "fastapi-server"
            self.log_file = f"{role}_{day}_{identity}_{attempt}.log"
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.file_handler = DiagnosticFileHandler(directory / self.log_file, self)
                self.file_handler.setFormatter(JsonEventFormatter())
                self.log_available = True
                self.logger.addHandler(self.file_handler)
            except (OSError, ValueError):
                self.mark_log_unavailable()

    def bind_trace_mode(self, propagate_trace_context: bool) -> None:
        """Project the one validated API emission mode without storing request context."""
        if type(propagate_trace_context) is not bool:
            raise ValueError("Trace emission requires a validated boolean mode")
        self.propagate_trace_context = propagate_trace_context

    def write(
        self, event: EvaluationEvent, operation_metadata: OperationMetadata | None = None
    ) -> None:
        try:
            envelope = ServerEvent.from_evaluation(
                event,
                operation_metadata,
                propagate_trace_context=self.propagate_trace_context,
            )
        except ValueError:
            raise RuntimeFailure("LOGGING_FAILED") from None
        self.write_server_event(envelope, operation_metadata)

    def write_server_event(
        self, event: ServerEvent, operation_metadata: OperationMetadata | None = None
    ) -> None:
        try:
            if self.propagate_trace_context and operation_metadata is None:
                raise ValueError("Enabled emission requires the actual operation metadata")
            if self.propagate_trace_context and operation_metadata is not None:
                carrier = write_trace_context(operation_metadata)
                if (
                    event.traceparent != carrier["traceparent"]
                    or event.tracestate != carrier.get("tracestate")
                ):
                    raise ValueError("Enabled emission must retain its actual operation carrier")
            elif event.traceparent is not None:
                raise ValueError("Disabled emission cannot claim a live trace carrier")
            event.encode_json_line(self.settings.max_event_bytes)
            self.logger.log(
                logging.getLevelName(event.data.level),
                event,
                extra={"operation_metadata": operation_metadata or self.service_operation},
            )
        except (OSError, ValueError, UnicodeError):
            raise RuntimeFailure("LOGGING_FAILED") from None

    def diagnostic(
        self, data: ApiDiagnosticData, operation_metadata: OperationMetadata | None = None
    ) -> None:
        operation = operation_metadata or self.service_operation
        self.write_server_event(
            ServerEvent.diagnostic(
                data,
                operation,
                propagate_trace_context=self.propagate_trace_context,
            ),
            operation,
        )

    def component_diagnostic(
        self,
        component: DiagnosticComponent,
        data: LifecycleFields,
        operation_metadata: OperationMetadata | None = None,
    ) -> None:
        self.diagnostic(
            ApiDiagnosticData.model_validate({"component": component, **data.model_dump()}),
            operation_metadata,
        )

    def unieval_diagnostic(
        self, data: LifecycleFields, operation_metadata: OperationMetadata | None = None
    ) -> None:
        self.component_diagnostic("unieval", data, operation_metadata)

    def mark_log_unavailable(self, operation_metadata: OperationMetadata | None = None) -> None:
        self.log_available = False
        operation = operation_metadata or self.service_operation
        warning = ServerEvent.diagnostic(
            ApiDiagnosticData(
                component="log",
                action="unavailable",
                level="WARNING",
                code="LOG_FILE_UNAVAILABLE",
                log_file=self.log_file,
            ),
            operation,
            propagate_trace_context=self.propagate_trace_context,
        )
        try:
            warning.encode_json_line(self.settings.max_event_bytes)
            record = self.logger.makeRecord(
                self.logger.name,
                logging.WARNING,
                "",
                0,
                warning,
                (),
                None,
                extra={"operation_metadata": operation},
            )
            self.stderr_handler.handle(record)
        except (OSError, ValueError, UnicodeError):
            raise RuntimeFailure("LOGGING_FAILED") from None

    def close(self) -> None:
        if self.file_handler is not None:
            self.logger.removeHandler(self.file_handler)
            try:
                self.file_handler.close()
            except (OSError, ValueError):
                if self.log_available:
                    self.mark_log_unavailable()
