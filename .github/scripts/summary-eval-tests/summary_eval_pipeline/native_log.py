"""How are body-free native lifecycle events mirrored without making logging a work gate?"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from hhem_evaluator.contracts.lifecycle_fields import LifecycleFields
from hhem_evaluator.shared.contracts.base import Uuid4
from hhem_evaluator.shared.contracts.service_settings import LoggingSettings
from hhem_evaluator.shared.create_execution_id import create_execution_id
from hhem_evaluator.write_event_records import StrictEventHandler
from pydantic import AwareDatetime

from .contracts import RunIdentity, WorkflowContract


class NativeDiagnosticData(LifecycleFields):
    component: Literal["llama", "log"]


class NativeEvent(WorkflowContract):
    specversion: Literal["1.0"]
    id: Uuid4
    source: Literal["/llama-server"]
    type: str
    time: AwareDatetime
    datacontenttype: Literal["application/json"]
    data: NativeDiagnosticData


class NativeFormatter(logging.Formatter):
    def __init__(self, max_bytes: int) -> None:
        super().__init__()
        self.max_bytes = max_bytes

    def format(self, record: logging.LogRecord) -> str:
        if not isinstance(record.msg, NativeEvent):
            raise ValueError("Only validated native lifecycle events may be logged")
        encoded = record.msg.model_dump_json()
        if len((encoded + "\n").encode("utf-8")) > self.max_bytes:
            raise ValueError("Record exceeds native_logging.max_event_bytes")
        return encoded


class NativeFileHandler(logging.FileHandler):
    def __init__(self, path: Path, writer: NativeLog) -> None:
        super().__init__(path, mode="a", encoding="utf-8")
        self.writer = writer

    def emit(self, record: logging.LogRecord) -> None:
        if self.writer.available:
            super().emit(record)

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802 - logging override.
        self.writer.unavailable()


class NativeLog:
    def __init__(self, directory: Path, run: RunIdentity, settings: LoggingSettings) -> None:
        day = run.started_at.strftime("%Y_%m_%d")
        self.filename = f"llama-server_{day}_{run.run_id}_{run.attempt}.log"
        self.available = False
        self.logger = logging.Logger("summary_eval.native", logging.getLevelName(settings.level))
        self.logger.propagate = False
        self.stderr = StrictEventHandler(sys.stderr)
        self.stderr.setFormatter(NativeFormatter(settings.max_event_bytes))
        self.logger.addHandler(self.stderr)
        self.file: NativeFileHandler | None = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self.file = NativeFileHandler(directory / self.filename, self)
            self.file.setFormatter(NativeFormatter(settings.max_event_bytes))
            self.logger.addHandler(self.file)
            self.available = True
        except (OSError, ValueError):
            self.unavailable()

    def event(self, data: NativeDiagnosticData) -> None:
        event = NativeEvent(
            specversion="1.0",
            id=create_execution_id(),
            source="/llama-server",
            type=f"llama-server.{data.component}.{data.action}",
            time=datetime.now(UTC),
            datacontenttype="application/json",
            data=data,
        )
        self.logger.log(logging.getLevelName(data.level), event)

    def unavailable(self) -> None:
        self.available = False
        self.event(
            NativeDiagnosticData(
                component="log",
                action="unavailable",
                level="WARNING",
                code="LOG_FILE_UNAVAILABLE",
                log_file=self.filename,
            )
        )

    def close(self) -> None:
        if self.file is not None:
            self.logger.removeHandler(self.file)
            try:
                self.file.close()
            except (OSError, ValueError):
                self.unavailable()
