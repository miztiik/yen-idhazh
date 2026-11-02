"""Which private body-free packets prove an owned service's startup and shutdown?"""

from typing import Annotated, Literal

from pydantic import Field, RootModel

from hhem_evaluator.contracts.base import (
    CommitId,
    NativeContract,
    PositiveCount,
    SchemaVersion,
    Uuid4,
)
from hhem_evaluator.contracts.service_settings import StartupContext

from .contracts import Hardware
from .host_reader import MachineUsage


class StartupPacket(NativeContract):
    version: SchemaVersion
    startup_id: Uuid4
    context: StartupContext
    git_sha: CommitId | None = None
    attempt: PositiveCount = 1
    request_id: Uuid4 | None = None
    correlation_id: Uuid4 | None = None


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
    hardware: Hardware
    profile_started: bool
    lifecycle_timeout_ms: PositiveCount


class ServiceStopped(ControlPacket):
    kind: Literal["stopped"]
    service: Literal["hhem", "host"]
    startup_id: Uuid4
    pid: PositiveCount
    clean: bool
    worker_exit_confirmed: bool | None
    machine: MachineUsage | None = None


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
