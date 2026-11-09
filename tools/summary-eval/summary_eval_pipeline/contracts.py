"""Which same-run generation, phase and combined results may this workflow write?"""

import hashlib
from datetime import timedelta
from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field, model_validator
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.read_api_health import ReadableApiHealth
from summary_evaluator.shared.contracts.base import (
    CommitId,
    ContextIdentity,
    Milliseconds,
    NativeContract,
    NonblankText,
    OutcomeStatus,
    PositiveCount,
    RelativePath,
    Sha256,
    Uuid4,
    validate_text,
)
from summary_evaluator.unieval.contracts.previous_selected_unieval_result import (
    PreviousSelectedUnievalResult,
)
from summary_evaluator.unieval.contracts.previous_unieval_result import (
    PreviousUnievalResult as UnievalResult,
)
from summary_evaluator.unieval.contracts.unieval_contract import DIMENSIONS
from summary_evaluator.unieval.contracts.unieval_result import (
    UnievalResult as CurrentUnievalResult,
)

from idhazh.contracts.app_config import ModelsFile

from .host_reader import HardwareRow, MachineUsage, measurement_complete

# These identities version disposable same-run files, not committed ledgers.
WORKFLOW_VERSION: Final = "2026-11-05"
WorkflowVersion = Literal["2026-11-05"]
PhaseName = Literal["generation", "evaluation"]
ServiceName = Literal["api", "hhem", "unieval", "host", "llama", "caller"]
# Cause codes are protocol identifiers with the same wire bound as context identities.
SourceCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")]
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
                    "change": "Generate natively and report only processes actually started.",
                },
                {
                    "version": "2026-11-04",
                    "change": "Bind evaluator results and safe preparation to one answer.",
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
    source_code: SourceCode | None = None

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
    reference_summary_sha256: Sha256
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
    reference_summary_sha256: Sha256
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
    worker_exit_confirmed: bool | None = Field(description="Observed HHEM worker exit.")
    unieval_worker_exit_confirmed: bool | None = Field(
        default=None, description="Observed UniEval worker exit, independent of HHEM."
    )
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


def has_completed_score(
    evaluation: EvaluationResult | None,
    unieval: UnievalResult | PreviousSelectedUnievalResult | CurrentUnievalResult | None,
) -> bool:
    return (evaluation is not None and evaluation.hhem is not None) or (
        unieval is not None
        and any(getattr(unieval.scores, dimension) is not None for dimension in DIMENSIONS)
    )


def phase_status(
    phase: PhaseName,
    evaluation: EvaluationResult | None,
    unieval: UnievalResult | None,
    hardware: Hardware | None,
    machine: MachineUsage | None,
    shutdown: ServiceShutdown,
    health: ApiHealth | None,
    errors: tuple[PipelineError, ...],
) -> OutcomeStatus:
    work = (
        evaluation is not None
        and evaluation.status == "complete"
        and unieval is not None
        and unieval.status == "complete"
        and health is not None
        and health.enabled_routes == ("hhem", "unieval")
        and health.status == "ready"
        and health.hhem.status == "ready"
        and health.unieval.status == "ready"
        if phase == "evaluation"
        else shutdown.llama_stopped is True
    )
    clean = shutdown.host_stopped is True and (
        (
            shutdown.api_stopped is True
            and (
                shutdown.worker_exit_confirmed is True
                and shutdown.unieval_worker_exit_confirmed is True
            )
        )
        if phase == "evaluation"
        else (
            shutdown.api_stopped is None
            and shutdown.worker_exit_confirmed is None
            and shutdown.unieval_worker_exit_confirmed is None
        )
    )
    complete = (
        work
        and clean
        and hardware is not None
        and hardware.status == "collected"
        and measurement_complete(machine)
        and not errors
    )
    if complete:
        return "complete"
    return "partial" if has_completed_score(evaluation, unieval) else "failed"


class PhaseEvidence(WorkflowContract):
    version: WorkflowVersion
    run: RunIdentity
    phase: PhaseName
    status: OutcomeStatus
    evaluation: EvaluationResult | None
    unieval: UnievalResult | None = None
    api_health: ReadableApiHealth | None = None
    evaluation_request_id: Uuid4 | None = None
    evaluation_correlation_id: Uuid4 | None = None
    reference_summary_sha256: Sha256
    hardware: Hardware | None
    machine: MachineUsage | None
    shutdown: ServiceShutdown
    servers: tuple[ServerOutcome, ...]
    errors: tuple[PipelineError, ...]
    generation_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def require_consistent_status(self) -> Self:
        expected = phase_status(
            self.phase,
            self.evaluation,
            self.unieval,
            self.hardware,
            self.machine,
            self.shutdown,
            self.api_health,
            self.errors,
        )
        if self.status != expected:
            raise ValueError("Status must describe actual work, measurements and cleanup")
        if self.phase == "generation" and (self.evaluation is not None or self.unieval is not None):
            raise ValueError("Generation does not score a summary")
        if self.phase == "generation" and (
            self.shutdown.api_stopped is not None
            or self.shutdown.worker_exit_confirmed is not None
            or self.shutdown.unieval_worker_exit_confirmed is not None
            or self.api_health is not None
            or any(server.server_name == "fastapi-server" for server in self.servers)
        ):
            raise ValueError("Generation starts no evaluation application or evaluator worker")
        for result in (self.evaluation, self.unieval):
            if result is None:
                continue
            if (
                self.generation_sha256 is None
                or self.reference_summary_sha256 is None
                or self.evaluation_request_id is None
                or self.evaluation_correlation_id is None
                or result.request_id != self.evaluation_request_id
                or result.correlation_id != self.evaluation_correlation_id
            ):
                raise ValueError("Scoring requires the bound receipt and actual request identities")
        if (
            self.unieval is not None
            and self.unieval.reference_summary_sha256 != self.reference_summary_sha256
        ):
            raise ValueError("UniEval must identify the independent reference")
        if self.api_health is not None:
            for name, result in (("hhem", self.evaluation), ("unieval", self.unieval)):
                observed = getattr(self.api_health, name)
                if observed.status == "ready" and (
                    observed.service_instance_id != self.api_health.service_instance_id
                ):
                    raise ValueError("Component readiness must identify this owned application")
                if result is not None and (
                    (result.model is not None and result.model != observed.model)
                    or (result.worker is not None and result.worker != observed.worker)
                ):
                    raise ValueError("Evaluator results must retain their observed loaded identity")
            hhem_worker, unieval_worker = (
                self.api_health.hhem.worker,
                self.api_health.unieval.worker,
            )
            if (
                hhem_worker is not None
                and unieval_worker is not None
                and hhem_worker.pid == unieval_worker.pid
            ):
                raise ValueError("The evaluators require independently owned worker processes")
        return self


class PipelineEvidence(WorkflowContract):
    version: WorkflowVersion
    status: OutcomeStatus
    prepared: PreparedRun | None
    generation: GenerationReceipt | None
    generation_phase: PhaseEvidence | None
    evaluation_phase: PhaseEvidence | None
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
            or generation.reference_summary_sha256 != self.prepared.reference_summary_sha256
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
                if observed is not None and (
                    observed.reference_summary_sha256 != generation.reference_summary_sha256
                ):
                    raise ValueError("Every phase must retain the independent reference identity")
        if phase is not None and phase.phase != "generation":
            raise ValueError("Generation evidence requires the generation phase")
        if evaluation is not None and evaluation.phase != "evaluation":
            raise ValueError("Evaluation evidence requires the evaluation phase")
        if (
            evaluation is not None
            and (evaluation.evaluation is not None or evaluation.unieval is not None)
            and (
                generation is None
                or generation.status != "complete"
                or phase is None
                or phase.shutdown.llama_stopped is not True
                or phase.shutdown.api_stopped is not None
            )
        ):
            raise ValueError("Scoring requires the current answer and confirmed native shutdown")
        score = evaluation is not None and has_completed_score(
            evaluation.evaluation, evaluation.unieval
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
