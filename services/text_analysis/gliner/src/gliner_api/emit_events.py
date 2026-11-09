"""How are validated GLiNER CloudEvents delivered only to stderr?"""

import asyncio
import logging
import sys
from datetime import UTC, datetime
from typing import TextIO
from uuid import uuid4

from local_api_host.propagate_trace_context import OperationMetadata, write_trace_context

from gliner_api.declare_event_contracts import (
    EVENT_SOURCE,
    EventType,
    GlinerEvent,
    RequestEventData,
    ServiceEventData,
)
from gliner_api.load_settings import LoggingSettings


class EventDeliveryError(RuntimeError):
    """Report failed delivery without exposing a stream or raw exception."""


class _EventFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not isinstance(record.msg, GlinerEvent):
            raise EventDeliveryError("Only validated GLiNER events may be emitted.")
        return record.msg.model_dump_json(exclude_none=True)


class _EventHandler(logging.Handler):
    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self.stream = stream
        self.setFormatter(_EventFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.stream.write(self.format(record) + "\n")
        self.stream.flush()


class EventEmitter:
    """Keep each event atomic and independent of global model-library loggers."""

    def __init__(self, settings: LoggingSettings, stream: TextIO | None = None) -> None:
        self.settings = settings
        self.logger = logging.Logger("gliner_api.events", logging.getLevelName(settings.level))
        self.logger.propagate = False
        self.handler = _EventHandler(sys.stderr if stream is None else stream)
        self.logger.addHandler(self.handler)
        self.lock = asyncio.Lock()
        self.closed = False

    async def emit(
        self,
        operation: OperationMetadata,
        event_type: EventType,
        data: ServiceEventData | RequestEventData,
    ) -> None:
        carrier = write_trace_context(operation)
        event = GlinerEvent.model_validate(
            {
                "specversion": "1.0",
                "id": str(uuid4()),
                "source": EVENT_SOURCE,
                "type": event_type,
                "time": (
                    datetime.now(UTC)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z")
                ),
                "datacontenttype": "application/json",
                **carrier,
                "data": data,
            }
        )
        encoded = (event.model_dump_json(exclude_none=True) + "\n").encode("utf-8")
        if len(encoded) > self.settings.max_event_bytes:
            raise EventDeliveryError("The GLiNER event exceeds its configured byte limit.")
        async with self.lock:
            if self.closed:
                raise EventDeliveryError("The GLiNER event sink is closed.")
            try:
                self.logger.log(logging.ERROR if data.status == "failed" else logging.INFO, event)
            except (OSError, UnicodeError, ValueError):
                raise EventDeliveryError("The GLiNER event could not be delivered.") from None

    async def aclose(self) -> None:
        async with self.lock:
            if not self.closed:
                self.closed = True
                self.logger.removeHandler(self.handler)
                self.handler.close()
