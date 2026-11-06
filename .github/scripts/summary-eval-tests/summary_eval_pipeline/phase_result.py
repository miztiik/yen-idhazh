"""Which status follows from one phase's actual work, instruments and confirmed cleanup?"""

from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult

from .contracts import (
    WORKFLOW_VERSION,
    Hardware,
    PhaseEvidence,
    PhaseName,
    PipelineError,
    RunIdentity,
    ServerOutcome,
    ServiceShutdown,
    phase_status,
)
from .host_reader import MachineUsage


def build_evidence(
    evaluation: EvaluationResult | None,
    hardware: Hardware | None,
    machine: MachineUsage | None,
    shutdown: ServiceShutdown,
    errors: list[PipelineError],
    *,
    run: RunIdentity,
    phase: PhaseName,
    reference_summary_sha256: str,
    servers: tuple[ServerOutcome, ...] = (),
    generation_sha256: str | None = None,
    unieval: UnievalResult | None = None,
    api_health: ApiHealth | None = None,
    evaluation_request_id: str | None = None,
    evaluation_correlation_id: str | None = None,
) -> PhaseEvidence:
    return PhaseEvidence(
        version=WORKFLOW_VERSION,
        run=run,
        phase=phase,
        status=phase_status(
            phase, evaluation, unieval, hardware, machine, shutdown, api_health, tuple(errors)
        ),
        evaluation=evaluation,
        unieval=unieval,
        api_health=api_health,
        evaluation_request_id=evaluation_request_id,
        evaluation_correlation_id=evaluation_correlation_id,
        reference_summary_sha256=reference_summary_sha256,
        hardware=hardware,
        machine=machine,
        shutdown=shutdown,
        servers=servers,
        errors=tuple(errors),
        generation_sha256=generation_sha256,
    )
