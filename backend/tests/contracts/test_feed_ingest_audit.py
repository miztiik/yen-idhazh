"""Behavior checks for feed-ingest audit contracts and their canonical fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from idhazh.contracts.base import canonical_json
from idhazh.contracts.feed_ingest_article_assessment import ArticleAssessmentRecord
from idhazh.contracts.feed_ingest_candidate import (
    ArticleLabels,
    PolicyIdentity,
    ScoreEvidence,
    SourceSnapshot,
)
from idhazh.contracts.feed_ingest_diversity import DiversityMetricRow
from idhazh.contracts.feed_ingest_source_run import (
    LedgerCompletionEvidence,
    SourceRunRecord,
)

FIXTURE_ROOT = Path(__file__).parents[3] / "tests" / "fixtures" / "contracts"
FIXTURE_FILES = {
    "feed-ingest-source-run": FIXTURE_ROOT
    / "feed-ingest-source-run"
    / "one-observation.json",
    "feed-ingest-article-assessment": FIXTURE_ROOT
    / "feed-ingest-article-assessment"
    / "one-observation.json",
    "feed-ingest-diversity": FIXTURE_ROOT
    / "feed-ingest-diversity"
    / "one-observation.json",
}


def load_observation(stem: str) -> dict[str, Any]:
    """Load one named canonical contract fixture when a test needs it."""
    return cast("dict[str, Any]", json.loads(FIXTURE_FILES[stem].read_text(encoding="utf-8")))


def make_source_snapshot() -> dict[str, Any]:
    return {
        "source_id": "sample-feed",
        "feed_url": "https://news.example.com/feed.xml",
        "title": "Sample Feed",
        "vertical": "world",
        "kind": "reporting",
        "tier": 1,
        "form": "article",
        "status": "active",
        "weight": 1.0,
        "applied_tier_weight": 1.0,
    }


def make_policy_identity() -> dict[str, Any]:
    return {
        "policy_version": "2026-10-20",
        "config_sha256": "a" * 64,
        "min_words_article": 200,
        "min_words_abstract": 50,
        "max_age_hours": 48.0,
        "recency_half_life_hours": 24.0,
        "recency_weight": 1.0,
        "source_authority_weight": 1.0,
        "base_source_allowance": 1,
        "bonus_uncovered_event_cluster": 1,
        "bonus_underrepresented_vertical": 1,
        "bonus_unique_evidence": 1,
        "lambda_source": 0.1,
        "lambda_source_kind": 0.1,
        "lambda_domain": 0.1,
        "lambda_vertical": 0.1,
        "lambda_desk": 0.1,
        "lambda_lens": 0.1,
        "lambda_event_type": 0.1,
        "lambda_event_cluster": 0.1,
        "lambda_entity": 0.1,
        "lambda_coverage": 0.1,
    }


def make_labels() -> dict[str, Any]:
    return {
        "assigned_desk": None,
        "lenses": None,
        "event_types": None,
        "event_cluster_id": None,
        "entities": None,
        "origin": None,
        "matcher_version": None,
    }


def make_score_evidence() -> dict[str, Any]:
    penalty = {"available": False, "value": None}
    return {
        "base_article_score": 1.0,
        "marginal_score": 0.9,
        "source": penalty,
        "source_kind": penalty,
        "domain": penalty,
        "vertical": penalty,
        "desk": penalty,
        "lens": penalty,
        "event_type": penalty,
        "event_cluster": penalty,
        "entity": penalty,
        "coverage": penalty,
        "source_allowance": 1,
        "bonus_uncovered_event_cluster": False,
        "bonus_underrepresented_vertical": False,
        "bonus_unique_evidence": False,
        "carrier_outlets": [],
        "representative_url_key": None,
        "replacement_url_key": None,
        "exploration_slot": False,
        "cap_relaxations": [],
    }


def make_completion_evidence() -> list[dict[str, Any]]:
    ledgers = (
        "article-assessments",
        "diversity",
        "editorial-selections",
        "dispatches",
        "rejections",
    )
    return [{"ledger": ledger, "row_count": 0, "files": []} for ledger in ledgers]


def make_source_run() -> dict[str, Any]:
    return {
        "date": "2026-10-20",
        "correlation_id": "feed-plan-2026-10-20-1",
        "run_id": "2026-10-20-1",
        "attempt": 1,
        "source_id": "sample-feed",
        "source": make_source_snapshot(),
        "status": "active",
        "fetch_status": "not_requested",
        "parse_status": "not_attempted",
        "parsed_count": None,
        "harvested_count": None,
        "fresh_count": None,
        "duplicate_count": None,
        "eligible_count": None,
        "normalized_count": None,
        "selected_count": None,
        "published_count": None,
        "lead_count": None,
        "drop_reasons": [],
        "fetch_duration_ms": None,
        "parse_duration_ms": None,
        "last_failure_at": None,
        "last_failure_reason": None,
        "history_success_fraction": None,
        "history_success_attempts": None,
        "history_window_days": None,
        "observation_phase": "plan_complete",
        "observed_at": "2026-10-20T08:00:00Z",
        "expected_source_count": 1,
        "completion_evidence": make_completion_evidence(),
    }


def make_assessment() -> dict[str, Any]:
    return {
        "date": "2026-10-20",
        "correlation_id": "feed-plan-2026-10-20-1",
        "candidate_id": "b" * 64,
        "source_id": "sample-feed",
        "source": make_source_snapshot(),
        "labels": make_labels(),
        "canonical_url": None,
        "url_key": None,
        "stage": "screen-article-candidates",
        "decision": "admitted",
        "reason": None,
        "observed_at": "2026-10-20T08:00:00Z",
        "policy": make_policy_identity(),
        "timing_at": None,
        "timing_basis": "unavailable",
        "age_hours": None,
        "max_age_hours": None,
        "extracted_word_count": None,
        "source_form": "article",
        "extraction_outcome": "not_attempted",
        "word_threshold": None,
        "author_present": None,
        "publisher_identity": None,
        "attribution_status": "unavailable",
        "paywall": None,
        "categories": None,
        "required_fields_present": None,
        "suitability_status": "unavailable",
        "informative_verdict_status": "not_assessed",
        "informative_verdict": None,
        "informative_evaluator_version": None,
        "suitability_verdict_status": "not_assessed",
        "suitability_verdict": None,
        "suitability_evaluator_version": None,
        "score_evidence": None,
        "score_evidence_status": "not_assessed",
    }


def make_diversity() -> dict[str, Any]:
    return {
        "date": "2026-10-20",
        "correlation_id": "feed-plan-2026-10-20-1",
        "run_id": "2026-10-20-1",
        "metric": "effective_number_of_sources",
        "basis": "selected",
        "as_of": "2026-10-20T08:00:00Z",
        "window_start": None,
        "window_end": None,
        "dimension": "source",
        "stage": None,
        "window_days": None,
        "dimension_value": None,
        "value": 0.0,
        "unit": "sources",
        "before_value": None,
        "after_value": None,
        "numerator": None,
        "denominator": None,
        "item_count": 0,
        "source_count": 0,
        "history_coverage_days": None,
        "history_required_days": None,
        "algorithm_version": "1",
        "config_sha256": "a" * 64,
        "availability": "available",
        "unavailable_reason": None,
        "top_k": None,
    }


def test_named_canonical_observations_round_trip() -> None:
    contracts = (
        (SourceRunRecord, "feed-ingest-source-run"),
        (ArticleAssessmentRecord, "feed-ingest-article-assessment"),
        (DiversityMetricRow, "feed-ingest-diversity"),
    )
    for contract, stem in contracts:
        record = contract.model_validate(load_observation(stem))
        assert record.version == contract.schema_version()
        assert contract.model_validate_json(canonical_json(record.model_dump(mode="json"))) == record


def test_source_observation_distinguishes_unavailable_from_known_zero() -> None:
    unavailable = SourceRunRecord.model_validate(make_source_run())
    assert unavailable.parsed_count is None

    empty = make_source_run()
    empty.update(
        fetch_status="success",
        parse_status="empty",
        fetch_duration_ms=0,
        parse_duration_ms=0,
        parsed_count=0,
        harvested_count=0,
    )
    assert SourceRunRecord.model_validate(empty).parsed_count == 0


def test_completion_evidence_proves_empty_and_nonempty_ledger_files() -> None:
    empty = LedgerCompletionEvidence.model_validate(make_completion_evidence()[0])
    assert empty.row_count == 0
    assert empty.files == []

    invalid_empty = {
        "ledger": "diversity",
        "row_count": 0,
        "files": [{
            "file_id": "01890f3e-7c00-8000-8000-000000000000",
            "content_sha256": "e" * 64,
            "row_count": 1,
        }],
    }
    with pytest.raises(ValidationError):
        LedgerCompletionEvidence.model_validate(invalid_empty)

    nonempty = {
        "ledger": "diversity",
        "row_count": 2,
        "files": [{
            "file_id": "01890f3e-7c00-8000-8000-000000000000",
            "content_sha256": "e" * 64,
            "row_count": 2,
        }],
    }
    assert LedgerCompletionEvidence.model_validate(nonempty).row_count == 2


def test_assessment_keeps_unassessed_evidence_null_and_measured_zero() -> None:
    unknown = ArticleAssessmentRecord.model_validate(make_assessment())
    assert unknown.extracted_word_count is None
    assert unknown.informative_verdict_status == "not_assessed"

    measured = make_assessment()
    measured.update(
        extraction_outcome="success",
        extracted_word_count=0,
        word_threshold=200,
    )
    assert ArticleAssessmentRecord.model_validate(measured).extracted_word_count == 0


def test_diversity_zero_is_distinct_from_unavailable_and_nonfinite_is_rejected() -> None:
    known_empty = DiversityMetricRow.model_validate(make_diversity())
    assert known_empty.value == 0.0

    unavailable = make_diversity()
    unavailable.update(
        value=None,
        availability="unavailable",
        unavailable_reason="missing_publication",
        basis="published",
    )
    assert DiversityMetricRow.model_validate(unavailable).value is None

    nonfinite = make_diversity()
    nonfinite["value"] = float("inf")
    with pytest.raises(ValidationError):
        DiversityMetricRow.model_validate(nonfinite)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_ratio_reading_rejects_values_outside_unit_interval(value: float) -> None:
    reading = make_diversity() | {
        "metric": "active_source_coverage", "unit": "ratio", "value": value,
    }
    with pytest.raises(ValidationError, match="ratio readings"):
        DiversityMetricRow.model_validate(reading)


@pytest.mark.parametrize("value", [-1.0, 0.5])
def test_count_reading_rejects_negative_and_fractional_values(value: float) -> None:
    reading = make_diversity() | {
        "metric": "source_kind_distribution",
        "dimension": "source_kind",
        "dimension_value": "reporting",
        "unit": "count",
        "value": value,
    }
    with pytest.raises(ValidationError, match="count readings"):
        DiversityMetricRow.model_validate(reading)


def test_count_and_effective_source_readings_accept_their_distinct_number_domains() -> None:
    count = make_diversity() | {
        "metric": "source_kind_distribution",
        "dimension": "source_kind",
        "dimension_value": "reporting",
        "unit": "count",
        "value": 2.0,
    }
    assert DiversityMetricRow.model_validate(count).value == 2.0
    assert DiversityMetricRow.model_validate(make_diversity() | {"value": 1.5}).value == 1.5
    with pytest.raises(ValidationError, match="effective-source readings"):
        DiversityMetricRow.model_validate(make_diversity() | {"value": -0.5})


def test_lost_diversity_accepts_signed_difference_with_nonnegative_endpoints() -> None:
    reading = make_diversity() | {
        "metric": "lost_diversity_by_stage",
        "basis": "stage",
        "stage": "selection",
        "unit": "source_difference",
        "before_value": 1.5,
        "after_value": 2.0,
        "value": -0.5,
    }
    assert DiversityMetricRow.model_validate(reading).value == -0.5
    for before, after in ((-1.0, 0.0), (0.0, -1.0)):
        invalid = reading | {
            "before_value": before, "after_value": after, "value": before - after,
        }
        with pytest.raises(ValidationError, match="before and after readings"):
            DiversityMetricRow.model_validate(invalid)


def test_shared_candidate_models_remain_closed_to_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SourceSnapshot.model_validate(make_source_snapshot() | {"future_field": 1})
    with pytest.raises(ValidationError):
        ArticleLabels.model_validate(make_labels() | {"future_label": "value"})
    with pytest.raises(ValidationError):
        PolicyIdentity.model_validate(make_policy_identity() | {"effective_policy_json": {}})
    with pytest.raises(ValidationError):
        ScoreEvidence.model_validate(make_score_evidence() | {"extra_score": 1})
