"""Which native host-profile fields does the manual evaluator consume?"""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    model_validator,
)

from .base import Milliseconds, NativeContract

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
TaskOutcome = Literal["success", "error", "cancelled"]
TaskEndReason = Literal[
    "task_settled",
    "explicit_stop",
    "owner_exited",
    "pid_reused",
    "expired",
    "service_stopped",
    "start_aborted",
]
HostUuid = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    ),
]
# Host counters use JavaScript's largest exactly representable integer.
MAX_SAFE_INTEGER = 9007199254740991
SafeCount = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
HostText = Annotated[str, StringConstraints(strict=True, min_length=1)]


def require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("A native host instant must be UTC")
    return value


HostInstant = Annotated[AwareDatetime, AfterValidator(require_utc)]


class HostProjection(NativeContract):
    """Validate consumed fields and discard native fields this caller does not use."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "version": "2026-11-02",
            "changelog": [
                {"version": "2026-11-02", "change": "Read the consumed native task-profile fields."}
            ],
        },
    )


class TaskIdentity(HostProjection):
    pipeline_name: HostText
    task_name: HostText
    run_id: HostText
    correlation_id: HostUuid
    request_id: HostUuid


class ProcessPin(HostProjection):
    pid: Annotated[SafeCount, Field(gt=0)]
    start_ticks: Annotated[str, StringConstraints(strict=True, pattern=r"^\d+$")]


class ProcessCpuValue(HostProjection):
    cpu_time_ms: Milliseconds
    percent_one_core: Milliseconds


class AvailableCpu(HostProjection):
    reason: None
    value: ProcessCpuValue


class UnavailableCpu(HostProjection):
    reason: UnavailableReason
    value: None


class ProcessProfile(HostProjection):
    cpu_interval_ms: Milliseconds
    cpu: Annotated[AvailableCpu | UnavailableCpu, Field(discriminator="reason")]
    sampled_rss_max_kb: SafeCount | None
    unavailable: dict[str, UnavailableReason]

    @model_validator(mode="after")
    def require_ram_unavailable_reason(self) -> Self:
        if self.sampled_rss_max_kb is None and "sampled_rss_max_kb" not in self.unavailable:
            raise ValueError("A missing worker RAM reading requires its native reason")
        return self


class ProfileProcesses(HostProjection):
    worker: ProcessProfile


class TaskProfile(HostProjection):
    identity: TaskIdentity
    outcome: TaskOutcome
    end_reason: TaskEndReason
    started_at: HostInstant = Field(description="Opening observation instant in UTC.")
    finished_at: HostInstant = Field(description="Closing observation instant in UTC.")
    elapsed_ms: Milliseconds
    unavailable: dict[str, UnavailableReason]
    processes: ProfileProcesses


class DisabledProfile(HostProjection):
    status: Literal["disabled"]
    reason: Literal["configured_off"]


class StartedProfile(HostProjection):
    status: Literal["started"]
    handle: HostUuid
    expires_at: HostInstant = Field(description="Safety expiry instant in UTC.")
    target: ProcessPin


class StoppedProfile(HostProjection):
    status: Literal["stopped"]
    handle: HostUuid
    end_reason: TaskEndReason
    profile: TaskProfile

    @model_validator(mode="after")
    def require_matching_end_reason(self) -> Self:
        if self.end_reason != self.profile.end_reason:
            raise ValueError("The stop and profile must describe the same ending")
        return self


class StartProfileResponse(
    RootModel[Annotated[DisabledProfile | StartedProfile, Field(discriminator="status")]]
):
    pass


class StopProfileResponse(
    RootModel[Annotated[DisabledProfile | StoppedProfile, Field(discriminator="status")]]
):
    pass
