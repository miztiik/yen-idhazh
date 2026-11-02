"""When does one body-free manual report prove scoring and worker resource coverage?"""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from .base import SCHEMA_VERSION, NativeContract, OutcomeStatus, PositiveCount, SchemaVersion
from .evaluation_result import EvaluationResult
from .host_profile_reader import TaskProfile
from .worker_identity import WorkerIdentity

ResourceReason = Literal[
    "configured_off",
    "pin_unavailable",
    "profile_start_failed",
    "profile_stop_failed",
    "worker_replaced",
    "profile_interrupted",
    "measurement_unavailable",
]
ResourceStatus = Literal["complete", "incomplete", "unavailable"]
FailureCode = Literal[
    "INPUT_INVALID",
    "INPUT_TOO_LARGE",
    "SETTINGS_INVALID",
    "STARTUP_FAILED",
    "STARTUP_IDENTITY_MISMATCH",
    "CHILD_EXITED",
    "CHILD_PROTOCOL_FAILED",
    "HEALTH_FAILED",
    "HTTP_FAILED",
    "RESPONSE_INVALID",
    "RESPONSE_TOO_LARGE",
    "EVALUATION_FAILED",
    "PROFILE_START_FAILED",
    "PROFILE_STOP_FAILED",
    "SERVICE_STOP_FAILED",
    "EVENT_STREAM_FAILED",
    "REPORT_WRITE_FAILED",
]
FailurePhase = Literal["input", "startup", "health", "evaluation", "profile", "cleanup", "report"]

# These are protocol messages; raw exceptions and response bodies never enter a report.
FAILURE_MESSAGES: dict[FailureCode, str] = {
    "INPUT_INVALID": "The named dispatch inputs are invalid.",
    "INPUT_TOO_LARGE": "The dispatch input exceeds its byte allowance.",
    "SETTINGS_INVALID": "The committed manual settings are invalid.",
    "STARTUP_FAILED": "An owned service did not become ready.",
    "STARTUP_IDENTITY_MISMATCH": "Readiness did not match the owned startup identity.",
    "CHILD_EXITED": "An owned service exited before its work finished.",
    "CHILD_PROTOCOL_FAILED": "An owned service returned invalid control metadata.",
    "HEALTH_FAILED": "The owned evaluator health check failed.",
    "HTTP_FAILED": "A bounded local HTTP operation failed.",
    "RESPONSE_INVALID": "A local response failed native validation.",
    "RESPONSE_TOO_LARGE": "A local response exceeded its byte allowance.",
    "EVALUATION_FAILED": "The evaluator returned an error HTTP result.",
    "PROFILE_START_FAILED": "The worker resource profile could not start.",
    "PROFILE_STOP_FAILED": "The worker resource profile could not close.",
    "SERVICE_STOP_FAILED": "An owned service did not confirm clean shutdown.",
    "EVENT_STREAM_FAILED": "The owned evaluator event stream failed validation.",
    "REPORT_WRITE_FAILED": "The body-free report could not be written.",
}


class WorkflowError(NativeContract):
    code: FailureCode
    phase: FailurePhase
    service: Literal["hhem", "host", "caller"]
    http_status: int | None = Field(default=None, ge=100, le=599)
    message: str

    @model_validator(mode="after")
    def require_safe_message(self) -> Self:
        if self.message != FAILURE_MESSAGES[self.code]:
            raise ValueError("A workflow error requires its fixed safe message")
        return self


class RunnerConditions(NativeContract):
    """Describe the observed host without adding a CPU or RAM collector."""

    system: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._ -]{1,128}$")]
    release: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._+ -]{1,128}$")]
    architecture: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._ -]{1,128}$")]
    logical_cpu_count: PositiveCount | None


class ServiceShutdown(NativeContract):
    hhem_stopped: bool | None
    host_stopped: bool | None
    worker_exit_confirmed: bool | None


class ResourceEvidence(NativeContract):
    status: ResourceStatus
    profile: TaskProfile | None
    initial_worker: WorkerIdentity | None
    final_worker: WorkerIdentity | None
    reason: ResourceReason | None
    runner: RunnerConditions
    shutdown: ServiceShutdown

    @model_validator(mode="after")
    def require_honest_coverage(self) -> Self:
        if (self.status == "complete") != (self.reason is None):
            raise ValueError("Incomplete or unavailable coverage requires its reason")
        if self.status == "complete":
            profile = self.profile
            if (
                profile is None
                or self.initial_worker is None
                or self.initial_worker.start_ticks is None
                or self.final_worker != self.initial_worker
                or profile.end_reason != "explicit_stop"
                or profile.outcome == "cancelled"
                or profile.processes.worker.cpu.reason is not None
                or profile.processes.worker.sampled_rss_max_kb is None
            ):
                raise ValueError("Complete coverage requires one uninterrupted measured worker")
        if (
            self.status == "incomplete"
            and self.profile is None
            and self.reason
            not in (
                "profile_stop_failed",
                "worker_replaced",
            )
        ):
            raise ValueError("An incomplete interval requires an observed profile")
        return self


class WorkflowReport(NativeContract):
    """Keep transient score evidence even when measurement or shutdown fails."""

    model_config = {
        "json_schema_extra": {
            "version": SCHEMA_VERSION,
            "changelog": [
                {"version": SCHEMA_VERSION, "change": "Declare body-free manual reports."}
            ],
        },
    }

    version: SchemaVersion
    status: OutcomeStatus
    evaluation: EvaluationResult | None
    resources: ResourceEvidence
    errors: tuple[WorkflowError, ...]

    @model_validator(mode="after")
    def require_consistent_status(self) -> Self:
        has_score = self.evaluation is not None and self.evaluation.hhem is not None
        complete = (
            has_score
            and self.evaluation is not None
            and self.evaluation.status == "complete"
            and self.resources.status == "complete"
            and not self.errors
        )
        expected = "complete" if complete else "partial" if has_score else "failed"
        if self.status != expected:
            raise ValueError("Report status must retain the actual score and coverage outcome")
        return self
