"""Do chart labels join one exact queue without changing machine contracts?"""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.review_queue import ReviewQueue
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.contracts.visual_label import (
    VisualLabel,
    VisualLabelDraw,
    VisualLabelRow,
    visual_label_draw_id,
)
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.visual_outcomes import project_visual_outcome

pytestmark = pytest.mark.contract


def _fixture(name: str) -> str:
    return read_text(CONTRACT_FIXTURES_DIR / name)


def test_visual_id_uses_only_the_decision_source_fields_and_is_not_persisted() -> None:
    decision = VisualDecision.from_json(_fixture("visual-decision/chart-rendered.json"))
    expected = derive_text_digest(
        "\0".join(
            ("visual-id-v1", decision.item_id, decision.url_key, decision.decided_at)
        )
    )

    assert decision.visual_id == expected
    assert "visual_id" not in decision.model_dump()
    assert decision.model_copy(update={"rationale": "different text"}).visual_id == expected
    assert (
        decision.model_copy(update={"item_id": "ai-02"}).visual_id
        != expected
    )


def test_draw_fixture_binds_the_exact_queue_bytes_and_url() -> None:
    queue_bytes = (CONTRACT_FIXTURES_DIR / "review-queue/published-pie-and-bubble.json").read_bytes()
    draw = VisualLabelDraw.from_json(_fixture("visual-label-draw/published-pie-and-bubble.json"))
    queue = ReviewQueue.from_json(queue_bytes.decode("utf-8"))

    assert hashlib.sha256(queue_bytes).hexdigest() == draw.queue_sha256
    assert queue.date == draw.queue_date
    assert draw.draw_id == visual_label_draw_id(
        queue_sha256=draw.queue_sha256,
        queue_date=draw.queue_date,
        published_base_url=draw.published_base_url,
        visual_types=draw.visual_types,
    )


def test_draw_rejects_a_changed_destination_or_non_published_url() -> None:
    payload = json.loads(_fixture("visual-label-draw/published-pie-and-bubble.json"))

    with pytest.raises(ValidationError, match="draw_id"):
        VisualLabelDraw.model_validate(payload | {"published_base_url": "https://elsewhere.example"})
    with pytest.raises(ValidationError):
        VisualLabelDraw.model_validate(payload | {"published_base_url": "http://news.example"})
    with pytest.raises(ValidationError):
        VisualLabelDraw.model_validate(payload | {"published_base_url": "https://news.example/?q=1"})


def test_label_csv_round_trips_one_named_answer_and_position() -> None:
    row = VisualLabelRow.from_json(_fixture("visual-label-row/one-reviewer-keeps-a-pie.json"))

    assert row.label is VisualLabel.KEEP
    assert row.queue_position == 1
    assert VisualLabelRow.from_csv_row(row.csv_row()) == row
    assert tuple(row.csv_row()) == VisualLabelRow.csv_columns()


def test_decision_identity_propagates_to_item_health_and_attempt_contracts() -> None:
    decision = VisualDecision.from_json(_fixture("visual-decision/chart-rendered.json"))
    projected = project_visual_outcome(decision)
    health = ItemHealthRow.model_validate(
        json.loads(_fixture("item-health-row/published.json")) | projected
    )
    attempt = VisualAttemptRow.model_validate(
        json.loads(_fixture("visual-attempt-row/published-chart.json"))
        | {"visual_id": decision.visual_id}
    )

    assert health.visual_id == decision.visual_id
    assert attempt.visual_id == decision.visual_id
    assert ItemHealthRow.from_json(health.to_json()).visual_id == decision.visual_id
    assert VisualAttemptRow.from_json(attempt.to_json()).visual_id == decision.visual_id
    assert VisualAttemptRow.from_json(
        _fixture("visual-attempt-row/published-chart.json")
    ).visual_id is None


def test_legacy_payloads_remain_readable_without_a_synthesized_identity() -> None:
    queue = ReviewQueue.from_json(_fixture("review-queue/one-of-each-population.json"))
    attempt = VisualAttemptRow.from_json(_fixture("visual-attempt-row/published-chart.json"))
    health = ItemHealthRow.from_json(_fixture("item-health-row/published.json"))

    assert all(row.visual_id is None for row in queue.rows)
    assert attempt.visual_id is None
    assert health.visual_id is None
