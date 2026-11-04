"""Which CloudEvents JSON records may leave the shared Python server?"""

from datetime import UTC, datetime, timedelta
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from ..resolve_ids import create_execution_id
from .base import Milliseconds, RelativePath, Uuid4, Uuid5
from .evaluate_request import is_absent
from .evaluation_event import EvaluationEvent
from .server_contract import ServerContract

DiagnosticComponent = Literal["api", "llama", "unieval", "log"]
DiagnosticAction = Literal[
    "started", "ready", "stopped", "failed", "cancelled", "unavailable", "completed"
]


class ApiDiagnosticData(ServerContract):
    """Allow safe lifecycle facts and codes, never an exception or model body."""

    component: DiagnosticComponent
    action: DiagnosticAction
    level: Literal["INFO", "WARNING", "ERROR"]
    code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$", exclude_if=is_absent)
    http_status: int | None = Field(default=None, ge=100, le=599, exclude_if=is_absent)
    duration_ms: Milliseconds | None = Field(default=None, exclude_if=is_absent)
    log_file: RelativePath | None = Field(default=None, exclude_if=is_absent)
    execution_id: Uuid4 | None = Field(default=None, exclude_if=is_absent)


class ServerEvent(ServerContract):
    """Carry one validated native occurrence in the CloudEvents structured profile."""

    specversion: Literal["1.0"]
    id: Uuid4 | Uuid5
    source: Literal["/fastapi-server"]
    type: str
    time: AwareDatetime = Field(description="UTC instant when this occurrence was emitted.")
    datacontenttype: Literal["application/json"]
    data: EvaluationEvent | ApiDiagnosticData

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
