"""Verify exact four-score requests, configured modes and honest completed results."""

import json

import pytest
from pydantic import ValidationError
from summary_evaluator_cases.contract_examples import REPOSITORY, example_previous_unieval_result
from summary_evaluator_cases.unieval_cases import read_unieval_recordings

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.contracts.previous_unieval_result import PreviousUnievalResult
from summary_evaluator.unieval.contracts.unieval_contract import (
    DIMENSIONS,
    UNIEVAL_SCORING_VERSION,
    SourceMode,
)
from summary_evaluator.unieval.contracts.unieval_recording import UnievalRecordingInputs
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult


def test_optional_reference_and_strict_controls_preserve_original_text() -> None:
    request = UnievalRequest(
        source_text=" Source body. \n",
        summary_text=" Generated answer. ",
        reference_summary_text="\nIndependent reference. ",
    )
    assert request.source_text == " Source body. \n"
    assert request.reference_summary_text == "\nIndependent reference. "
    schema = UnievalRequest.model_json_schema()
    assert set(schema["required"]) == {"source_text", "summary_text"}
    assert UnievalRequest(source_text="Source.", summary_text="Summary.").model_dump() == {
        "source_text": "Source.", "summary_text": "Summary.",
    }
    assert "consistency_source_mode" not in request.model_dump_json()
    for update in (
        {"reference_summary_text": ""},
        {"reference_summary_text": None},
        {"reference_summary_text": " \n"},
        {"evaluate_relevance": None},
        {"evaluate_relevance": 0},
        {"evaluate_relevance": 1},
        {"evaluate_relevance": "false"},
        {"evaluate_relevance": "true"},
        {"consistency_source_mode": None},
        {"consistency_source_mode": ""},
        {"consistency_source_mode": " full_source_prompt"},
        {"consistency_source_mode": "all_source_windows "},
        {"consistency_source_mode": False},
        {"consistency_source_mode": ["full_source_prompt"]},
        {"consistency_source_mode": "retrieved_source_passages"},
        {"summary_text": True},
        {"destination": "PrivateValueCanary"},
    ):
        with pytest.raises(ValidationError):
            UnievalRequest.model_validate({**request.model_dump(), **update})


def test_named_settings_freeze_all_assets_and_source_geometry() -> None:
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    assert settings.version == UNIEVAL_SCORING_VERSION
    assert settings.scoring.evaluate_relevance is False
    assert settings.listener == api.listener
    assert settings.scoring.consistency_source_mode == "full_source_prompt"
    assert settings.assets.model.revision == "ed8da5a8aa01b19d49a5f8738d382ced54b73ad0"
    assert settings.prompts.relevance.format(summary="Answer", reference="Reference")
    changed = settings.model_dump(mode="json")
    changed["scoring"]["source_overlap_tokens"] = changed["scoring"]["source_window_tokens"]
    with pytest.raises(ValidationError):
        type(settings).model_validate_json(json.dumps(changed))


def test_recordings_have_no_fabricated_missing_or_out_of_range_scores() -> None:
    _, predictions, identity = read_unieval_recordings()
    assert identity.loaded_revision == identity.tokenizer_revision
    assert all(
        0 <= comparison.score <= 1 for case in predictions.cases for comparison in case.comparisons
    )
    assert set(DIMENSIONS) == {"fluency", "coherence", "consistency", "relevance"}
    schema = UnievalResult.model_json_schema()
    assert schema["version"] == UNIEVAL_SCORING_VERSION
    assert set(schema["$defs"]["UnievalScores"]["properties"]) == set(DIMENSIONS)


def test_previous_result_reader_keeps_required_four_scores_and_original_identity() -> None:
    original = example_previous_unieval_result("a" * 64).model_dump_json()
    saved = PreviousUnievalResult.model_validate_json(original)
    assert saved.version == "2026-11-04"
    assert saved.model_dump_json() == original
    payload = saved.model_dump(mode="json")
    payload["scores"]["relevance"] = None
    with pytest.raises(ValidationError, match="all four"):
        PreviousUnievalResult.model_validate_json(json.dumps(payload))
    payload = saved.model_dump(mode="json")
    payload["effective_settings"]["evaluate_relevance"] = False
    with pytest.raises(ValidationError):
        PreviousUnievalResult.model_validate_json(json.dumps(payload))


def test_previous_recording_reader_keeps_required_reference_and_original_controls() -> None:
    saved = UnievalRecordingInputs.model_validate_json(
        (REPOSITORY / "tests" / "fixtures" / "unieval-evaluator" / "model-inputs.json").read_bytes()
    )
    payload = saved.model_dump(mode="json")
    assert saved.version == "2026-11-04"
    assert "evaluate_relevance" not in payload["cases"][0]["request"]
    assert "evaluate_relevance" not in payload["cases"][0]["controls"]
    del payload["cases"][0]["request"]["reference_summary_text"]
    with pytest.raises(ValidationError):
        UnievalRecordingInputs.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("default", [False, True])
@pytest.mark.parametrize("selected", [None, False, True])
@pytest.mark.parametrize("reference", [None, "  Exact reference.\n"])
def test_only_resolved_boolean_and_reference_presence_select_relevance(
    default: bool, selected: bool | None, reference: str | None,
) -> None:
    from summary_evaluator.unieval.resolve_unieval_selection import resolve_unieval_selection

    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    payload: dict[str, object] = {"source_text": "Source.", "summary_text": "Summary."}
    if selected is not None:
        payload["evaluate_relevance"] = selected
    if reference is not None:
        payload["reference_summary_text"] = reference
    request = UnievalRequest.model_validate(payload)
    controls, reason = resolve_unieval_selection(
        request, settings.scoring.model_copy(update={"evaluate_relevance": default})
    )
    enabled = default if selected is None else selected
    assert controls.evaluate_relevance is enabled
    assert controls.consistency_source_mode == settings.scoring.consistency_source_mode
    assert reason == (
        "disabled" if not enabled else "reference_not_supplied" if reference is None else None
    )
    assert request.reference_summary_text == reference


@pytest.mark.parametrize("default", ["full_source_prompt", "all_source_windows"])
@pytest.mark.parametrize("selected", [None, "full_source_prompt", "all_source_windows"])
def test_explicit_mode_overrides_configuration_without_selecting_relevance(
    default: SourceMode, selected: SourceMode | None,
) -> None:
    from summary_evaluator.unieval.resolve_unieval_selection import resolve_unieval_selection

    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    payload: dict[str, object] = {
        "source_text": " Source.\n", "summary_text": "Summary.",
        "reference_summary_text": " Unused independent reference.\n",
    }
    if selected is not None:
        payload["consistency_source_mode"] = selected
    request = UnievalRequest.model_validate(payload)
    configured = settings.scoring.model_copy(update={"consistency_source_mode": default})
    controls, reason = resolve_unieval_selection(request, configured)
    assert controls.consistency_source_mode == (default if selected is None else selected)
    assert controls.model_dump(exclude={"consistency_source_mode"}) == configured.model_dump(
        exclude={"consistency_source_mode"}
    )
    assert reason == "disabled" and request.reference_summary_text == payload[
        "reference_summary_text"
    ]
    assert request.consistency_source_mode == selected
