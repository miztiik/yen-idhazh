"""Which body-free evidence belongs to one pipeline evaluation and host measurement?"""

from typing import Literal, Self

from pydantic import Field, model_validator

from hhem_evaluator.contracts.base import (
    SCHEMA_VERSION,
    NativeContract,
    OutcomeStatus,
    SchemaVersion,
)
from hhem_evaluator.contracts.evaluation_result import EvaluationResult

from .host_reader import HardwareRow, MachineUsage, measurement_complete

FailureCode = Literal[
    "INPUT_INVALID",
    "INPUT_TOO_LARGE",
    "STARTUP_FAILED",
    "STARTUP_IDENTITY_MISMATCH",
    "CHILD_EXITED",
    "CHILD_PROTOCOL_FAILED",
    "HEALTH_FAILED",
    "HTTP_FAILED",
    "RESPONSE_INVALID",
    "RESPONSE_TOO_LARGE",
    "EVALUATION_FAILED",
    "SERVICE_STOP_FAILED",
    "EVENT_STREAM_FAILED",
    "HOST_FAILED",
    "REPORT_FAILED",
]
FailurePhase = Literal["input", "startup", "health", "evaluation", "host", "cleanup", "report"]
FAILURE_MESSAGES: dict[FailureCode, str] = {
    "INPUT_INVALID": "The named dispatch inputs are invalid.",
    "INPUT_TOO_LARGE": "The dispatch input exceeds its byte allowance.",
    "STARTUP_FAILED": "An owned service did not become ready.",
    "STARTUP_IDENTITY_MISMATCH": "Readiness did not match the owned startup identity.",
    "CHILD_EXITED": "An owned service exited before its work finished.",
    "CHILD_PROTOCOL_FAILED": "An owned service returned invalid control metadata.",
    "HEALTH_FAILED": "The owned evaluator health check failed.",
    "HTTP_FAILED": "A bounded local HTTP operation failed.",
    "RESPONSE_INVALID": "A local response failed native validation.",
    "RESPONSE_TOO_LARGE": "A local response exceeded its byte allowance.",
    "EVALUATION_FAILED": "The evaluator returned an error HTTP result.",
    "SERVICE_STOP_FAILED": "An owned service did not confirm clean shutdown.",
    "EVENT_STREAM_FAILED": "The owned evaluator event stream failed validation.",
    "HOST_FAILED": "Shared host collection did not complete.",
    "REPORT_FAILED": "The pipeline report could not be written.",
}


class PipelineError(NativeContract):
    code: FailureCode
    phase: FailurePhase
    service: Literal["hhem", "host", "caller"]
    http_status: int | None = Field(default=None, ge=100, le=599)
    message: str

    @model_validator(mode="after")
    def require_safe_message(self) -> Self:
        if self.message != FAILURE_MESSAGES[self.code]:
            raise ValueError("A pipeline error requires its fixed safe message")
        return self


class Hardware(HardwareRow):
    status: Literal["collected", "disabled", "failed"]
    unavailable: dict[str, str]
    reason: Literal["configured_off", "collection_failed"] | None


class ServiceShutdown(NativeContract):
    hhem_stopped: bool | None
    host_stopped: bool | None
    worker_exit_confirmed: bool | None


class PipelineEvidence(NativeContract):
    """Keep evaluator output independent of Markdown and input-text publication."""

    model_config = {
        "json_schema_extra": {
            "version": SCHEMA_VERSION,
            "changelog": [
                {
                    "version": SCHEMA_VERSION,
                    "change": "Declare pipeline evaluation and machine evidence.",
                }
            ],
        },
    }

    version: SchemaVersion
    status: OutcomeStatus
    evaluation: EvaluationResult | None
    hardware: Hardware | None
    machine: MachineUsage | None
    shutdown: ServiceShutdown
    unieval: Literal["not_implemented"]
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_consistent_status(self) -> Self:
        score = self.evaluation is not None and self.evaluation.hhem is not None
        complete = (
            self.evaluation is not None
            and self.evaluation.status == "complete"
            and self.hardware is not None
            and self.hardware.status == "collected"
            and measurement_complete(self.machine)
            and self.shutdown.hhem_stopped is True
            and self.shutdown.host_stopped is True
            and self.shutdown.worker_exit_confirmed is True
            and not self.errors
        )
        expected = "complete" if complete else "partial" if score else "failed"
        if self.status != expected:
            raise ValueError("Status must describe actual evaluation, host and cleanup evidence")
        return self
