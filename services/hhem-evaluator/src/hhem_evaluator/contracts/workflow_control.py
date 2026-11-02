"""Which private body-free packets prove an owned service's startup and shutdown?"""

from typing import Annotated, Literal

from pydantic import Field, RootModel

from .base import NativeContract, PositiveCount, SchemaVersion, Uuid4
from .service_settings import StartupContext


class StartupPacket(NativeContract):
    version: SchemaVersion
    startup_id: Uuid4
    context: StartupContext


class ControlPacket(NativeContract):
    version: SchemaVersion


class ApiReady(ControlPacket):
    kind: Literal["ready"]
    service: Literal["hhem"]
    startup_id: Uuid4
    pid: PositiveCount
    service_instance_id: Uuid4


class HostReady(ControlPacket):
    kind: Literal["ready"]
    service: Literal["host"]
    startup_id: Uuid4
    pid: PositiveCount
    host: Literal["127.0.0.1", "::1"]
    port: int = Field(strict=True, ge=1, le=65535)
    lifecycle_timeout_ms: PositiveCount


class ServiceStopped(ControlPacket):
    kind: Literal["stopped"]
    service: Literal["hhem", "host"]
    startup_id: Uuid4
    pid: PositiveCount
    clean: bool
    worker_exit_confirmed: bool | None


class ServiceStartFailed(ControlPacket):
    kind: Literal["failed"]
    service: Literal["hhem", "host"]
    startup_id: Uuid4
    pid: PositiveCount


class ServiceControl(
    RootModel[
        Annotated[
            ApiReady | HostReady | ServiceStopped | ServiceStartFailed,
            Field(union_mode="left_to_right"),
        ]
    ]
):
    pass
