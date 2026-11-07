"""Which status follows from one phase's actual work, instruments and confirmed cleanup?"""

from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult

from .contracts import (
    Hardware,
    PhaseName,
    PipelineError,
    RunIdentity,
    ServerOutcome,
)
from .host_reader import MachineUsage
from .phase_contracts import PhaseEvidence, PhaseShutdown, phase_status
from .scorer_evidence import EVIDENCE_VERSION, ScorerApiEvidence


def build_evidence(
    evaluation: EvaluationResult | None,
    hardware: Hardware | None,
    machine: MachineUsage | None,
    shutdown: PhaseShutdown,
    errors: list[PipelineError],
    *,
    run: RunIdentity,
    phase: PhaseName,
    reference_summary_sha256: str,
    servers: tuple[ServerOutcome, ...] = (),
    generation_sha256: str | None = None,
    unieval: UnievalResult | None = None,
    scorer_apis: tuple[ScorerApiEvidence, ...] = (),
    evaluation_request_id: str | None = None,
    evaluation_correlation_id: str | None = None,
) -> PhaseEvidence:
    return PhaseEvidence(
        version=EVIDENCE_VERSION,
        run=run,
        phase=phase,
        status=phase_status(
            phase, evaluation, unieval, hardware, machine, shutdown, scorer_apis, tuple(errors)
        ),
        evaluation=evaluation,
        unieval=unieval,
        scorer_apis=scorer_apis,
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
