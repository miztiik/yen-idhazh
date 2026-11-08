"""Which private packets identify a phase's shared API and machine supervisor?"""

from typing import Annotated, Final, Literal

from local_api_host.propagate_trace_context import OperationMetadata
from pydantic import BaseModel, ConfigDict, Field, RootModel
from summary_evaluator.shared.contracts.base import CommitId, PositiveCount, Uuid4
from summary_evaluator.shared.contracts.service_settings import StartupContext

from .contracts import (
    Hardware,
    PhaseName,
    RunIdentity,
    ServerOutcome,
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


MACHINE_STARTUP_VERSION: Final = "2026-11-08"


class MachineStartupPacket(WorkflowContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": MACHINE_STARTUP_VERSION,
            "readCompatibility": "read legacy flat 2026-11-05 startup without adding metadata",
            "changelog": [
                {
                    "version": MACHINE_STARTUP_VERSION,
                    "change": "Carry the issued machine launch operation in a transient wrapper.",
                }
            ],
        }
    )
    version: Literal["2026-11-08"]
    startup: StartupPacket
    operation_metadata: OperationMetadata

    @property
    def startup_id(self) -> str:
        return self.startup.startup_id

    @property
    def phase(self) -> PhaseName:
        return self.startup.phase


class MachineStartup(
    RootModel[
        Annotated[MachineStartupPacket | StartupPacket, Field(discriminator="version")]
    ]
):
    model_config = ConfigDict(
        json_schema_extra=MachineStartupPacket.model_config["json_schema_extra"]
    )


def encode_control_packet(packet: BaseModel, max_bytes: int) -> bytes:
    line = packet.model_dump_json().encode("utf-8") + b"\n"
    if len(line) > max_bytes:
        raise ValueError("The complete private packet exceeds its byte allowance")
    return line


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
    server: HonoServerReader | ServerOutcome | None = None
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
