"""Build literal evidence contract inputs, never observations of model or API processes."""

import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from summary_eval_pipeline.contracts import (
    WORKFLOW_VERSION,
    GenerationReceipt,
    Hardware,
    LoadedModel,
    ModelSelection,
    PipelineError,
    PreparedRun,
    RunIdentity,
    ServerOutcome,
    text_sha256,
)
from summary_eval_pipeline.host_reader import MachineUsage
from summary_eval_pipeline.inputs import ManualInputs
from summary_eval_pipeline.phase_contracts import PhaseShutdown
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.report_contracts import (
    PipelineDocument,
    PipelineEvidence,
    PipelineResult,
)
from summary_eval_pipeline.scorer_evidence import EVIDENCE_VERSION, ScorerApiEvidence
from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION
from summary_evaluator.hhem.contracts.evaluate_request import EffectiveSettings
from summary_evaluator.hhem.contracts.evaluation_progress import (
    EvaluationTimings,
    EvaluationWindows,
    WindowCounts,
)
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity, RuntimeVersions
from summary_evaluator.hhem.contracts.service_health import ServiceHealth
from summary_evaluator.serve_http.contracts.api_health import ApiHealth, DisabledEvaluatorHealth
from summary_evaluator.shared.contracts.process_identity import ProcessIdentity
from summary_evaluator.shared.contracts.server_contract import SERVER_SCHEMA_VERSION
from summary_evaluator.shared.contracts.service_settings import ListenerSettings
from summary_evaluator.shared.contracts.worker_exit import WorkerExit
from summary_evaluator.shared.contracts.worker_identity import WorkerIdentity
from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_request import EffectiveUnievalControls
from summary_evaluator.unieval.contracts.unieval_result import (
    DimensionWork,
    UnievalHealth,
    UnievalModelIdentity,
    UnievalResult,
    UnievalRuntimeVersions,
    UnievalScores,
    UnievalTimings,
    UnievalWork,
)

REQUEST_ID = "12345678-1234-4234-8234-123456789abc"
CORRELATION_ID = "87654321-4321-4321-8321-cba987654321"
HHEM_INSTANCE = "11111111-2222-4333-8444-555555555555"
UNIEVAL_INSTANCE = "99999999-8888-4777-8666-555555555555"


def scorer_api_example(
    scorer: Literal["hhem", "unieval"],
    result: EvaluationResult | UnievalResult | None = None,
    *,
    errors: tuple[PipelineError, ...] = (),
    stopped: bool | None = True,
    log_file: str | None = None,
) -> ScorerApiEvidence:
    instance = HHEM_INSTANCE if scorer == "hhem" else UNIEVAL_INSTANCE
    disabled = DisabledEvaluatorHealth()
    health: ApiHealth | None = None
    if result is not None:
        common = {
            "service_instance_id": instance, "status": "ready",
            "worker": result.worker, "model": result.model,
            "queue_depth": 0, "queue_capacity": 1, "failure_code": None,
        }
        health = ApiHealth(
            version=SERVER_SCHEMA_VERSION,
            service_instance_id=instance,
            enabled_routes=(scorer,),
            status="ready",
            hhem=ServiceHealth.model_validate({"version": SCHEMA_VERSION, **common})
            if scorer == "hhem" else disabled,
            unieval=UnievalHealth.model_validate({"version": UNIEVAL_VERSION, **common})
            if scorer == "unieval" else disabled,
            coverage=disabled,
            log_file=log_file,
            log_available=log_file is not None,
        )
    worker = result.worker if result is not None else None
    return ScorerApiEvidence(
        scorer=scorer,
        listener=ListenerSettings(
            host="127.0.0.1", port=3010 if scorer == "hhem" else 3011,
            max_body_bytes=10000, body_read_timeout_ms=1000,
        ),
        process=ProcessIdentity(
            pid=2100 if scorer == "hhem" else 2101,
            start_ticks="1000", pin_unavailable_reason=None,
        ) if result is not None else None,
        service_instance_id=instance if result is not None else None,
        health=health,
        worker_exit=WorkerExit(
            pid=worker.pid if worker is not None else None,
            exit_code=0 if worker is not None and stopped else None,
            confirmed=stopped if worker is not None and stopped is not None
            else False if worker is not None else None,
        ),
        outcome=ServerOutcome(
            server_name="fastapi-server",
            startup="ready" if result is not None else "failed" if errors else "not_started",
            startup_ms=10.0 if result is not None or errors else None,
            shutdown="stopped" if result is not None and stopped is True
            else "failed" if result is not None and stopped is False else "not_started",
            exit_code=0 if result is not None and stopped else None,
            log_filename=log_file,
            log_available=log_file is not None,
        ),
        errors=errors,
    )


def in_memory_pipeline() -> tuple[ManualInputs, PipelineEvidence]:
    inputs = ManualInputs(source_text="Source.", reference_summary_text="Reference.")
    run = RunIdentity(
        run_id="contract-run", attempt=1, git_sha="a" * 40,
        started_at=datetime(2026, 11, 7, tzinfo=UTC),
    )
    selected = ModelSelection(
        models_file="models/contract.json", declaration_sha256="b" * 64,
        model_id="native-model", repo="project/model", revision="a" * 40,
        filename="weights.gguf", sha256="c" * 64, quantisation="contract",
    )
    prepared = PreparedRun(
        version=WORKFLOW_VERSION, run=run, selected=selected,
        source_sha256=text_sha256(inputs.source_text),
        reference_summary_sha256=text_sha256(inputs.reference_summary_text),
        status="complete", errors=(),
    )
    receipt = GenerationReceipt(
        version=WORKFLOW_VERSION, run=run, selected=selected,
        loaded=LoadedModel(
            model_id=selected.model_id, weights_path=f"backend/models/{selected.filename}",
            sha256=selected.sha256, pid=123,
        ),
        source_sha256=prepared.source_sha256,
        reference_summary_sha256=prepared.reference_summary_sha256,
        summary_sha256=text_sha256("Summary."), summary_text="Summary.",
        status="complete", errors=(),
    )
    receipt_hash = text_sha256(receipt.model_dump_json())
    worker = WorkerIdentity(generation=1, pid=1234, start_ticks="5000", pin_unavailable_reason=None)
    hhem = EvaluationResult(
        version=SCHEMA_VERSION, status="complete", execution_id=HHEM_INSTANCE,
        request_id=REQUEST_ID, correlation_id=CORRELATION_ID,
        terminal_event_id="c6684c7e-d04f-5630-a3cd-711a03154752",
        hhem=0.0, hhem_full=None, hhem_delta=None,
        effective_settings=EffectiveSettings(
            chunk_words=10, chunk_overlap_words=0, hhem_full=False, include_window_details=False,
        ),
        windows=EvaluationWindows(
            primary=WindowCounts(planned=1, scored=1), full=None, full_reused_primary=False,
        ),
        model=ModelIdentity(
            reference="project/hhem", configured_revision="a" * 40, loaded_revision="a" * 40,
            foundation_reference="project/foundation", foundation_revision="a" * 40,
            runtime_versions=RuntimeVersions(python="3.12", pytorch="2.8", transformers="4.57"),
        ),
        worker=worker,
        timings_ms=EvaluationTimings(queue_wait=0, primary_scoring=0, full_scoring=None, total=0),
        errors=(),
    )
    work = DimensionWork(planned=1, completed=1)
    unieval = UnievalResult(
        version=UNIEVAL_VERSION, status="complete", execution_id=UNIEVAL_INSTANCE,
        request_id=REQUEST_ID, correlation_id=CORRELATION_ID,
        reference_summary_sha256=prepared.reference_summary_sha256,
        model=UnievalModelIdentity(
            reference="project/unieval", configured_revision="a" * 40, loaded_revision="a" * 40,
            tokenizer_revision="a" * 40, reference_code_revision="a" * 40,
            runtime_versions=UnievalRuntimeVersions(
                python="3.12", pytorch="2.8", transformers="4.57", tokenizers="0.22", nltk="3.9",
            ),
        ),
        worker=worker.model_copy(update={"pid": 1235}),
        effective_settings=EffectiveUnievalControls(
            consistency_source_mode="full_source_prompt", max_input_tokens=1000,
            source_window_tokens=100, source_overlap_tokens=0, max_source_windows=10,
            max_comparisons=100, source_budget_tokens=None,
        ),
        scores=UnievalScores(fluency=0.0, coherence=0.0, consistency=0.0, relevance=0.0),
        work=UnievalWork(
            fluency=work, coherence=work, consistency=work, relevance=work,
            summary_sentences=1, source_characters=len(inputs.source_text),
        ),
        timings_ms=UnievalTimings(queue_wait=0, scoring=0, total=0), errors=(),
    )
    hardware = Hardware(
        status="collected", cpu_model="Contract CPU", cpu_logical_processors=1,
        cpu_physical_cores=1, machine_memory_total_mib=1.0, unavailable={}, reason=None,
    )
    machine = MachineUsage.model_validate({
        "outcome": "success", "end_reason": "explicit_stop", "started_at": run.started_at,
        "finished_at": run.started_at + timedelta(milliseconds=1), "elapsed_ms": 1.0,
        "cpu": {"value": {"user": 1.0, "system": 0.0}, "reason": None},
        "machine_available_min_kb": 400, "unavailable": {},
        "samples": (
            {"phase": "opening", "memory_kb": {"total": 1024, "available": 512}, "unavailable": {}},
            {"phase": "closing", "memory_kb": {"total": 1024, "available": 400}, "unavailable": {}},
        ),
    })
    generated = build_evidence(
        None, hardware, machine, PhaseShutdown(host_stopped=True, llama_stopped=True), [],
        phase="generation", run=run,
        reference_summary_sha256=prepared.reference_summary_sha256,
        generation_sha256=receipt_hash,
    )
    evaluated = build_evidence(
        hhem, hardware, machine, PhaseShutdown(host_stopped=True), [],
        phase="evaluation", unieval=unieval,
        scorer_apis=(scorer_api_example("hhem", hhem), scorer_api_example("unieval", unieval)),
        evaluation_request_id=REQUEST_ID, evaluation_correlation_id=CORRELATION_ID,
        run=run, reference_summary_sha256=prepared.reference_summary_sha256,
        generation_sha256=receipt_hash,
    )
    return inputs, PipelineEvidence(
        version=EVIDENCE_VERSION, status="complete", prepared=prepared, generation=receipt,
        generation_phase=generated, evaluation_phase=evaluated, errors=(),
    )


def legacy_pipeline_example(*, current_outer: bool = False) -> PipelineResult:
    """Retain the old shared API shape, including its absent API process observations."""
    _, pipeline = in_memory_pipeline()
    payload = pipeline.model_dump(mode="json")
    payload["version"] = EVIDENCE_VERSION if current_outer else WORKFLOW_VERSION
    for key in ("generation_phase", "evaluation_phase"):
        phase = payload[key]
        apis = phase.pop("scorer_apis")
        phase["version"] = WORKFLOW_VERSION
        phase["shutdown"].update({
            "api_stopped": True if apis else None,
            "worker_exit_confirmed": True if apis else None,
            "unieval_worker_exit_confirmed": True if apis else None,
        })
        if apis:
            shared = apis[0]["health"]
            shared["enabled_routes"] = ["hhem", "unieval"]
            shared["unieval"] = apis[1]["health"]["unieval"]
            shared["unieval"]["service_instance_id"] = shared["service_instance_id"]
            phase["api_health"] = shared
            phase["servers"] = [apis[0]["outcome"]]
    return PipelineDocument.model_validate_json(json.dumps(payload)).root
