"""Do the four lean planner records distinguish unknown, zero and actual work?"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from idhazh.contracts.feed_health_state import FeedHealthReliability, FeedHealthStateRow
from idhazh.contracts.feed_ingest_candidate import SourceSnapshot
from idhazh.contracts.feed_ingest_discovered_article import DiscoveredArticleRow
from idhazh.contracts.feed_ingest_plan_run import PlanRunRow
from idhazh.contracts.feed_ingest_selected_article import SelectedArticleRatings, SelectedArticleRow

from ._fixtures import planner_payload

pytestmark = pytest.mark.contract


def load_observation(stem: str) -> dict[str, Any]:
    return planner_payload(stem)


def make_source_snapshot() -> dict[str, Any]:
    return dict(planner_payload("FeedIngestCandidate")["source"])


def make_policy_identity() -> dict[str, Any]:
    return dict(planner_payload("selected-articles")["ratings"])


def make_labels() -> dict[str, Any]:
    return dict(planner_payload("feed-health-state")["reliability"])


def make_score_evidence() -> dict[str, Any]:
    return dict(planner_payload("selected-articles")["ratings"])


def make_source_run() -> dict[str, Any]:
    return planner_payload("plan-runs")


def make_assessment() -> dict[str, Any]:
    return planner_payload("selected-articles")


def make_diversity() -> dict[str, Any]:
    return planner_payload("feed-health-state")


def test_named_canonical_observations_round_trip() -> None:
    for model, name, version in (
        (DiscoveredArticleRow, "discovered-articles", "2026-10-25"),
        (SelectedArticleRow, "selected-articles", "2026-10-26"),
        (FeedHealthStateRow, "feed-health-state", "2026-10-25"),
        (PlanRunRow, "plan-runs", "2026-10-26"),
    ):
        row = model.model_validate(load_observation(name))
        assert model.from_json(row.to_json()) == row
        assert "version" not in row.model_dump()
        assert model.json_schema()["version"] == version
        assert model.json_schema()["changelog"][0]["version"] == version


def test_source_observation_distinguishes_unavailable_from_known_zero() -> None:
    payload = make_diversity()
    unknown = FeedHealthStateRow.model_validate(payload | {
        "article_requests": None, "counts_complete": False, "reliability": None,
    })
    assert unknown.article_requests is None and unknown.reliability is None
    zero = FeedHealthStateRow.model_validate(payload | {"article_requests": 0})
    assert zero.article_requests == 0 and zero.counts_complete
    with pytest.raises(ValidationError):
        FeedHealthStateRow.model_validate(payload | {"article_requests": None})


def test_completion_evidence_proves_empty_and_nonempty_ledger_files() -> None:
    # A run result now states zero directly; completion-file audit trees are gone.
    payload = make_source_run()
    empty = PlanRunRow.model_validate(payload)
    assert empty.selected_count == 0 and empty.selected_articles_artifact is None
    partial = PlanRunRow.model_validate(payload | {
        "status": "partial", "failure_code": "article-work-failed", "selected_count": 1,
        "selected_articles_artifact": "selected-articles-fixture",
    })
    assert partial.selected_count == 1
    with pytest.raises(ValidationError):
        PlanRunRow.model_validate(payload | {"completion_evidence": []})
    with pytest.raises(ValidationError):
        PlanRunRow.model_validate({name: value for name, value in payload.items() if name != "selected_count"})


def test_assessment_keeps_unassessed_evidence_null_and_measured_zero() -> None:
    row = SelectedArticleRow.model_validate(make_assessment())
    assert [item.value for item in row.ratings.adjustments] == [None, 0.0, -0.25]
    assert row.publisher_id is None
    assert row.published_at == "2026-10-20T10:00:00.123Z"
    assert row.published_at_source == "selection"
    assert row.ratings.recency_score == 1.0 and row.ratings.feed_authority_score == 0.5
    for changed in ({"article_text": "artifact-only"}, {"published_at": None},
                    {"published_at_source": "legacy-unavailable"}):
        with pytest.raises(ValidationError):
            SelectedArticleRow.model_validate(make_assessment() | changed)
    with pytest.raises(ValueError, match="incompatible planner row schema version"):
        SelectedArticleRow.read_row(make_assessment(), schema_version="2026-10-25")


def test_diversity_zero_is_distinct_from_unavailable_and_nonfinite_is_rejected() -> None:
    payload = make_diversity()
    reliability = dict(payload["reliability"])
    reliability |= {
        "productive": 0, "attempted": 1, "success_fraction": 0.0,
        "production_factor": 0.5, "from_day": "2026-10-01", "through_day": "2026-10-19",
    }
    row = FeedHealthStateRow.model_validate(payload | {"reliability": reliability})
    assert row.reliability is not None and row.reliability.success_fraction == 0.0
    with pytest.raises(ValidationError):
        FeedHealthStateRow.model_validate(payload | {"reliability": reliability | {"success_fraction": float("inf")}})


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_ratio_reading_rejects_values_outside_unit_interval(value: float) -> None:
    payload = make_diversity()
    with pytest.raises(ValidationError):
        FeedHealthStateRow.model_validate(payload | {"reliability": payload["reliability"] | {"success_fraction": value}})


@pytest.mark.parametrize("value", [-1.0, 0.5])
def test_count_reading_rejects_negative_and_fractional_values(value: float) -> None:
    for field in ("feed_reads", "productive_reads", "failed_reads", "feed_requests", "article_requests", "robots_requests", "items"):
        with pytest.raises(ValidationError):
            FeedHealthStateRow.model_validate(make_diversity() | {field: value})
    with pytest.raises(ValidationError):
        PlanRunRow.model_validate(make_source_run() | {"duration_ms": value})
    with pytest.raises(ValidationError):
        SelectedArticleRow.model_validate(make_assessment() | {"estimated_work": value})


def test_count_and_effective_source_readings_accept_their_distinct_number_domains() -> None:
    payload = make_source_run()
    assert PlanRunRow.model_validate(payload | {"duration_ms": 0}).duration_ms == 0
    assert PlanRunRow.model_validate(payload | {"reliability_floor": 0.5}).reliability_floor == 0.5
    with pytest.raises(ValidationError):
        PlanRunRow.model_validate(payload | {"duration_ms": True})


def test_lost_diversity_accepts_signed_difference_with_nonnegative_endpoints() -> None:
    payload = make_assessment()
    ratings = make_score_evidence() | {"adjustments": [
        {"term": "domain", "value": -0.5}, {"term": "evidence", "value": 0.25},
        {"term": "publisher", "value": None},
    ]}
    row = SelectedArticleRow.model_validate(payload | {"ratings": ratings})
    assert [term.value for term in row.ratings.adjustments] == [-0.5, 0.25, None]
    with pytest.raises(ValidationError):
        SelectedArticleRow.model_validate(payload | {"ratings": ratings | {"adjustments": [{"term": 2, "value": 0.0}]}})


def test_shared_candidate_models_remain_closed_to_unknown_fields() -> None:
    for model, payload in (
        (SourceSnapshot, make_source_snapshot()), (SelectedArticleRatings, make_policy_identity()),
        (FeedHealthReliability, make_labels()),
    ):
        model.model_validate(payload)
        with pytest.raises(ValidationError):
            model.model_validate(payload | {"hidden_policy_tree": {}})
