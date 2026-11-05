"""Do private evaluation documents validate their schema examples and software invariants?"""

from __future__ import annotations

import json
from typing import Any

import pytest
from support.paths import CONTRACT_FIXTURES_DIR

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.content_similarity_judge_evaluation import (
    EvaluationAnnotation,
    EvaluationLabels,
    EvaluationReading,
    EvaluationReport,
    EvaluationRun,
    EvaluationSet,
)
from idhazh.contracts.story_similarity_pair import SameStoryVerdict

pytestmark = pytest.mark.contract
DOCUMENTS = (EvaluationSet, EvaluationLabels, EvaluationRun, EvaluationReport)


@pytest.mark.parametrize("model", DOCUMENTS)
def test_named_schema_example_is_canonical_and_closed(
    model: type[EvaluationSet | EvaluationLabels | EvaluationRun | EvaluationReport],
) -> None:
    path = CONTRACT_FIXTURES_DIR / model.__schema_stem__ / "example.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    document = model.model_validate(original)
    assert json.loads(document.to_json()) == original
    assert model.from_json(document.to_json()) == document
    assert model.json_schema()["version"] == "2026-11-05"
    with pytest.raises(ValueError):
        model.model_validate(original | {"destination": "https://invalid.test:8443"})


def test_annotations_bind_reviewer_identity_and_exact_rubric() -> None:
    base = EvaluationLabels(
        version=EvaluationLabels.schema_version(),
        set_sha256="a" * 64, rubric="A rubric.",
        rubric_sha256=derive_text_digest("A rubric."), annotations=(),
    )
    with pytest.raises(ValueError, match="rubric"):
        EvaluationLabels.model_validate(base.model_dump() | {"rubric": "Another rubric."})
    row = EvaluationAnnotation(
        case_id="b" * 64, input_sha256="c" * 64, reviewer_key="reviewer-a",
        role="primary", origin="human", verdict=SameStoryVerdict.YES,
        marked_at="2026-11-05T00:00:00Z",
    )
    with pytest.raises(ValueError, match="duplicate reviewer"):
        EvaluationLabels.model_validate(base.model_dump() | {
            "annotations": [row, row.model_copy(update={"role": "independent"})],
        })


def test_refusal_and_completed_span_evidence_cannot_disagree() -> None:
    reading: dict[str, Any] = {
        "verdict": None, "grammar_applied": False, "refusal_reason": "missing_emission",
        "prompt_tokens": 1, "completion_tokens": 1, "elapsed_seconds": 0.1,
        "first_token_margin": None, "first_token_window": None, "thinking_spans": 0,
        "request_json": ["{}"], "raw_response": ['{"content":"YES"}'],
    }
    EvaluationReading.model_validate(reading)
    for changed in (
        {"verdict": "NO"}, {"refusal_reason": None}, {"prompt_tokens": True},
        {"completion_tokens": -1}, {"elapsed_seconds": float("inf")},
        {"thinking_spans": 1}, {"request_json": ["null"]},
    ):
        with pytest.raises(ValueError):
            EvaluationReading.model_validate(reading | changed)


def test_incomplete_documents_cannot_claim_capture_or_measurement() -> None:
    run = EvaluationRun.read(
        CONTRACT_FIXTURES_DIR / EvaluationRun.__schema_stem__ / "example.json"
    )
    with pytest.raises(ValueError, match="both readings"):
        EvaluationRun.model_validate(run.model_dump() | {"state": "captured"})
    report = EvaluationReport.read(
        CONTRACT_FIXTURES_DIR / EvaluationReport.__schema_stem__ / "example.json"
    )
    invalid_changes: tuple[dict[str, object], ...] = (
        {"state": "measured"}, {"blockers": []}, {"streams": report.streams[:1]},
    )
    for changes in invalid_changes:
        with pytest.raises(ValueError):
            EvaluationReport.model_validate(report.model_dump() | changes)


@pytest.mark.parametrize("bad_count", [-1, True, 1.5, "1"])
def test_counts_are_strict_and_reconcile_with_support(bad_count: object) -> None:
    report = EvaluationReport.read(
        CONTRACT_FIXTURES_DIR / EvaluationReport.__schema_stem__ / "example.json"
    )
    raw = report.model_dump()
    raw["streams"][0]["case_count"] = bad_count
    with pytest.raises(ValueError):
        EvaluationReport.model_validate(raw)
