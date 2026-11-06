"""Which native machine fields do the workflow tasks and report consume?"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, RootModel
from summary_evaluator.shared.contracts.base import Count, Milliseconds, NativeContract

UnavailableReason = Literal[
    "unsupported_platform",
    "missing_file",
    "permission_denied",
    "too_large",
    "invalid_data",
    "missing_field",
    "counter_reset",
    "no_ticks",
    "configured_off",
    "not_configured",
    "process_exited",
    "pid_reused",
    "clock_ticks_unavailable",
    "no_interval",
]
TaskEndReason = Literal[
    "task_settled",
    "explicit_stop",
    "owner_exited",
    "pid_reused",
    "expired",
    "service_stopped",
    "start_aborted",
]
Percentage = Annotated[float, Field(ge=0, le=100)]
NonnegativeNumber = Annotated[float, Field(ge=0)]


class HostReader(NativeContract):
    """Leave validation of unconsumed host fields to their native Zod schema."""

    model_config = ConfigDict(extra="ignore")


class CpuUsage(HostReader):
    user: Percentage
    system: Percentage


class CpuPresent(HostReader):
    value: CpuUsage
    reason: Literal[None]


class CpuMissing(HostReader):
    value: None
    reason: UnavailableReason


class CpuObservation(RootModel[CpuPresent | CpuMissing]):
    @property
    def value(self) -> CpuUsage | None:
        return self.root.value


class HardwareRow(HostReader):
    cpu_model: str | None
    cpu_logical_processors: Count | None
    cpu_physical_cores: Count | None
    machine_memory_total_mib: NonnegativeNumber | None


class HonoServerReader(HostReader):
    server_name: Literal["hono-server"]
    startup: Literal["not_started", "ready", "failed"]
    startup_ms: Milliseconds | None
    shutdown: Literal["not_started", "stopped", "forced", "failed"]
    exit_code: int | None
    log_filename: str
    log_available: bool
    error_code: str | None
    cleanup_error_code: str | None


class MachineMemory(HostReader):
    total: Count | None
    available: Count | None


class MachineSample(HostReader):
    phase: Literal["opening", "poll", "closing"]
    memory_kb: MachineMemory
    unavailable: dict[str, UnavailableReason]


class MachineUsage(HostReader):
    outcome: Literal["success", "error", "cancelled"]
    end_reason: TaskEndReason
    started_at: AwareDatetime
    finished_at: AwareDatetime
    elapsed_ms: Milliseconds
    cpu: CpuObservation
    machine_available_min_kb: Count | None
    unavailable: dict[str, UnavailableReason]
    samples: tuple[MachineSample, ...] = Field(min_length=2)


def measurement_complete(profile: MachineUsage | None) -> bool:
    return (
        profile is not None
        and profile.outcome != "cancelled"
        and profile.end_reason == "explicit_stop"
        and profile.cpu.value is not None
        and profile.machine_available_min_kb is not None
        and profile.samples[-1].phase == "closing"
        and profile.samples[-1].memory_kb.total is not None
        and profile.samples[-1].memory_kb.available is not None
    )
