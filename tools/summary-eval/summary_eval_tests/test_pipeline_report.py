"""Verify literal disclosures, retained failures and upward-rounded seconds."""

import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import (
    PipelineError,
    ServerOutcome,
    text_sha256,
)
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import ManualInputs
from summary_eval_pipeline.phase_contracts import PhaseEvidence, PhaseShutdown
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.report import describe_hhem, format_seconds, render_report
from summary_eval_pipeline.report_contracts import PipelineDocument, PipelineEvidence
from summary_eval_pipeline.scorer_evidence import EVIDENCE_VERSION
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import write_result
from summary_evaluator_cases.contract_examples import REPOSITORY, example_result
from summary_evaluator_cases.service_cases import service_settings

from summary_eval_tests.generation_cases import handoff_case, selected_root
from summary_eval_tests.scorer_evidence_cases import (
    in_memory_pipeline,
    legacy_pipeline_example,
    scorer_api_example,
)
from summary_eval_tests.test_host_profile_reader_parity import required_bun


@pytest.mark.parametrize(
    ("milliseconds", "expected"),
    [
        (None, "Not available"),
        (0.0, "0.000"),
        (0.001, "0.001"),
        (123.0, "0.123"),
        (123.0001, "0.124"),
        (1999.9999, "2.000"),
    ],
)
def test_durations_round_up_without_inventing_missing_work(
    milliseconds: float | None,
    expected: str,
) -> None:
    assert format_seconds(milliseconds) == expected


def test_report_discloses_generated_answer_as_literal_text_and_identifies_models() -> None:
    inputs, prepared, generation = handoff_case()
    answer = 'Summary </pre><img src=x onerror="alert(1)">'
    generation = generation.model_copy(
        update={
            "summary_text": answer,
            "summary_sha256": text_sha256(answer),
        }
    )
    evidence = PipelineEvidence(
        version=EVIDENCE_VERSION,
        status="failed",
        prepared=prepared,
        generation=generation,
        generation_phase=None,
        evaluation_phase=None,
        errors=(),
    )
    inputs = ManualInputs(
        source_text='Source <script>alert("source")</script>\n</pre></details>',
        reference_summary_text='Reference </pre><img src=x onerror="alert(2)">',
    )
    link = "https://example.test/repository/blob/selected/config/summary-evals/hhem-evaluator/settings.json"
    markdown = render_report(evidence, inputs, service_settings(), link)
    assert "<pre>" + html.escape(inputs.source_text) + "</pre>" in markdown
    assert "<pre>" + html.escape(answer) + "</pre>" in markdown
    assert inputs.source_text not in markdown and answer not in markdown
    assert "<script>" not in markdown and "<img" not in markdown
    assert "<pre>" + html.escape(inputs.reference_summary_text) + "</pre>" in markdown
    assert markdown.count("<details>") == markdown.count("</details>") == 3
    assert link in markdown and generation.selected.models_file in markdown
    assert generation.loaded is not None and generation.loaded.model_id in markdown
    assert "| UniEval | Not run | - | Not available |" in markdown
    rendered = subprocess.run(
        [
            required_bun(),
            "-e",
            "const html=Bun.markdown.html(await Bun.stdin.text()); "
            "console.log(JSON.stringify({tables:(html.match(/<table>/g)||[]).length,"
            "unsafe:html.includes('<script>')||html.includes('<img')}));",
        ],
        input=markdown,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert json.loads(rendered.stdout) == {"tables": 5, "unsafe": False}


def test_report_keeps_the_selected_declaration_when_generation_did_not_start() -> None:
    inputs, prepared, _ = handoff_case()
    evidence = PipelineEvidence(
        version=EVIDENCE_VERSION,
        status="failed",
        prepared=prepared,
        generation=None,
        generation_phase=None,
        evaluation_phase=None,
        errors=(),
    )
    markdown = render_report(evidence, inputs, service_settings(), "https://example.test/config")
    assert prepared.selected.models_file in markdown and prepared.selected.model_id in markdown
    assert "Not loaded" in markdown and "Not generated" in markdown


def test_missing_invalid_response_is_failed_not_reported_as_work_never_started() -> None:
    from summary_eval_tests.test_generation_handoff import generation_phase

    inputs, prepared, generation, generated = generation_phase()
    result = example_result()
    evaluated = build_evidence(
        result,
        None,
        None,
        PhaseShutdown(host_stopped=True),
        [WorkflowError("RESPONSE_INVALID", "evaluation", "unieval", 500).error],
        run=prepared.run,
        phase="evaluation",
        reference_summary_sha256=prepared.reference_summary_sha256,
        generation_sha256=text_sha256(generation.model_dump_json()),
        evaluation_request_id=result.request_id,
        evaluation_correlation_id=result.correlation_id,
        scorer_apis=(scorer_api_example("hhem", result),),
    )
    evidence = PipelineEvidence(
        version=EVIDENCE_VERSION,
        status="partial",
        prepared=prepared,
        generation=generation,
        generation_phase=generated,
        evaluation_phase=evaluated,
        errors=(),
    )
    report = render_report(evidence, inputs, service_settings(), "https://example.test/config")
    assert "| UniEval | Failed - no valid result | - | Not available |" in report
    assert "0.75 source support (0-1); 1 / 1 source windows complete" in report
    assert "evaluation / unieval / HTTP 500: RESPONSE_INVALID" in report


def test_hhem_work_counts_do_not_invent_a_score_for_an_uncompleted_window() -> None:
    from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
    from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult

    completed = example_result()
    assert completed.windows.primary is not None
    failed = EvaluationResult.model_validate_json(
        completed.model_copy(
            update={
                "status": "failed",
                "hhem": None,
                "windows": completed.windows.model_copy(
                    update={"primary": completed.windows.primary.model_copy(update={"scored": 0})}
                ),
                "errors": (ErrorDetail.from_code("MODEL_SCORING_FAILED", "worker"),),
            }
        ).model_dump_json()
    )
    assert describe_hhem(failed) == "Score unavailable; 0 / 1 source windows complete"
    assert describe_hhem(None) == "-"


def test_report_leads_with_work_and_preserves_service_http_and_owning_cleanup_phase() -> None:
    inputs, prepared, generation = handoff_case()
    receipt_hash = text_sha256(generation.model_dump_json())
    generation_cleanup = WorkflowError("SERVICE_STOP_FAILED", "cleanup", "host").error
    evaluation_cleanup = WorkflowError("SERVICE_STOP_FAILED", "cleanup", "hhem").error
    log_filename = "fastapi-server_2026_11_04_123456_1.log"
    host_log_filename = "hono-server_2026_11_04_123456_1.log"
    server = ServerOutcome(
        server_name="fastapi-server",
        startup="ready",
        startup_ms=123.0,
        shutdown="failed",
        exit_code=1,
        log_filename=log_filename,
        log_available=True,
        cleanup_error_code="SERVICE_STOP_FAILED",
    )
    generation_phase = build_evidence(
        None,
        None,
        None,
        PhaseShutdown(host_stopped=False, llama_stopped=True),
        [generation_cleanup],
        run=prepared.run,
        phase="generation",
        servers=(
            server.model_copy(
                update={
                    "server_name": "hono-server",
                    "log_filename": host_log_filename,
                }
            ),
        ),
        generation_sha256=receipt_hash,
        reference_summary_sha256=prepared.reference_summary_sha256,
    )
    evaluation_phase = build_evidence(
        example_result(),
        None,
        None,
        PhaseShutdown(host_stopped=True),
        [WorkflowError("EVALUATION_FAILED", "evaluation", "hhem", 502).error],
        run=prepared.run,
        phase="evaluation",
        scorer_apis=(
            scorer_api_example(
                "hhem", example_result(), stopped=False, errors=(evaluation_cleanup,),
                log_file=log_filename,
            ).model_copy(update={"outcome": server}),
        ),
        generation_sha256=receipt_hash,
        reference_summary_sha256=prepared.reference_summary_sha256,
        evaluation_request_id=example_result().request_id,
        evaluation_correlation_id=example_result().correlation_id,
    )
    evidence = PipelineEvidence(
        version=EVIDENCE_VERSION,
        status="partial",
        prepared=prepared,
        generation=generation,
        generation_phase=generation_phase,
        evaluation_phase=evaluation_phase,
        errors=(),
    )
    markdown = render_report(evidence, inputs, service_settings(), "https://example.test/config")
    assert re.findall(r"^## (.+)$", markdown, re.MULTILINE) == [
        "Actual work",
        "Errors",
        "UniEval scores",
        "Model configuration",
        "Hardware",
        "Owned servers",
        "Texts",
    ]
    assert "evaluation / hhem / HTTP 502: EVALUATION_FAILED" in markdown
    assert "generation / cleanup / host: SERVICE_STOP_FAILED" in markdown
    assert "evaluation / hhem / cleanup: SERVICE_STOP_FAILED" in markdown
    assert "generation / cleanup / hono-server: SERVICE_STOP_FAILED" in markdown
    assert "evaluation / hhem / cleanup: SERVICE_STOP_FAILED" in markdown
    assert "HTTP None" not in markdown
    assert "Artifacts -> summary-eval-tests-server-logs" in markdown
    assert log_filename in markdown
    assert host_log_filename in markdown
    assert "| generation | fastapi-server |" not in markdown
    assert "| generation | HHEM worker exit confirmed |" not in markdown
    assert "| generation | UniEval worker exit confirmed |" not in markdown
    assert "| evaluation | hhem API | PID 2100;" in markdown
    assert "Model worker exit" in markdown
    assert re.findall(r"\*\*Table ([A-Z])\*\*", markdown) == ["A", "B", "C", "D", "E"]
    row_ids = re.findall(r"^\| ([A-Z]\d+) \|", markdown, re.MULTILINE)
    assert len(row_ids) == len(set(row_ids))
    assert row_ids[0] == "A1" and "B1" in row_ids and "C1" in row_ids and "D1" in row_ids


def test_safe_machine_cause_is_retained_in_native_evidence_and_visible_in_the_report() -> None:
    fixture = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "pipeline-evidence.json"
    evidence = PipelineDocument.model_validate_json(fixture.read_bytes()).root
    failure = WorkflowError(
        "STARTUP_FAILED", "startup", "host", source_code="MACHINE_API_STARTUP_INVALID"
    ).error
    evidence = evidence.model_copy(update={"errors": (failure,)})
    markdown = render_report(
        evidence,
        ManualInputs(
            source_text="Project-authored source.",
            reference_summary_text="Independent reference.",
        ),
        service_settings(),
        "https://example.test/config",
    )
    assert "STARTUP_FAILED (cause MACHINE_API_STARTUP_INVALID)" in markdown
    assert PipelineError.model_validate_json(failure.model_dump_json()) == failure


@pytest.mark.parametrize(
    "code",
    [
        "PrivateRawFailureCanary",
        "UNSAFE\nCODE",
        "CODE_" + "X" * 128,
    ],
)
def test_machine_cause_codes_refuse_raw_text_and_unbounded_values(code: str) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WorkflowError("HOST_FAILED", "host", "host", source_code=code)


@pytest.mark.parametrize("oversized", [False, True])
def test_report_creator_retains_full_artifact_and_never_promotes_failed_work(
    tmp_path: Path,
    oversized: bool,
) -> None:
    selected_root(tmp_path)
    inputs, prepared, generation = handoff_case()
    source = "PrivateSourceCanary " + ("<" * 300000 if oversized else "<script>data</script>")
    answer = "PrivateSummaryCanary ${{ inputs.not_a_command }}"
    prepared = prepared.model_copy(update={"source_sha256": text_sha256(source)})
    generation = generation.model_copy(
        update={
            "source_sha256": text_sha256(source),
            "summary_text": answer,
            "summary_sha256": text_sha256(answer),
        }
    )
    directory = tmp_path / load_pipeline_settings(REPOSITORY).output_directory
    write_result(directory / "run.json", prepared)
    write_result(directory / "generation.json", generation)
    for phase, name in (("generation", "generation-phase.json"), ("evaluation", "evaluation.json")):
        phase_evidence = build_evidence(
            None,
            None,
            None,
            PhaseShutdown(
                host_stopped=True,
                llama_stopped=True if phase == "generation" else None,
            ),
            [WorkflowError("HOST_FAILED", "host", "host").error],
            run=prepared.run,
            phase="generation" if phase == "generation" else "evaluation",
            generation_sha256=text_sha256(generation.model_dump_json()),
            reference_summary_sha256=prepared.reference_summary_sha256,
        )
        write_result(directory / name, phase_evidence)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "inputs": {
                    "source_text": source,
                    "models_file": "",
                    "reference_summary_text": inputs.reference_summary_text,
                }
            }
        ),
        encoding="utf-8",
    )
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / "tools" / "summary-eval" / "report.py"),
            "--root",
            str(tmp_path),
        ],
        env={
            **os.environ,
            "GITHUB_EVENT_PATH": str(event),
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_SERVER_URL": "https://example.test",
            "GITHUB_REPOSITORY": "fixture/repository",
            "GITHUB_SHA": prepared.run.git_sha,
            "GITHUB_RUN_ID": prepared.run.run_id,
            "GITHUB_RUN_ATTEMPT": str(prepared.run.attempt),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    if oversized:
        assert not summary.exists() and "summary_size_exceeded" in result.stdout
        assert (directory / "report.md").read_bytes().count(b"&lt;") == 300000
    else:
        assert summary.read_bytes() == (directory / "report.md").read_bytes()
        assert "failed" in result.stdout
    assert b"PrivateSourceCanary" in (directory / "report.md").read_bytes()
    assert b"PrivateSummaryCanary" in (directory / "report.md").read_bytes()
    assert "PrivateSourceCanary" not in result.stdout + result.stderr
    assert "PrivateSummaryCanary" not in result.stdout + result.stderr
    retained = PipelineEvidence.model_validate_json((directory / "results.json").read_bytes())
    assert retained.generation is not None and retained.generation.summary_text == answer
    assert retained.status == "failed"


@pytest.mark.parametrize("current_outer", [False, True])
def test_preserved_parent_report_renders_one_shared_api_without_independent_process_rows(
    current_outer: bool,
) -> None:
    from summary_eval_pipeline.contracts import WORKFLOW_VERSION
    from summary_eval_pipeline.contracts import PhaseEvidence as LegacyPhaseEvidence

    evidence = legacy_pipeline_example(current_outer=current_outer)
    inputs, _ = in_memory_pipeline()
    markdown = render_report(evidence, inputs, service_settings(), "https://example.test/config")
    assert markdown.count("| Shared scorer API (legacy 2026-11-05) |") == 1
    assert "| hhem API |" not in markdown and "| unieval API |" not in markdown
    assert "PID 2100" not in markdown and "PID 2101" not in markdown
    assert "worker exit PIDs/statuses not recorded" in markdown
    assert evidence.generation_phase is not None and evidence.evaluation_phase is not None
    assert isinstance(evidence.evaluation_phase, LegacyPhaseEvidence)
    assert evidence.evaluation_phase.api_health is not None
    assert "coverage" not in evidence.evaluation_phase.api_health.model_dump()
    assert (
        evidence.generation_phase.version == evidence.evaluation_phase.version == WORKFLOW_VERSION
    )
    reread = PipelineDocument.model_validate_json(evidence.model_dump_json()).root
    assert reread.generation_phase is not None and reread.evaluation_phase is not None
    assert reread.generation_phase.version == reread.evaluation_phase.version == WORKFLOW_VERSION


def test_previous_disabled_health_keeps_independent_api_observations_unchanged() -> None:
    from summary_eval_pipeline.scorer_evidence import ScorerApiEvidence

    _, complete = in_memory_pipeline()
    assert isinstance(complete.evaluation_phase, PhaseEvidence)
    original = complete.evaluation_phase.scorer_apis[0]
    payload = original.model_dump(mode="json")
    payload["health"]["coverage"] = {"status": "disabled", "worker": None, "model": None}
    reread = ScorerApiEvidence.model_validate_json(json.dumps(payload))
    assert reread == original
    assert reread.process == original.process
    assert reread.service_instance_id == original.service_instance_id
    assert reread.worker_exit == original.worker_exit
    assert reread.health is not None and "coverage" not in reread.health.model_dump()
    payload["health"]["coverage"]["status"] = "ready"
    with pytest.raises(ValidationError):
        ScorerApiEvidence.model_validate_json(json.dumps(payload))


def test_independent_rows_show_actual_identity_exit_and_scorer_scoped_startup_failure() -> None:
    inputs, complete = in_memory_pipeline()
    assert isinstance(complete.evaluation_phase, PhaseEvidence)
    original = complete.evaluation_phase
    hhem = original.scorer_apis[0].model_copy(
        update={
            "outcome": original.scorer_apis[0].outcome.model_copy(
                update={"log_filename": "fastapi-server-hhem.log", "log_available": True}
            )
        }
    )
    failed = scorer_api_example(
        "unieval", errors=(WorkflowError("HEALTH_FAILED", "health", "unieval", 503).error,),
    )
    phase = PhaseEvidence.model_validate_json(
        original.model_copy(
            update={"status": "partial", "unieval": None, "scorer_apis": (hhem, failed)}
        ).model_dump_json()
    )
    evidence = complete.model_copy(update={"status": "partial", "evaluation_phase": phase})
    markdown = render_report(evidence, inputs, service_settings(), "https://example.test/config")
    assert markdown.count("| hhem API |") == markdown.count("| unieval API |") == 1
    assert "| hhem API | PID 2100; start ticks 1000 |" in markdown
    assert "PID 1234; exit status 0; confirmed True" in markdown
    assert "| unieval API | Not recorded | Not recorded | failed |" in markdown
    assert "fastapi-server-hhem.log" in markdown
    assert "evaluation / unieval / health / HTTP 503: HEALTH_FAILED" in markdown
    assert "evaluation / health / api:" not in markdown
    assert "| UniEval | Failed - no valid result |" in markdown
    assert "0.0 source support (0-1)" in markdown
