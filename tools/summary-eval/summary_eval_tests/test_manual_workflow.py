"""Verify the named form, visible phases and bounded platform-data boundary."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, PipelineEvidence
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import read_manual_inputs
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator_cases.contract_examples import REPOSITORY, read_contract

from summary_eval_tests.test_host_profile_reader_parity import (
    bridge_path,
    mapping,
    required_bun,
)


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


def test_named_workflow_selects_one_declaration_with_the_current_pointer_default() -> None:
    workflow = named_workflow()
    triggers = mapping(workflow["on"])
    assert set(triggers) == {"workflow_dispatch"}
    inputs = mapping(mapping(triggers["workflow_dispatch"])["inputs"])
    assert set(inputs) == {"source_text", "models_file", "reference_summary_text"}
    source, model = mapping(inputs["source_text"]), mapping(inputs["models_file"])
    assert source["type"] == "string" and source["required"] is True
    reference = mapping(inputs["reference_summary_text"])
    assert reference["type"] == "string" and reference["required"] is True
    assert model["type"] == "string" and model["required"] is False and "options" not in model
    pointer = json.loads((REPOSITORY / "config" / "idhazh.json").read_bytes())["models_file"]
    assert model["default"] == pointer
    assert mapping(workflow["permissions"]) == {"contents": "read"}
    jobs = mapping(workflow["jobs"])
    assert set(jobs) == {"evaluate"}
    job = mapping(jobs["evaluate"])
    assert job["runs-on"] == "ubuntu-latest" and "strategy" not in job
    assert 0 < int(str(job["timeout-minutes"])) < 360
    steps = job["steps"]
    assert isinstance(steps, list)
    declared = [mapping(step) for step in steps]
    text = "\n".join(strings({key: value for key, value in workflow.items() if key != "on"}))
    assert not re.search(r"\$\{\{[^}]*\binputs\b", text)
    phases = [
        str(step["run"]).rsplit(" ", 1)[-1]
        for step in declared
        if "tools/summary-eval/run.py" in str(step.get("run", ""))
    ]
    assert phases == ["prepare", "generate", "evaluate"]
    assert "--frozen --extra model --no-dev" in text
    assert "tools/summary-eval/report.py --root ../.." in text
    assert "bun install --frozen-lockfile --cwd services/serve-pipeline-apis" in text
    for forbidden in (
        "bun install --frozen-lockfile --cwd services/feed-ingest-plan",
        "bun install --frozen-lockfile --cwd packages/data-delivery",
        "git commit",
        "git push",
        "git add",
        "digest.yml",
        "idhazh pipeline",
        "article_url",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "taskset",
        "ulimit",
        "GITHUB_EVENT_PATH:",
        "summary-eval-hhem/",
    ):
        assert forbidden not in text
    uploads = [
        step
        for step in declared
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(uploads) == 2
    assert uploads[0]["if"] == "${{ always() && steps.prepare.outputs.output_directory != '' }}"
    assert uploads[1]["if"] == (
        "${{ (failure() || cancelled()) && steps.prepare.outputs.output_directory != '' "
        "&& steps.prepare.outputs.native_log_directory != '' }}"
    )
    assert "${{ steps.prepare.outputs.output_directory }}/generation.json" in str(
        mapping(uploads[0]["with"])["path"]
    )
    diagnostics = str(mapping(uploads[1]["with"])["path"])
    assert "${{ steps.prepare.outputs.output_directory }}/logs/" in diagnostics
    assert "${{ steps.prepare.outputs.native_log_directory }}/" in diagnostics
    assert all("retention-days" not in mapping(step["with"]) for step in uploads)
    assert not (REPOSITORY / ".github" / "workflows" / "hhem-evaluation-api-test.yml").exists()
    assert not (REPOSITORY / "config" / "summary-eval-hhem.json").exists()


def test_workflow_scopes_the_standard_token_to_native_preparation_only() -> None:
    workflow = named_workflow()
    job = mapping(mapping(workflow["jobs"])["evaluate"])
    assert "GITHUB_TOKEN" not in mapping(workflow.get("env", {}))
    assert "GITHUB_TOKEN" not in mapping(job.get("env", {}))
    steps = job["steps"]
    assert isinstance(steps, list)
    declared = [mapping(step) for step in steps]
    prepare = next(step for step in declared if step.get("id") == "prepare")
    assert mapping(prepare["env"]) == {"GITHUB_TOKEN": "${{ secrets.GITHUB_TOKEN }}"}
    assert "run.py --root ../.. prepare" in str(prepare["run"])
    for step in declared:
        if step is not prepare:
            assert "GITHUB_TOKEN" not in mapping(step.get("env", {}))


def write_event(path: Path, inputs: dict[str, object]) -> None:
    path.write_text(json.dumps({"inputs": inputs}), encoding="utf-8")


def test_platform_input_preserves_exact_source_and_blank_model_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    source = "  PrivateSourceCanary\n$(`never run this`)  "
    reference = "  PrivateReferenceCanary\nindependent reference.  "
    write_event(
        event,
        {"source_text": source, "reference_summary_text": reference, "models_file": ""},
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    inputs = read_manual_inputs(load_pipeline_settings(REPOSITORY))
    assert inputs.source_text == source and inputs.models_file == ""
    assert inputs.reference_summary_text == reference
    assert event.is_file()


@pytest.mark.parametrize(
    "inputs",
    [
        {"source_text": "Source.", "summary_text": "Supplied answer."},
        {"source_text": "Source.", "models_file": "", "model": "PrivateValueCanary"},
        {"models_file": ""},
        {"source_text": None},
        {"source_text": True},
        {"source_text": " \n"},
        {"source_text": "Source.", "models_file": None},
        {"source_text": "Source.", "reference_summary_text": None},
        {"source_text": "Source.", "reference_summary_text": True},
        {"source_text": "Source.", "reference_summary_text": " \n"},
        {"source_text": "Source.", "reference_summary_text": "\ud800"},
    ],
)
def test_invalid_platform_inputs_fail_without_echoing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inputs: dict[str, object],
) -> None:
    event = tmp_path / "event.json"
    valid = {"reference_summary_text": "Independent reference.", **inputs}
    if inputs == {"source_text": "Source.", "summary_text": "Supplied answer."}:
        valid = inputs
    write_event(event, valid)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(load_pipeline_settings(REPOSITORY))
    assert failure.value.error.code == "INPUT_INVALID"
    assert "PrivateValueCanary" not in str(failure.value)
    assert "Source." not in failure.value.error.model_dump_json()


def test_event_envelope_overflow_fails_instead_of_truncating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    manual = load_pipeline_settings(REPOSITORY)
    event.write_bytes(b" " * (manual.max_input_bytes + manual.event_envelope_bytes + 1))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(manual)
    assert failure.value.error.code == "INPUT_TOO_LARGE"


def test_reference_must_fit_the_workflow_input_allowance_before_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    pipeline = load_pipeline_settings(REPOSITORY)
    write_event(
        event,
        {
            "source_text": "Source.",
            "reference_summary_text": "R" * pipeline.max_input_bytes,
        },
    )
    assert event.stat().st_size < pipeline.max_input_bytes + pipeline.event_envelope_bytes
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(pipeline)
    assert failure.value.error.code == "INPUT_TOO_LARGE"


@pytest.mark.parametrize("overflow", [0, 1])
def test_exact_utf8_input_allowance_and_one_byte_over_are_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overflow: int,
) -> None:
    event = tmp_path / "event.json"
    payload: dict[str, object] = {
        "source_text": "Exact source \u00e9.",
        "reference_summary_text": "Independent reference.",
        "models_file": "",
    }
    write_event(event, payload)
    from summary_eval_pipeline.inputs import ManualInputs

    expected = ManualInputs.model_validate(payload)
    size = len(expected.model_dump_json().encode("utf-8"))
    pipeline = load_pipeline_settings(REPOSITORY).model_copy(
        update={"max_input_bytes": size - overflow}
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    if overflow:
        with pytest.raises(WorkflowError) as failure:
            read_manual_inputs(pipeline)
        assert failure.value.error.code == "INPUT_TOO_LARGE"
    else:
        assert read_manual_inputs(pipeline) == expected


def test_frozen_parent_report_and_unchanged_private_machine_control_remain_readable() -> None:
    fixture = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "pipeline-evidence.json"
    report = PipelineEvidence.model_validate_json(fixture.read_bytes())
    assert report.version == WORKFLOW_VERSION and report.generation is None
    packet: dict[str, object] = {
        "version": WORKFLOW_VERSION,
        "startup_id": "12345678-1234-4234-8234-123456789abc",
        "context": {"run_id": "fixture-run", "pipeline_name": "fixture", "task_name": "score"},
    }
    read_contract(StartupPacket, packet)
    with pytest.raises(ValidationError):
        read_contract(StartupPacket, {**packet, "source_text": "PrivateSourceCanary"})
    assert PipelineEvidence.model_json_schema()["version"] == WORKFLOW_VERSION
    with pytest.raises(ValidationError):
        read_contract(
            PipelineEvidence,
            {**report.model_dump(mode="json"), "version": "2026-11-04"},
        )
    with pytest.raises(ValidationError):
        read_contract(
            PipelineEvidence,
            {**report.model_dump(mode="json"), "summary_text": "PrivateSummaryCanary"},
        )
