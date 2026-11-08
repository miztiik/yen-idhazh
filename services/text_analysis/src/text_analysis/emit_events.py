"""How are validated text-analysis CloudEvents written only to stderr?"""

import asyncio
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TextIO
from uuid import uuid4

from local_api_host.propagate_trace_context import (
    OperationMetadata,
    write_trace_context,
)

from text_analysis.declare_api_contracts import (
    EventType,
    RequestEventData,
    ServiceEventData,
    TextAnalysisEvent,
)
from text_analysis.declare_service_settings import LoggingSettings


class StrictEventHandler(logging.Handler):
    """Write one formatted event or propagate the delivery failure."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self.stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        self.stream.write(self.format(record) + "\n")
        self.stream.flush()


class EventFormatter(logging.Formatter):
    """Serialize only validated text-analysis events."""

    def format(self, record: logging.LogRecord) -> str:
        if not isinstance(record.msg, TextAnalysisEvent):
            raise ValueError("Only validated text-analysis events may be logged")
        return record.msg.model_dump_json()


class EventEmitter:
    """Own one async-safe stderr logger and the service-root operation."""

    def __init__(
        self,
        settings: LoggingSettings,
        stream: TextIO | None = None,
    ) -> None:
        self.settings = settings
        self.logger = logging.Logger(
            "text_analysis.events",
            logging.getLevelName(settings.level),
        )
        self.logger.propagate = False
        self.handler = StrictEventHandler(sys.stderr if stream is None else stream)
        self.handler.setFormatter(EventFormatter())
        self.logger.addHandler(self.handler)
        self.lock = asyncio.Lock()
        self.service_operation: OperationMetadata | None = None
        self.on_failure: Callable[[], None] = lambda: None
        self.closed = False

    def bind_failure(self, callback: Callable[[], None]) -> None:
        self.on_failure = callback

    async def emit(
        self,
        operation: OperationMetadata,
        event_type: EventType,
        data: ServiceEventData | RequestEventData,
    ) -> bool:
        carrier = write_trace_context(operation)
        event = TextAnalysisEvent.model_validate(
            {
                "specversion": "1.0",
                "id": str(uuid4()),
                "source": "/services/text-analysis",
                "type": event_type,
                "time": datetime.now(UTC)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
                "datacontenttype": "application/json",
                "traceparent": carrier["traceparent"],
                **(
                    {"tracestate": carrier["tracestate"]}
                    if "tracestate" in carrier
                    else {}
                ),
                "data": data,
            }
        )
        encoded = (event.model_dump_json() + "\n").encode("utf-8")
        if len(encoded) > self.settings.max_event_bytes:
            self.on_failure()
            return False
        async with self.lock:
            if self.closed:
                self.on_failure()
                return False
            try:
                self.logger.log(
                    logging.INFO if data.level == "INFO" else logging.ERROR,
                    event,
                )
            except (OSError, UnicodeError, ValueError):
                self.on_failure()
                return False
        return True

    async def emit_service(
        self,
        operation: OperationMetadata,
        event_type: EventType,
        data: ServiceEventData,
    ) -> bool:
        self.service_operation = operation
        return await self.emit(operation, event_type, data)

    async def emit_runtime_failure(self, data: ServiceEventData) -> bool:
        if self.service_operation is None:
            self.on_failure()
            return False
        return await self.emit(
            self.service_operation,
            "text-analysis.service.failed",
            data,
        )

    async def aclose(self) -> None:
        async with self.lock:
            if self.closed:
                return
            self.closed = True
            self.logger.removeHandler(self.handler)
            self.handler.close()
