"""Verify the named form, visible phases and bounded platform-data boundary."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from summary_eval_pipeline.contracts import WORKFLOW_VERSION, PipelineEvidence
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import read_manual_inputs
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator_cases.contract_examples import REPOSITORY, read_contract


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
    assert inputs.evaluate_relevance is False
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
        {"source_text": "Source.", "evaluate_relevance": None},
        {"source_text": "Source.", "evaluate_relevance": 0},
        {"source_text": "Source.", "evaluate_relevance": 1},
        {"source_text": "Source.", "evaluate_relevance": "False"},
        {"source_text": "Source.", "evaluate_relevance": ""},
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


@pytest.mark.parametrize("reference", [None, ""])
@pytest.mark.parametrize("boolean", [None, False, True, "false", "true"])
def test_platform_empty_reference_and_canonical_boolean_are_normalized_only_at_the_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    reference: str | None, boolean: bool | str | None,
) -> None:
    payload: dict[str, object] = {"source_text": "Exact source."}
    if reference is not None:
        payload["reference_summary_text"] = reference
    if boolean is not None:
        payload["evaluate_relevance"] = boolean
    event = tmp_path / "event.json"
    write_event(event, payload)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    inputs = read_manual_inputs(load_pipeline_settings(REPOSITORY))
    assert inputs.reference_summary_text is None
    assert inputs.reference_summary_sha256 is None
    assert inputs.evaluate_relevance is (boolean is True or boolean == "true")
    assert "reference_summary_text" not in inputs.model_dump()
    from summary_eval_pipeline.inputs import ManualInputs

    with pytest.raises(ValidationError):
        ManualInputs(source_text="Source.", reference_summary_text="")
    with pytest.raises(ValidationError):
        ManualInputs.model_validate({"source_text": "Source.", "evaluate_relevance": "true"})
