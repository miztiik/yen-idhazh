"""Verify the named manual workflow, bounded platform input and body-free report boundary."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import PipelineEvidence
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import encode_request, read_manual_inputs
from summary_eval_pipeline.settings import load_pipeline_settings

from .contract_examples import REPOSITORY, read_contract
from .service_cases import service_settings
from .test_host_profile_reader_parity import bridge_path, mapping, required_bun


def named_workflow() -> dict[str, object]:
    result = subprocess.run(
        [required_bun(), "run", "--no-install", str(bridge_path()), "workflow"],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "The existing Bun YAML reader failed: " + result.stderr
    return mapping(json.loads(result.stdout))


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for child in value.values() for text in strings(child)]
    if isinstance(value, list):
        return [text for child in value for text in strings(child)]
    return []


def test_named_workflow_is_manual_read_only_and_has_exactly_two_text_inputs() -> None:
    workflow = named_workflow()
    triggers = mapping(workflow["on"])
    assert set(triggers) == {"workflow_dispatch"}
    inputs = mapping(mapping(triggers["workflow_dispatch"])["inputs"])
    assert set(inputs) == {"source_text", "summary_text"}
    for spec in inputs.values():
        declaration = mapping(spec)
        assert declaration["type"] == "string" and declaration["required"] is True
        assert "default" not in declaration and "options" not in declaration
    assert mapping(workflow["permissions"]) == {"contents": "read"}
    jobs = mapping(workflow["jobs"])
    assert set(jobs) == {"evaluate"}
    job = mapping(jobs["evaluate"])
    assert job["runs-on"] == "ubuntu-latest"
    assert 0 < int(str(job["timeout-minutes"])) < 360
    assert "strategy" not in job
    steps = job["steps"]
    assert isinstance(steps, list)
    declared = [mapping(step) for step in steps]
    assert sum(str(step.get("uses", "")).startswith("actions/checkout@") for step in declared) == 1
    outside_form = {key: value for key, value in workflow.items() if key != "on"}
    text = "\n".join(strings(outside_form))
    assert not re.search(r"\$\{\{[^}]*\binputs\b", text)
    assert "source_text" not in text and "summary_text" not in text
    assert "summary-eval-hhem/run.py --root ../.." in text
    assert "summary-eval-hhem/report.py --root ../.." in text
    assert "--extra model --no-dev" in text
    for forbidden in (
        "git commit",
        "git push",
        "git add",
        "digest.yml",
        "idhazh pipeline",
        "summarize",
        "article_url",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "taskset",
        "ulimit",
        "GITHUB_EVENT_PATH:",
    ):
        assert forbidden not in text
    uploads = [
        step
        for step in declared
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(uploads) == 1 and uploads[0]["if"] == "always()"
    paths = str(mapping(uploads[0]["with"])["path"]).splitlines()
    output = load_pipeline_settings(REPOSITORY).output_directory
    assert paths == [
        output + "/evaluation.json",
        output + "/report.md",
    ]


def test_ordinary_service_ci_prepares_the_real_host_package_without_model_weights() -> None:
    # This is one named CI file, not discovery over the workflow directory.
    text = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = text.index("  hhem-evaluator:\n")
    end = text.index("\n  gates:\n", start)
    selected = text[start:end]
    assert "bun install --frozen-lockfile --cwd services/host-probes" in selected
    assert "uv sync --frozen --group dev" in selected
    assert "--extra model" not in selected
    assert "uv run --frozen pytest" in selected


def write_event(path: Path, inputs: dict[str, object]) -> None:
    path.write_text(json.dumps({"inputs": inputs}), encoding="utf-8")


def test_platform_input_preserves_text_and_enforces_the_exact_encoded_request_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    source = "  PrivateSourceCanary\n$(`never run this`)  "
    summary = "PrivateSummaryCanary ${{ inputs.not_a_command }}"
    write_event(event, {"source_text": source, "summary_text": summary})
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    selected = service_settings()
    manual = load_pipeline_settings(REPOSITORY)
    request = read_manual_inputs(selected, manual)
    assert request.source_text == source and request.summary_text == summary
    assert request.hhem_full is False
    size = len(encode_request(request))
    data = selected.model_dump(mode="json")
    data["listener"]["max_body_bytes"] = size
    exact = type(selected).model_validate_json(json.dumps(data))
    assert len(encode_request(read_manual_inputs(exact, manual))) == size
    data["listener"]["max_body_bytes"] = size - 1
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(type(selected).model_validate_json(json.dumps(data)), manual)
    assert failure.value.error.code == "INPUT_TOO_LARGE"
    # The caller read one platform-owned input and created no second text-bearing file.
    assert list(tmp_path.iterdir()) == [event]


@pytest.mark.parametrize(
    "inputs",
    [
        {"source_text": "Source.", "summary_text": "Summary.", "model": "PrivateValueCanary"},
        {"source_text": "Source."},
        {"source_text": "Source.", "summary_text": None},
        {"source_text": "Source.", "summary_text": True},
        {"source_text": " \n", "summary_text": "Summary."},
    ],
)
def test_invalid_platform_inputs_fail_without_echoing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inputs: dict[str, object],
) -> None:
    event = tmp_path / "event.json"
    write_event(event, inputs)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(service_settings(), load_pipeline_settings(REPOSITORY))
    assert failure.value.error.code == "INPUT_INVALID"
    assert "PrivateValueCanary" not in str(failure.value)
    assert "Source." not in failure.value.error.model_dump_json()


def test_event_envelope_overflow_fails_instead_of_truncating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    selected = service_settings()
    manual = load_pipeline_settings(REPOSITORY)
    allowance = selected.listener.max_body_bytes + manual.event_envelope_bytes
    with event.open("wb") as stream:
        stream.write(b" " * (allowance + 1))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(selected, manual)
    assert failure.value.error.code == "INPUT_TOO_LARGE"


def test_named_report_fixture_is_native_and_private_control_forbids_text() -> None:
    fixture = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "pipeline-evidence.json"
    report = PipelineEvidence.model_validate_json(fixture.read_bytes())
    assert report.version == "2026-11-02" and report.evaluation is None
    packet: dict[str, object] = {
        "version": "2026-11-02",
        "startup_id": "12345678-1234-4234-8234-123456789abc",
        "context": {"run_id": "fixture-run", "pipeline_name": "fixture", "task_name": "score"},
    }
    read_contract(StartupPacket, packet)
    with pytest.raises(ValidationError):
        read_contract(StartupPacket, {**packet, "source_text": "PrivateSourceCanary"})
    assert PipelineEvidence.model_json_schema()["version"] == "2026-11-02"
    with pytest.raises(ValidationError):
        read_contract(
            PipelineEvidence,
            {
                **report.model_dump(mode="json"),
                "summary_text": "PrivateSummaryCanary",
            },
        )
