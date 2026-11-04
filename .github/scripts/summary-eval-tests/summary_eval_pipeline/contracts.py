"""Which same-run generation, phase and combined results may this workflow write?"""

import hashlib
from datetime import timedelta
from typing import Annotated, Final, Literal, Self

from hhem_evaluator.contracts.base import (
    CommitId,
    ContextIdentity,
    Milliseconds,
    NativeContract,
    NonblankText,
    OutcomeStatus,
    PositiveCount,
    RelativePath,
    Sha256,
    validate_text,
)
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field, model_validator

from idhazh.contracts.app_config import ModelsFile

from .host_reader import HardwareRow, MachineUsage, measurement_complete

# These identities version disposable same-run files, not committed ledgers.
WORKFLOW_VERSION: Final = "2026-11-04"
WorkflowVersion = Literal["2026-11-04"]
PhaseName = Literal["generation", "evaluation"]
ServiceName = Literal["api", "hhem", "host", "llama", "caller"]
FailureCode = Literal[
    "INPUT_INVALID",
    "INPUT_TOO_LARGE",
    "MODEL_INVALID",
    "ASSET_FAILED",
    "ASSET_AUTH_MISSING",
    "RECEIPT_INVALID",
    "GENERATION_FAILED",
    "GENERATION_INCOMPLETE",
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
    "TASK_CANCELLED",
    "RESULT_WRITE_FAILED",
]
FailurePhase = Literal[
    "input",
    "preparation",
    "startup",
    "health",
    "generation",
    "evaluation",
    "host",
    "cleanup",
    "report",
]
FAILURE_MESSAGES: dict[FailureCode, str] = {
    "INPUT_INVALID": "The named dispatch inputs are invalid.",
    "INPUT_TOO_LARGE": "The dispatch input exceeds its byte allowance.",
    "MODEL_INVALID": "The selected model declaration is invalid.",
    "ASSET_FAILED": "The declared native assets could not be prepared.",
    "ASSET_AUTH_MISSING": "Preparation requires GITHUB_TOKEN for the pinned runtime lookup.",
    "RECEIPT_INVALID": "The saved generation does not match this run, source and model.",
    "GENERATION_FAILED": "The summarizer did not return a valid final answer.",
    "GENERATION_INCOMPLETE": "The summarizer did not finish its final answer.",
    "STARTUP_FAILED": "An owned service did not become ready.",
    "STARTUP_IDENTITY_MISMATCH": "Readiness did not match the owned startup identity.",
    "CHILD_EXITED": "An owned service exited before its work finished.",
    "CHILD_PROTOCOL_FAILED": "An owned service returned invalid control metadata.",
    "HEALTH_FAILED": "An owned component health check failed.",
    "HTTP_FAILED": "A bounded local HTTP operation failed.",
    "RESPONSE_INVALID": "A local response failed native validation.",
    "RESPONSE_TOO_LARGE": "A local response exceeded its byte allowance.",
    "EVALUATION_FAILED": "The evaluator returned an error HTTP result.",
    "SERVICE_STOP_FAILED": "An owned service did not confirm clean shutdown.",
    "EVENT_STREAM_FAILED": "An owned diagnostic stream failed validation.",
    "HOST_FAILED": "Shared host collection did not complete.",
    "REPORT_FAILED": "The workflow report could not be written.",
    "TASK_CANCELLED": "The workflow task was cancelled.",
    "RESULT_WRITE_FAILED": "A same-run result could not be saved.",
}


class WorkflowContract(NativeContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": WORKFLOW_VERSION,
            "readCompatibility": "current_only; disposable same-run artifacts",
            "changelog": [
                {
                    "version": WORKFLOW_VERSION,
                    "change": "Record preparation outcomes and safe asset failures.",
                },
                {
                    "version": WORKFLOW_VERSION,
                    "change": "Use native string-length constraints for generation text.",
                },
                {
                    "version": WORKFLOW_VERSION,
                    "change": "Retain the selected run when generation has not started.",
                },
                {
                    "version": WORKFLOW_VERSION,
                    "change": "Name shared API shutdown separately from HHEM worker exit.",
                },
                {
                    "version": "2026-11-02",
                    "change": "Earlier changes are in this file's git history.",
                },
            ],
        }
    )


class PipelineError(WorkflowContract):
    code: FailureCode
    phase: FailurePhase
    service: ServiceName
    http_status: int | None = None
    message: str

    @model_validator(mode="after")
    def require_safe_message(self) -> Self:
        if self.message != FAILURE_MESSAGES[self.code]:
            raise ValueError("A workflow error requires its fixed safe message")
        if self.http_status is not None and not 100 <= self.http_status <= 599:
            raise ValueError("Expected an HTTP status")
        return self


class RunIdentity(WorkflowContract):
    run_id: ContextIdentity
    attempt: PositiveCount
    git_sha: CommitId
    started_at: AwareDatetime

    @model_validator(mode="after")
    def require_utc(self) -> Self:
        if self.started_at.utcoffset() != timedelta(0):
            raise ValueError("The run-start instant must use UTC")
        return self


class ModelSelection(WorkflowContract):
    models_file: ModelsFile
    declaration_sha256: Sha256
    model_id: ContextIdentity
    repo: NonblankText
    revision: CommitId
    filename: RelativePath
    sha256: Sha256
    quantisation: NonblankText


class PreparedRun(WorkflowContract):
    version: WorkflowVersion
    run: RunIdentity
    selected: ModelSelection
    source_sha256: Sha256
    status: Literal["pending", "complete", "failed"]
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_preparation_outcome(self) -> Self:
        if (self.status == "failed") != bool(self.errors):
            raise ValueError("Failed preparation requires its original safe errors")
        if any(error.phase != "preparation" for error in self.errors):
            raise ValueError("Preparation errors must identify their own phase")
        return self


class LoadedModel(WorkflowContract):
    model_id: ContextIdentity
    weights_path: RelativePath
    sha256: Sha256
    pid: PositiveCount


# The native decoder refuses unanchored patterns; semantic text checks still run after decoding.
AnswerText = Annotated[str, Field(min_length=1), AfterValidator(validate_text)]


class GeneratedAnswer(WorkflowContract):
    title: AnswerText
    summary: AnswerText


class GenerationReceipt(WorkflowContract):
    version: WorkflowVersion
    run: RunIdentity
    selected: ModelSelection
    loaded: LoadedModel | None
    source_sha256: Sha256
    summary_sha256: Sha256 | None
    summary_text: NonblankText | None
    status: Literal["complete", "failed"]
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_final_answer(self) -> Self:
        if self.status == "complete":
            if self.loaded is None or self.summary_text is None or self.errors:
                raise ValueError("Completed generation requires its loaded model and final answer")
            if (
                self.loaded.model_id != self.selected.model_id
                or self.loaded.sha256 != self.selected.sha256
                or self.loaded.weights_path != f"backend/models/{self.selected.filename}"
                or self.summary_sha256 != text_sha256(self.summary_text)
            ):
                raise ValueError("The generated answer must bind the loaded model and exact bytes")
        elif self.summary_text is not None or self.summary_sha256 is not None or not self.errors:
            raise ValueError("Failed generation has errors and no accepted answer")
        return self


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Hardware(HardwareRow):
    status: Literal["collected", "disabled", "failed"]
    unavailable: dict[str, str]
    reason: Literal["configured_off", "collection_failed"] | None


class ServiceShutdown(WorkflowContract):
    api_stopped: bool | None
    host_stopped: bool | None
    worker_exit_confirmed: bool | None
    llama_stopped: bool | None = None


class ServerOutcome(WorkflowContract):
    server_name: Literal["hono-server", "fastapi-server", "llama-server"]
    startup: Literal["not_started", "ready", "failed"]
    startup_ms: Milliseconds | None
    shutdown: Literal["not_started", "stopped", "forced", "failed"]
    exit_code: int | None
    log_filename: RelativePath | None
    log_available: bool
    error_code: str | None = None
    cleanup_error_code: str | None = None


class PhaseEvidence(WorkflowContract):
    version: WorkflowVersion
    run: RunIdentity
    phase: PhaseName
    status: OutcomeStatus
    evaluation: EvaluationResult | None
    hardware: Hardware | None
    machine: MachineUsage | None
    shutdown: ServiceShutdown
    servers: tuple[ServerOutcome, ...]
    errors: tuple[PipelineError, ...]
    generation_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def require_consistent_status(self) -> Self:
        score = self.evaluation is not None and self.evaluation.hhem is not None
        work = (
            self.evaluation is not None and self.evaluation.status == "complete"
            if self.phase == "evaluation"
            else self.shutdown.llama_stopped is True
        )
        clean = (
            self.shutdown.api_stopped is True
            and self.shutdown.host_stopped is True
            and (self.phase != "evaluation" or self.shutdown.worker_exit_confirmed is True)
        )
        complete = (
            work
            and clean
            and self.hardware is not None
            and self.hardware.status == "collected"
            and measurement_complete(self.machine)
            and not self.errors
        )
        expected = "complete" if complete else "partial" if score else "failed"
        if self.status != expected:
            raise ValueError("Status must describe actual work, measurements and cleanup")
        if self.phase == "generation" and self.evaluation is not None:
            raise ValueError("Generation does not score a summary")
        if self.evaluation is not None and self.generation_sha256 is None:
            raise ValueError("Scoring evidence requires the exact generation receipt identity")
        return self


class PipelineEvidence(WorkflowContract):
    version: WorkflowVersion
    status: OutcomeStatus
    prepared: PreparedRun | None
    generation: GenerationReceipt | None
    generation_phase: PhaseEvidence | None
    evaluation_phase: PhaseEvidence | None
    unieval: Literal["not_run"]
    errors: tuple[PipelineError, ...]

    @model_validator(mode="after")
    def require_consistent_status(self) -> Self:
        generation, phase, evaluation = (
            self.generation,
            self.generation_phase,
            self.evaluation_phase,
        )
        if generation is not None and (
            self.prepared is None
            or self.prepared.status != "complete"
            or generation.run != self.prepared.run
            or generation.selected != self.prepared.selected
            or generation.source_sha256 != self.prepared.source_sha256
        ):
            raise ValueError("Generation requires the captured run's completed preparation")
        if (
            self.prepared is not None
            and self.prepared.status != "complete"
            and (generation is not None or phase is not None or evaluation is not None)
        ):
            raise ValueError("Incomplete preparation cannot claim model-phase results")
        if generation is not None:
            for observed in (phase, evaluation):
                if observed is not None and observed.run != generation.run:
                    raise ValueError("Every phase must belong to the same run")
                if (
                    observed is not None
                    and observed.generation_sha256 is not None
                    and (observed.generation_sha256 != text_sha256(generation.model_dump_json()))
                ):
                    raise ValueError("Every phase must retain the exact saved generation")
        if phase is not None and phase.phase != "generation":
            raise ValueError("Generation evidence requires the generation phase")
        if evaluation is not None and evaluation.phase != "evaluation":
            raise ValueError("Evaluation evidence requires the evaluation phase")
        if (
            evaluation is not None
            and evaluation.evaluation is not None
            and (
                generation is None
                or generation.status != "complete"
                or phase is None
                or phase.shutdown.llama_stopped is not True
            )
        ):
            raise ValueError("Scoring requires the current answer and confirmed native shutdown")
        score = (
            evaluation is not None
            and evaluation.evaluation is not None
            and evaluation.evaluation.hhem is not None
        )
        complete = (
            generation is not None
            and generation.status == "complete"
            and phase is not None
            and phase.status == "complete"
            and evaluation is not None
            and evaluation.status == "complete"
            and not self.errors
        )
        if self.status != ("complete" if complete else "partial" if score else "failed"):
            raise ValueError("Combined status must retain every phase failure")
        return self
