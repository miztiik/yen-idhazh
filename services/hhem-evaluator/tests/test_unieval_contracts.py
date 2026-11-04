"""Verify exact four-score requests, configured modes and honest completed results."""

import json

import pytest
from pydantic import ValidationError

from hhem_evaluator.api_settings import load_api_settings
from hhem_evaluator.contracts.unieval_contract import DIMENSIONS, UNIEVAL_VERSION
from hhem_evaluator.contracts.unieval_request import UnievalRequest
from hhem_evaluator.contracts.unieval_result import UnievalResult
from hhem_evaluator.load_unieval_settings import load_unieval_settings

from .contract_examples import REPOSITORY
from .unieval_cases import read_unieval_recordings


def test_required_reference_and_optional_controls_preserve_original_text() -> None:
    request = UnievalRequest(
        source_text=" Source body. \n",
        summary_text=" Generated answer. ",
        reference_summary_text="\nIndependent reference. ",
    )
    assert request.source_text == " Source body. \n"
    assert request.reference_summary_text == "\nIndependent reference. "
    schema = UnievalRequest.model_json_schema()
    assert set(schema["required"]) == {"source_text", "summary_text", "reference_summary_text"}
    assert "consistency_source_mode" not in request.model_dump_json()
    for update in (
        {"reference_summary_text": ""},
        {"reference_summary_text": None},
        {"consistency_source_mode": None},
        {"consistency_source_mode": "retrieved_source_passages"},
        {"summary_text": True},
        {"destination": "PrivateValueCanary"},
    ):
        with pytest.raises(ValidationError):
            UnievalRequest.model_validate({**request.model_dump(), **update})


def test_named_settings_freeze_all_assets_and_source_geometry() -> None:
    api = load_api_settings(REPOSITORY / "config" / "fastapi-server.json")
    settings = load_unieval_settings(REPOSITORY, api)
    assert settings.version == UNIEVAL_VERSION
    assert settings.listener == api.listener
    assert settings.scoring.consistency_source_mode == "all_source_windows"
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
    assert schema["version"] == UNIEVAL_VERSION
    assert set(schema["$defs"]["UnievalScores"]["properties"]) == set(DIMENSIONS)
