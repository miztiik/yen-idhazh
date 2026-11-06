"""Which private packets identify a phase's shared API and machine supervisor?"""

from typing import Annotated, Literal

from hhem_evaluator.shared.contracts.base import CommitId, PositiveCount, Uuid4
from hhem_evaluator.shared.contracts.service_settings import StartupContext
from pydantic import Field, RootModel

from .contracts import (
    Hardware,
    PhaseName,
    RunIdentity,
    SourceCode,
    WorkflowContract,
    WorkflowVersion,
)
from .host_reader import HonoServerReader, MachineUsage


class StartupPacket(WorkflowContract):
    version: WorkflowVersion
    startup_id: Uuid4
    context: StartupContext
    git_sha: CommitId | None = None
    attempt: PositiveCount = 1
    request_id: Uuid4 | None = None
    correlation_id: Uuid4 | None = None
    phase: PhaseName = "evaluation"
    run: RunIdentity | None = None


class ControlPacket(WorkflowContract):
    version: WorkflowVersion


class ApiReady(ControlPacket):
    kind: Literal["ready"]
    service: Literal["api"]
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
    service: Literal["api", "host"]
    startup_id: Uuid4
    pid: PositiveCount
    clean: bool
    worker_exit_confirmed: bool | None
    unieval_worker_exit_confirmed: bool | None = None
    machine: MachineUsage | None = None
    server: HonoServerReader | None = None
    log_available: bool | None = None
    error_code: SourceCode | None = None
    cleanup_error_code: SourceCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)


class ServiceStartFailed(ControlPacket):
    kind: Literal["failed"]
    service: Literal["api", "host"]
    startup_id: Uuid4
    pid: PositiveCount
    error_code: SourceCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)


class ServiceControl(
    RootModel[
        Annotated[
            ApiReady | HostReady | ServiceStopped | ServiceStartFailed,
            Field(union_mode="left_to_right"),
        ]
    ]
):
    pass
