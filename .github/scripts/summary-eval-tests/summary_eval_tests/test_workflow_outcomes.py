"""Does current-only evidence require both complete native results and independent cleanup?"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import (
    WORKFLOW_VERSION,
    PhaseEvidence,
    PipelineEvidence,
    ServiceShutdown,
    text_sha256,
)
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.report import render_report
from summary_evaluator.hhem.contracts.base import SCHEMA_VERSION
from summary_evaluator.hhem.contracts.service_health import ServiceHealth
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.shared.contracts.server_contract import SERVER_SCHEMA_VERSION
from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_result import DimensionWork, UnievalHealth
from summary_evaluator_cases.contract_examples import (
    EXECUTION_ID,
    example_result,
    example_unieval_result,
)
from summary_evaluator_cases.service_cases import service_settings

from summary_eval_tests.generation_cases import handoff_case
from summary_eval_tests.pipeline_cases import NativeHostPipe, prepare_proc


def test_native_zero_scores_complete_only_with_both_results_measurement_and_joined_workers(
    tmp_path: Path,
) -> None:
    inputs, prepared, receipt = handoff_case()
    hhem = example_result()
    unieval = example_unieval_result(prepared.reference_summary_sha256)
    health = ApiHealth(
        version=SERVER_SCHEMA_VERSION,
        service_instance_id=EXECUTION_ID,
        enabled_routes=("hhem", "unieval"),
        status="ready",
        hhem=ServiceHealth(
            version=SCHEMA_VERSION,
            service_instance_id=EXECUTION_ID,
            status="ready",
            worker=hhem.worker,
            model=hhem.model,
            queue_depth=0,
            queue_capacity=1,
            failure_code=None,
        ),
        unieval=UnievalHealth(
            version=UNIEVAL_VERSION,
            service_instance_id=EXECUTION_ID,
            status="ready",
            worker=unieval.worker,
            model=unieval.model,
            queue_depth=0,
            queue_capacity=1,
            failure_code=None,
        ),
        log_file=None,
        log_available=False,
    )
    prepare_proc(tmp_path)
    host = NativeHostPipe(tmp_path)
    try:
        prepare_proc(tmp_path, closing=True)
        clean, machine = host.close()
        shutdown = ServiceShutdown(
            api_stopped=True,
            host_stopped=clean,
            worker_exit_confirmed=True,
            unieval_worker_exit_confirmed=True,
        )
        phase = build_evidence(
            hhem,
            host.hardware,
            machine,
            shutdown,
            [],
            run=prepared.run,
            phase="evaluation",
            reference_summary_sha256=prepared.reference_summary_sha256,
            generation_sha256=text_sha256(receipt.model_dump_json()),
            evaluation_request_id=hhem.request_id,
            evaluation_correlation_id=hhem.correlation_id,
            unieval=unieval,
            api_health=health,
        )
        generated = build_evidence(
            None,
            host.hardware,
            machine,
            shutdown.model_copy(
                update={
                    "api_stopped": None,
                    "llama_stopped": True,
                    "worker_exit_confirmed": None,
                    "unieval_worker_exit_confirmed": None,
                }
            ),
            [],
            run=prepared.run,
            phase="generation",
            reference_summary_sha256=prepared.reference_summary_sha256,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        combined = PipelineEvidence(
            version=WORKFLOW_VERSION,
            status="complete",
            prepared=prepared,
            generation=receipt,
            generation_phase=generated,
            evaluation_phase=phase,
            errors=(),
        )
        assert phase.status == generated.status == combined.status == "complete"
        assert phase.unieval is not None
        assert all(value == 0.0 for value in phase.unieval.scores.model_dump().values())
        report = render_report(combined, inputs, service_settings(), "https://example.test/config")
        for dimension in ("fluency", "coherence", "consistency", "relevance"):
            assert f"| {dimension} | 0.0 |" in report
        assert "all_source_windows" in report and "4 of 4 dimensions complete" in report
        assert "not source coverage" in report and "cannot join evidence" in report
        for change in (
            {"unieval": None},
            {"shutdown": shutdown.model_copy(update={"unieval_worker_exit_confirmed": False})},
            {"shutdown": shutdown.model_copy(update={"worker_exit_confirmed": False})},
            {"hardware": None},
            {"machine": None},
            {
                "unieval": unieval.model_copy(
                    update={
                        "status": "partial",
                        "scores": unieval.scores.model_copy(update={"relevance": None}),
                        "work": unieval.work.model_copy(update={"relevance": DimensionWork()}),
                        "errors": (
                            UnievalError.from_code("RELEVANCE_INPUT_TOO_LONG", "relevance"),
                        ),
                    }
                )
            },
        ):
            payload = phase.model_copy(update={**change, "status": "partial"}).model_dump_json()
            partial = PhaseEvidence.model_validate_json(payload)
            assert partial.status == "partial"
            with pytest.raises(ValidationError):
                PhaseEvidence.model_validate_json(
                    partial.model_copy(update={"status": "complete"}).model_dump_json()
                )
        for field in ("evaluation_request_id", "reference_summary_sha256", "generation_sha256"):
            value = json.loads(phase.model_dump_json())
            value[field] = None
            with pytest.raises(ValidationError):
                PhaseEvidence.model_validate_json(json.dumps(value))
    finally:
        host.close()
