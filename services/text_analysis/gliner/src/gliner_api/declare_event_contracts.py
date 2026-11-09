"""Which source-free GLiNER occurrences may leave the process as CloudEvents?"""

import re
from datetime import UTC, datetime
from typing import Final, Literal, Self
from uuid import UUID

from local_api_host.propagate_trace_context import read_trace_context
from pydantic import Field, field_validator, model_validator
from starlette.datastructures import Headers

from gliner_api.declare_api_contracts import ApiContract, ErrorCode, OperationName

EVENT_SOURCE: Final = "/services/text-analysis/gliner"
EventType = Literal[
    "gliner.service.started",
    "gliner.service.ready",
    "gliner.service.stopped",
    "gliner.service.failed",
    "gliner.request.completed",
    "gliner.request.failed",
]
ServiceFailureCode = Literal[
    "MODEL_UNAVAILABLE",
    "STARTUP_FAILED",
    "SHUTDOWN_FAILED",
    "LOGGING_FAILED",
]


class ServiceEventData(ApiContract):
    """Describe provider lifecycle without model identity or unsafe diagnostics."""

    status: Literal["starting", "disabled", "ready", "stopped", "failed"]
    enabled: bool
    error_code: ServiceFailureCode | None = None

    @model_validator(mode="after")
    def require_failure_code(self) -> Self:
        if (self.status == "failed") != (self.error_code is not None):
            raise ValueError("Only failed service events may carry a failure code")
        return self


class RequestEventData(ApiContract):
    """Describe only the native operation and its fixed terminal outcome."""

    operation: OperationName
    status: Literal["complete", "failed"]
    error_code: ErrorCode | None = None

    @model_validator(mode="after")
    def require_failure_code(self) -> Self:
        if (self.status == "failed") != (self.error_code is not None):
            raise ValueError("Request status and failure code must agree")
        return self


class GlinerEvent(ApiContract):
    """Carry one validated occurrence through CloudEvents 1.0 and W3C transport."""

    specversion: Literal["1.0"]
    id: str
    source: str = Field(json_schema_extra={"const": EVENT_SOURCE})
    type: EventType
    time: str
    datacontenttype: Literal["application/json"]
    traceparent: str
    tracestate: str | None = None
    data: ServiceEventData | RequestEventData

    @field_validator("id")
    @classmethod
    def require_uuid4(cls, value: str) -> str:
        try:
            identity = UUID(value)
        except ValueError:
            raise ValueError("Event identity must be a lowercase UUIDv4") from None
        if identity.version != 4 or str(identity) != value:
            raise ValueError("Event identity must be a lowercase UUIDv4")
        return value

    @field_validator("time")
    @classmethod
    def require_utc_instant(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z", value):
            raise ValueError("Event time must be a UTC second or millisecond instant")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("Event time must be a valid UTC instant") from None
        if parsed.tzinfo != UTC:
            raise ValueError("Event time must use UTC")
        return value

    @model_validator(mode="before")
    @classmethod
    def refuse_null_trace_state(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("tracestate", ...) is None:
            raise ValueError("Absent tracestate must be omitted")
        return value

    @model_validator(mode="after")
    def require_native_occurrence(self) -> Self:
        if self.source != EVENT_SOURCE:
            raise ValueError("Event source must identify this native provider")
        carrier = {"traceparent": self.traceparent}
        if self.tracestate is not None:
            carrier["tracestate"] = self.tracestate
        operation = read_trace_context(Headers(carrier))
        if operation is None or operation.trace_state != self.tracestate:
            raise ValueError("Event transport must contain canonical valid W3C context")
        if isinstance(self.data, ServiceEventData):
            expected = {
                "starting": "gliner.service.started",
                "disabled": "gliner.service.started",
                "ready": "gliner.service.ready",
                "stopped": "gliner.service.stopped",
                "failed": "gliner.service.failed",
            }[self.data.status]
        else:
            expected = (
                "gliner.request.completed"
                if self.data.status == "complete"
                else "gliner.request.failed"
            )
        if self.type != expected:
            raise ValueError("Event type must match its native terminal data")
        return self
