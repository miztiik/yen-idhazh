"""Verify literal disclosures, truthful missing readings and upward-rounded seconds."""

import html
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from summary_eval_pipeline.contracts import PipelineEvidence
from summary_eval_pipeline.report import format_seconds, render_report
from summary_eval_pipeline.settings import load_pipeline_settings

from hhem_evaluator.contracts.evaluate_request import EvaluateRequest

from .contract_examples import REPOSITORY
from .service_cases import service_settings


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


def test_one_markdown_report_discloses_only_escaped_literal_inputs() -> None:
    fixture = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "pipeline-evidence.json"
    evidence = PipelineEvidence.model_validate_json(fixture.read_bytes())
    request = EvaluateRequest(
        source_text='Source <script>alert("source")</script>\n</pre></details>',
        summary_text='Summary </pre><img src=x onerror="alert(1)">',
        hhem_full=False,
    )
    link = "https://example.test/repository/blob/selected/config/hhem-evaluator/settings.json"
    markdown = render_report(evidence, request, service_settings(), link)
    assert "<pre>" + html.escape(request.source_text) + "</pre>" in markdown
    assert "<pre>" + html.escape(request.summary_text) + "</pre>" in markdown
    assert request.source_text not in markdown and request.summary_text not in markdown
    assert "<script>" not in markdown and "<img" not in markdown
    assert markdown.count("<details>") == markdown.count("</details>") == 2
    assert link in markdown
    assert "sha256" not in markdown.lower()
    assert "Not run - future task | - | -" in markdown
    assert "Unavailable - Not run" in markdown
    assert request.source_text not in evidence.model_dump_json()


@pytest.mark.parametrize("oversized", [False, True])
def test_report_creator_publishes_the_same_file_or_fails_without_truncating(
    tmp_path: Path,
    oversized: bool,
) -> None:
    config = tmp_path / "config"
    (config / "hhem-evaluator").mkdir(parents=True)
    for name in ("summary-eval-hhem.json", "hhem-evaluator/settings.json"):
        (config / name).write_bytes((REPOSITORY / "config" / name).read_bytes())
    directory = tmp_path / load_pipeline_settings(REPOSITORY).output_directory
    directory.mkdir(parents=True)
    (directory / "evaluation.json").write_bytes(
        (
            REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "pipeline-evidence.json"
        ).read_bytes()
    )
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "inputs": {
                    "source_text": (
                        "PrivateSourceCanary " + "<" * 300000
                        if oversized
                        else "PrivateSourceCanary <script>not a command</script>"
                    ),
                    "summary_text": "PrivateSummaryCanary ${{ inputs.not_a_command }}",
                }
            }
        ),
        encoding="utf-8",
    )
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY / ".github" / "scripts" / "summary-eval-hhem" / "report.py"),
            "--root",
            str(tmp_path),
        ],
        env={
            **os.environ,
            "GITHUB_EVENT_PATH": str(event),
            "GITHUB_STEP_SUMMARY": str(summary),
            "GITHUB_SERVER_URL": "https://example.test",
            "GITHUB_REPOSITORY": "fixture/repository",
            "GITHUB_SHA": "a" * 40,
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if oversized:
        assert result.returncode == 1
        assert not summary.exists()
        assert "summary_size_exceeded" in result.stdout
        assert (directory / "report.md").read_bytes().count(b"&lt;") == 300000
    else:
        assert result.returncode == 0, result.stderr
        assert summary.read_bytes() == (directory / "report.md").read_bytes()
    assert b"PrivateSourceCanary" in (directory / "report.md").read_bytes()
    assert b"PrivateSummaryCanary" in (directory / "report.md").read_bytes()
    assert "PrivateSourceCanary" not in result.stdout + result.stderr
    assert "PrivateSummaryCanary" not in result.stdout + result.stderr
    assert b"PrivateSourceCanary" not in (directory / "evaluation.json").read_bytes()
