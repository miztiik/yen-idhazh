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


def test_named_workflow_selects_one_declaration_with_the_current_pointer_default() -> None:
    workflow = named_workflow()
    triggers = mapping(workflow["on"])
    assert set(triggers) == {"workflow_dispatch"}
    inputs = mapping(mapping(triggers["workflow_dispatch"])["inputs"])
    assert set(inputs) == {"source_text", "models_file"}
    source, model = mapping(inputs["source_text"]), mapping(inputs["models_file"])
    assert source["type"] == "string" and source["required"] is True
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
        if "summary-eval-tests/run.py" in str(step.get("run", ""))
    ]
    assert phases == ["prepare", "generate", "evaluate"]
    assert "--frozen --extra model --no-dev" in text
    assert "summary-eval-tests/report.py --root ../.." in text
    assert "bun install --frozen-lockfile --cwd services/typescript-api" in text
    for forbidden in (
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
    assert len(uploads) == 2 and uploads[0]["if"] == "always()"
    assert uploads[1]["if"] == "failure() || cancelled()"
    assert all("retention-days" not in mapping(step["with"]) for step in uploads)
    assert not (REPOSITORY / ".github" / "workflows" / "hhem-evaluation-api-test.yml").exists()
    assert not (REPOSITORY / "config" / "summary-eval-hhem.json").exists()


def test_native_ci_retains_resources_and_prepares_the_actual_shared_api() -> None:
    text = (REPOSITORY / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    selected = text[text.index("  hhem-evaluator:\n") : text.index("\n  gates:\n")]
    assert "bun install --frozen-lockfile --cwd services/typescript-api" in selected
    assert "uv sync --frozen --group dev" in selected and "--extra model" not in selected
    assert "scripts/prepare-unieval-resources.py --root ../.." in selected
    assert "uv run --frozen pytest" in selected
    assert "summary-eval-hhem/" not in selected


def write_event(path: Path, inputs: dict[str, object]) -> None:
    path.write_text(json.dumps({"inputs": inputs}), encoding="utf-8")


def test_platform_input_preserves_exact_source_and_blank_model_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = tmp_path / "event.json"
    source = "  PrivateSourceCanary\n$(`never run this`)  "
    write_event(event, {"source_text": source, "models_file": ""})
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    inputs = read_manual_inputs(service_settings(), load_pipeline_settings(REPOSITORY))
    assert inputs.source_text == source and inputs.models_file == ""
    assert list(tmp_path.iterdir()) == [event]


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
    selected, manual = service_settings(), load_pipeline_settings(REPOSITORY)
    event.write_bytes(b" " * (selected.listener.max_body_bytes + manual.event_envelope_bytes + 1))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(WorkflowError) as failure:
        read_manual_inputs(selected, manual)
    assert failure.value.error.code == "INPUT_TOO_LARGE"


def test_current_report_fixture_and_private_control_have_one_native_shape() -> None:
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
            {**report.model_dump(mode="json"), "summary_text": "PrivateSummaryCanary"},
        )
