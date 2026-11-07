"""How are validated application envelopes delivered to their configured logs?"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

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
        scorer: ApiComponent | None = None,
    ) -> None:
        self.settings = settings
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

    def write(self, event: EvaluationEvent) -> None:
        self.write_server_event(ServerEvent.from_evaluation(event))

    def write_server_event(self, event: ServerEvent) -> None:
        try:
            event.encode_json_line(self.settings.max_event_bytes)
            self.logger.log(logging.getLevelName(event.data.level), event)
        except (OSError, ValueError, UnicodeError):
            raise RuntimeFailure("LOGGING_FAILED") from None

    def diagnostic(self, data: ApiDiagnosticData) -> None:
        self.write_server_event(ServerEvent.diagnostic(data))

    def component_diagnostic(self, component: DiagnosticComponent, data: LifecycleFields) -> None:
        self.diagnostic(
            ApiDiagnosticData.model_validate({"component": component, **data.model_dump()})
        )

    def unieval_diagnostic(self, data: LifecycleFields) -> None:
        self.component_diagnostic("unieval", data)

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
