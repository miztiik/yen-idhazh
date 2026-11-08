"""Which CloudEvents JSON records may leave the shared Python server?"""

from datetime import UTC, datetime, timedelta
from typing import Final, Literal, Self

from local_api_host.propagate_trace_context import read_trace_context
from pydantic import AwareDatetime, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema
from starlette.datastructures import Headers

from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.shared.contracts.base import Uuid4, Uuid5
from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.optional_fields import is_absent, omit_default
from summary_evaluator.shared.contracts.server_contract import ServerContract
from summary_evaluator.shared.create_execution_id import create_execution_id

SERVER_EVENT_SCHEMA_VERSION: Final = "2026-11-08"
DiagnosticComponent = Literal["api", "unieval", "coverage", "log"]


class ApiDiagnosticData(LifecycleFields):
    """Allow safe lifecycle facts and codes, never an exception or model body."""

    component: DiagnosticComponent


class ServerEvent(ServerContract):
    """Carry one validated native occurrence in the CloudEvents structured profile."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": SERVER_EVENT_SCHEMA_VERSION,
            "changelog": [
                {
                    "version": SERVER_EVENT_SCHEMA_VERSION,
                    "change": "Read optional W3C carriers without changing native occurrences.",
                }
            ],
            "readCompatibility": (
                "read_and_preserve; absent carriers stay omitted; "
                "present carriers must validate and state requires a parent"
            ),
        }
    )

    specversion: Literal["1.0"]
    id: Uuid4 | Uuid5
    source: Literal["/fastapi-server"]
    type: str
    time: AwareDatetime = Field(description="UTC instant when this occurrence was emitted.")
    datacontenttype: Literal["application/json"]
    traceparent: str | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    tracestate: str | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    data: EvaluationEvent | ApiDiagnosticData

    @field_validator("traceparent", "tracestate")
    @classmethod
    def refuse_null_carriers(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Omit absent trace carriers instead of supplying null")
        return value

    @model_validator(mode="after")
    def require_valid_trace_carrier(self) -> Self:
        if self.traceparent is None:
            if self.tracestate is not None:
                raise ValueError("tracestate requires traceparent")
            return self
        carrier = {"traceparent": self.traceparent}
        if self.tracestate is not None:
            carrier["tracestate"] = self.tracestate
        operation = read_trace_context(Headers(carrier))
        if operation is None:
            raise ValueError("traceparent must contain valid W3C operation context")
        if self.tracestate is not None and self.tracestate != operation.trace_state:
            raise ValueError("tracestate must be canonical W3C trace state")
        return self

    @model_validator(mode="after")
    def require_matching_occurrence(self) -> Self:
        if self.time.utcoffset() != timedelta(0):
            raise ValueError("time must use UTC")
        if isinstance(self.data, EvaluationEvent):
            expected = f"fastapi-server.hhem.{self.data.operation}.{self.data.phase}"
            if self.id != self.data.event_id or self.time != self.data.occurred_at:
                raise ValueError("The envelope must retain the native event occurrence")
        else:
            expected = f"fastapi-server.{self.data.component}.{self.data.action}"
        if self.type != expected:
            raise ValueError("type must identify the declared native occurrence")
        return self

    @classmethod
    def from_evaluation(cls, event: EvaluationEvent) -> Self:
        return cls(
            specversion="1.0",
            id=event.event_id,
            source="/fastapi-server",
            type=f"fastapi-server.hhem.{event.operation}.{event.phase}",
            time=event.occurred_at,
            datacontenttype="application/json",
            data=event,
        )

    @classmethod
    def diagnostic(cls, data: ApiDiagnosticData) -> Self:
        return cls(
            specversion="1.0",
            id=create_execution_id(),
            source="/fastapi-server",
            type=f"fastapi-server.{data.component}.{data.action}",
            time=datetime.now(UTC),
            datacontenttype="application/json",
            data=data,
        )

    def encode_json_line(self, max_bytes: int) -> bytes:
        encoded = (self.model_dump_json() + "\n").encode("utf-8")
        if len(encoded) > max_bytes:
            raise ValueError("Record exceeds logging.max_event_bytes")
        return encoded
