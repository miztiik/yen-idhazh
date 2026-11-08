"""Which strict settings define one local API host without owning service behavior?"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HostContract(BaseModel):
    """Reject undeclared or mutable local-host settings."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ListenerSettings(HostContract):
    """Bind one bounded loopback listener."""

    host: Literal["127.0.0.1", "::1"]
    port: int = Field(ge=1, le=65535)
    max_body_bytes: int = Field(gt=0)
    body_read_timeout_ms: int = Field(gt=0)


class HostSettings(HostContract):
    """Declare one service-owned FastAPI surface on a reusable local host."""

    title: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    health_path: str
    schema_path: str
    listener: ListenerSettings
    shutdown_timeout_ms: int = Field(gt=0)
    propagate_trace_context: bool

    @field_validator("health_path", "schema_path")
    @classmethod
    def require_absolute_operation_path(cls, value: str) -> str:
        if (
            not value.startswith("/")
            or value == "/"
            or value.endswith("/")
            or "?" in value
            or "#" in value
        ):
            raise ValueError(
                "Host operation paths must be absolute routes without a trailing slash"
            )
        return value

    @model_validator(mode="after")
    def require_distinct_host_paths(self) -> Self:
        if self.health_path == self.schema_path:
            raise ValueError("Health and schema paths must be distinct")
        return self
