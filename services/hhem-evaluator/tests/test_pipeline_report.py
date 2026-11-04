"""Verify literal disclosures, retained failures and upward-rounded seconds."""

import html
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from summary_eval_pipeline.contracts import (
    WORKFLOW_VERSION,
    PipelineEvidence,
    ServiceShutdown,
    text_sha256,
)
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import ManualInputs
from summary_eval_pipeline.phase_result import build_evidence
from summary_eval_pipeline.report import format_seconds, render_report
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import write_result

from .contract_examples import REPOSITORY
from .generation_cases import handoff_case, selected_root
from .service_cases import service_settings
from .test_host_profile_reader_parity import required_bun


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
        version=WORKFLOW_VERSION,
        status="failed",
        prepared=prepared,
        generation=generation,
        generation_phase=None,
        evaluation_phase=None,
        unieval="not_run",
        errors=(),
    )
    inputs = ManualInputs(source_text='Source <script>alert("source")</script>\n</pre></details>')
    link = "https://example.test/repository/blob/selected/config/hhem-evaluator/settings.json"
    markdown = render_report(evidence, inputs, service_settings(), link)
    assert "<pre>" + html.escape(inputs.source_text) + "</pre>" in markdown
    assert "<pre>" + html.escape(answer) + "</pre>" in markdown
    assert inputs.source_text not in markdown and answer not in markdown
    assert "<script>" not in markdown and "<img" not in markdown
    assert markdown.count("<details>") == markdown.count("</details>") == 2
    assert link in markdown and generation.selected.models_file in markdown
    assert generation.loaded is not None and generation.loaded.model_id in markdown
    assert "Not run - separate workflow integration | - | -" in markdown
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
    assert json.loads(rendered.stdout) == {"tables": 4, "unsafe": False}


def test_report_keeps_the_selected_declaration_when_generation_did_not_start() -> None:
    inputs, prepared, _ = handoff_case()
    evidence = PipelineEvidence(
        version=WORKFLOW_VERSION,
        status="failed",
        prepared=prepared,
        generation=None,
        generation_phase=None,
        evaluation_phase=None,
        unieval="not_run",
        errors=(),
    )
    markdown = render_report(evidence, inputs, service_settings(), "https://example.test/config")
    assert prepared.selected.models_file in markdown and prepared.selected.model_id in markdown
    assert "Not loaded" in markdown and "Not generated" in markdown


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
            ServiceShutdown(
                api_stopped=True,
                host_stopped=True,
                worker_exit_confirmed=None,
                llama_stopped=True if phase == "generation" else None,
            ),
            [WorkflowError("HOST_FAILED", "host", "host").error],
            run=prepared.run,
            phase="generation" if phase == "generation" else "evaluation",
            generation_sha256=text_sha256(generation.model_dump_json()),
        )
        write_result(directory / name, phase_evidence)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"inputs": {"source_text": source, "models_file": ""}}), encoding="utf-8"
    )
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / ".github" / "scripts" / "summary-eval-tests" / "report.py"),
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
