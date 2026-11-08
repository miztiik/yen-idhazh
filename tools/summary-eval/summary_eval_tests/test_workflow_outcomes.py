"""Do independent evidence and preserved shared evidence require their actual observations?"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import (
    text_sha256,
)
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.phase_contracts import PhaseDocument, PhaseEvidence, PhaseShutdown
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.report import render_report
from summary_eval_pipeline.report_contracts import (
    REPORT_VERSION,
    PipelineDocument,
    PipelineEvidence,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_result import DimensionWork
from summary_evaluator_cases.contract_examples import (
    example_result,
    example_unieval_result,
)
from summary_evaluator_cases.service_cases import service_settings

from summary_eval_tests.generation_cases import handoff_case
from summary_eval_tests.pipeline_cases import NativeHostPipe, prepare_proc
from summary_eval_tests.scorer_evidence_cases import in_memory_pipeline, scorer_api_example


def test_native_zero_scores_complete_only_with_both_results_measurement_and_joined_workers(
    tmp_path: Path,
) -> None:
    inputs, prepared, receipt = handoff_case()
    assert prepared.reference_summary_sha256 is not None
    hhem = example_result()
    unieval = example_unieval_result(prepared.reference_summary_sha256)
    apis = (scorer_api_example("hhem", hhem), scorer_api_example("unieval", unieval))
    prepare_proc(tmp_path)
    host = NativeHostPipe(tmp_path)
    try:
        prepare_proc(tmp_path, closing=True)
        clean, machine = host.close()
        shutdown = PhaseShutdown(host_stopped=clean)
        phase = build_evidence(
            hhem,
            host.hardware,
            machine,
            shutdown,
            [],
            run=prepared.run,
            phase="evaluation",
            reference_summary_sha256=prepared.reference_summary_sha256,
            evaluate_relevance=prepared.evaluate_relevance,
            generation_sha256=text_sha256(receipt.model_dump_json()),
            evaluation_request_id=hhem.request_id,
            evaluation_correlation_id=hhem.correlation_id,
            unieval=unieval,
            scorer_apis=apis,
        )
        generated = build_evidence(
            None,
            host.hardware,
            machine,
            shutdown.model_copy(update={"llama_stopped": True}),
            [],
            run=prepared.run,
            phase="generation",
            reference_summary_sha256=prepared.reference_summary_sha256,
            evaluate_relevance=prepared.evaluate_relevance,
            generation_sha256=text_sha256(receipt.model_dump_json()),
        )
        combined = PipelineEvidence(
            version=REPORT_VERSION,
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
        assert "all_source_windows" in report and "4 of 4 applicable dimensions complete" in report
        assert "not source coverage" in report and "cannot join evidence" in report
        for change in (
            {"unieval": None},
            {"shutdown": shutdown.model_copy(update={"host_stopped": False})},
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


def test_current_in_memory_evidence_roundtrips_without_changing_native_families() -> None:
    from summary_eval_pipeline.run_contracts import RUN_VERSION

    _, pipeline = in_memory_pipeline()
    current = PipelineDocument.model_validate_json(pipeline.model_dump_json()).root
    assert isinstance(current, PipelineEvidence) and current.status == "complete"
    assert current.generation is not None and current.generation.version == RUN_VERSION
    phase = current.evaluation_phase
    assert isinstance(phase, PhaseEvidence)
    assert phase.evaluation is not None and phase.evaluation.hhem == 0.0
    assert phase.unieval is not None
    assert all(value == 0.0 for value in phase.unieval.scores.model_dump().values())
    assert phase.errors == ()
    assert phase.servers == ()
    assert [api.scorer for api in phase.scorer_apis] == ["hhem", "unieval"]
    assert len({api.process.pid for api in phase.scorer_apis if api.process is not None}) == 2


@pytest.mark.parametrize("supplied", [False, True])
def test_three_applicable_scores_complete_the_bound_report_and_disclose_an_unused_reference(
    supplied: bool,
) -> None:
    inputs, evidence = in_memory_pipeline()
    payload = evidence.model_dump(mode="json")
    assert evidence.generation is not None
    for key in ("prepared", "generation", "generation_phase", "evaluation_phase"):
        payload[key]["evaluate_relevance"] = False
        if not supplied:
            payload[key]["reference_summary_sha256"] = None
    from summary_eval_pipeline.run_contracts import GenerationReceipt

    receipt = GenerationReceipt.model_validate_json(json.dumps(payload["generation"]))
    for key in ("generation_phase", "evaluation_phase"):
        payload[key]["generation_sha256"] = text_sha256(receipt.model_dump_json())
    unieval = payload["evaluation_phase"]["unieval"]
    unieval["effective_settings"]["evaluate_relevance"] = False
    unieval["relevance_skip_reason"] = "disabled"
    unieval["scores"]["relevance"] = None
    unieval["work"]["relevance"] = {"planned": None, "completed": 0}
    if not supplied:
        unieval["reference_summary_sha256"] = None
    current = PipelineDocument.model_validate_json(json.dumps(payload)).root
    assert isinstance(current, PipelineEvidence) and current.status == "complete"
    assert current.evaluation_phase is not None and current.evaluation_phase.unieval is not None
    assert current.evaluation_phase.unieval.status == "complete"
    inputs = inputs.model_copy(update={
        "evaluate_relevance": False,
        **({} if supplied else {"reference_summary_text": None}),
    })
    report = render_report(current, inputs, service_settings(), "https://example.test/config")
    assert "3 of 3 applicable dimensions complete" in report
    assert "Skipped - disabled" in report
    assert "Skipped relevance is not a failure or zero" in report
    assert ("Supplied but unused" if supplied else "Not supplied") in report
    broken = current.model_dump(mode="json")
    broken["generation"]["evaluate_relevance"] = True
    with pytest.raises(ValidationError):
        PipelineDocument.model_validate_json(json.dumps(broken))


@pytest.mark.parametrize(
    "fault",
    [
        "api_pid", "application", "worker_pid", "api_worker", "routes",
        "missing_process", "listener", "exit", "aggregate", "unscoped", "version",
    ],
)
def test_current_complete_evidence_refuses_shared_crossed_or_missing_observations(
    fault: str,
) -> None:
    _, pipeline = in_memory_pipeline()
    assert pipeline.evaluation_phase is not None
    payload = pipeline.evaluation_phase.model_dump(mode="json")
    hhem, unieval = payload["scorer_apis"]
    if fault == "api_pid":
        unieval["process"] = hhem["process"]
    elif fault == "application":
        unieval["service_instance_id"] = hhem["service_instance_id"]
        unieval["health"]["service_instance_id"] = hhem["service_instance_id"]
        unieval["health"]["unieval"]["service_instance_id"] = hhem["service_instance_id"]
    elif fault == "worker_pid":
        unieval["health"]["unieval"]["worker"]["pid"] = hhem["health"]["hhem"]["worker"]["pid"]
        payload["unieval"]["worker"]["pid"] = unieval["health"]["unieval"]["worker"]["pid"]
    elif fault == "api_worker":
        hhem["process"]["pid"] = hhem["health"]["hhem"]["worker"]["pid"]
    elif fault == "routes":
        hhem["health"]["enabled_routes"] = ["hhem", "unieval"]
    elif fault == "missing_process":
        hhem["process"] = None
    elif fault == "listener":
        unieval["listener"] = hhem["listener"]
    elif fault == "exit":
        unieval["worker_exit"]["confirmed"] = False
    elif fault == "aggregate":
        payload["servers"] = [hhem["outcome"]]
    elif fault == "unscoped":
        payload["errors"] = [WorkflowError("HEALTH_FAILED", "health", "api").error.model_dump()]
        payload["status"] = "partial"
    else:
        payload["version"] = "2026-11-06"
    with pytest.raises(ValidationError):
        PhaseDocument.model_validate_json(json.dumps(payload))


def test_failed_startup_record_keeps_the_ready_sibling_and_its_computed_zero() -> None:
    _, pipeline = in_memory_pipeline()
    assert isinstance(pipeline.evaluation_phase, PhaseEvidence)
    original = pipeline.evaluation_phase
    failed = scorer_api_example(
        "unieval", errors=(WorkflowError("STARTUP_FAILED", "startup", "unieval").error,),
    )
    partial = PhaseDocument.model_validate_json(
        original.model_copy(
            update={
                "status": "partial", "unieval": None,
                "scorer_apis": (original.scorer_apis[0], failed),
            }
        ).model_dump_json()
    ).root
    assert isinstance(partial, PhaseEvidence) and partial.evaluation == original.evaluation
    assert partial.evaluation is not None and partial.evaluation.hhem == 0.0
    assert partial.scorer_apis[0] == original.scorer_apis[0]
    assert partial.scorer_apis[1].process is None
    assert partial.scorer_apis[1].health is None
    assert partial.errors == ()
    assert partial.servers == ()


def test_current_worker_exit_must_describe_the_worker_that_completed_the_score() -> None:
    _, pipeline = in_memory_pipeline()
    assert isinstance(pipeline.evaluation_phase, PhaseEvidence)
    payload = pipeline.evaluation_phase.model_dump(mode="json")
    payload["scorer_apis"][1]["worker_exit"]["pid"] += 1
    with pytest.raises(ValidationError):
        PhaseDocument.model_validate_json(json.dumps(payload))
    payload["status"] = "partial"
    assert PhaseDocument.model_validate_json(json.dumps(payload)).root.status == "partial"


def test_current_report_checks_the_original_receipt_hash_supplied_by_its_bounded_reader() -> None:
    _, pipeline = in_memory_pipeline()
    assert pipeline.generation_phase is not None
    encoded = pipeline.model_dump_json()
    saved_hash = pipeline.generation_phase.generation_sha256
    restored = PipelineDocument.model_validate_json(
        encoded, context={"generation_sha256": saved_hash}
    ).root
    assert restored.status == "complete"
    with pytest.raises(ValidationError):
        PipelineDocument.model_validate_json(
            encoded, context={"generation_sha256": "f" * 64}
        )


def test_unknown_report_versions_are_refused_without_reading_a_different_variant() -> None:
    _, pipeline = in_memory_pipeline()
    payload = pipeline.model_dump(mode="json")
    for version in ("2026-11-06", "2026-11-08"):
        with pytest.raises(ValidationError):
            PipelineDocument.model_validate_json(json.dumps({**payload, "version": version}))
