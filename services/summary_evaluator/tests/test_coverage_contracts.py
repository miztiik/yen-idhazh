"""Does coverage admit only prepared text and retain the historical metric vocabulary?"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageResult
from summary_evaluator.source_coverage.contracts.service_settings import AuthoredCoverageSettings

ROOT = Path(__file__).resolve().parents[3]


def test_coverage_accepts_only_explicit_prepared_text() -> None:
    request = CoverageRequest(source_text="Prepared source.", summary_text="Prepared summary.")
    assert request.model_dump() == {
        "source_text": "Prepared source.", "summary_text": "Prepared summary."
    }
    for value in (
        {"sourceText": "Source.", "summaryText": "Summary."},
        {**request.model_dump(), "source_title": "Title"},
        {**request.model_dump(), "source_text": " "},
        {**request.model_dump(), "summary_text": None},
        {**request.model_dump(), "summary_text": 1},
    ):
        with pytest.raises(ValidationError):
            CoverageRequest.model_validate(value)


def test_existing_response_is_wire_parity_not_a_calculation_recording() -> None:
    path = ROOT / "tests" / "fixtures" / "typescript-metadata" / "evaluator-response.json"
    historical = json.loads(path.read_bytes())
    result = CoverageResult.model_validate_json(
        json.dumps({"status": historical["status"], "metrics": historical["metrics"]})
    )
    assert result.metrics.model_dump(mode="json", exclude_none=True) == historical["metrics"]
    assert set(CoverageResult.model_fields) == {"status", "metrics"}


def test_named_coverage_config_keeps_legacy_effective_defaults() -> None:
    settings = AuthoredCoverageSettings.model_validate_json(
        (ROOT / "config" / "summary-evals" / "unieval-evaluator" / "coverage.json").read_bytes()
    )
    assert settings.preparation.chunk_words == 380
    assert settings.preparation.stride_words == 80
    assert settings.preparation.grounding_threshold == 0.5
    assert settings.model.max_length == 1024
    assert settings.model.device == "cpu"
    assert settings.model.threads == "logical_processors"
    with pytest.raises(ValidationError):
        AuthoredCoverageSettings.model_validate_json(
            settings.model_dump_json().replace('"stride_words":80', '"stride_words":380')
        )
