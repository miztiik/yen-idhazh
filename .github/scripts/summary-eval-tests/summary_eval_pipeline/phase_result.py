"""Which status follows from one phase's actual work, instruments and confirmed cleanup?"""

from hhem_evaluator.contracts.evaluation_result import EvaluationResult

from .contracts import (
    WORKFLOW_VERSION,
    Hardware,
    PhaseEvidence,
    PhaseName,
    PipelineError,
    RunIdentity,
    ServerOutcome,
    ServiceShutdown,
)
from .host_reader import MachineUsage, measurement_complete


def build_evidence(
    evaluation: EvaluationResult | None,
    hardware: Hardware | None,
    machine: MachineUsage | None,
    shutdown: ServiceShutdown,
    errors: list[PipelineError],
    *,
    run: RunIdentity,
    phase: PhaseName,
    servers: tuple[ServerOutcome, ...] = (),
    generation_sha256: str | None = None,
) -> PhaseEvidence:
    work = (
        evaluation is not None and evaluation.status == "complete"
        if phase == "evaluation"
        else shutdown.llama_stopped is True
    )
    complete = (
        work
        and hardware is not None
        and hardware.status == "collected"
        and measurement_complete(machine)
        and not errors
        and shutdown.api_stopped is True
        and shutdown.host_stopped is True
        and (phase != "evaluation" or shutdown.worker_exit_confirmed is True)
    )
    return PhaseEvidence(
        version=WORKFLOW_VERSION,
        run=run,
        phase=phase,
        status="complete"
        if complete
        else ("partial" if evaluation is not None and evaluation.hhem is not None else "failed"),
        evaluation=evaluation,
        hardware=hardware,
        machine=machine,
        shutdown=shutdown,
        servers=servers,
        errors=tuple(errors),
        generation_sha256=generation_sha256,
    )
