"""Do requested and delivered visual types remain distinct through old and new payloads?"""

from __future__ import annotations

import json
from typing import Any, cast

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.contracts.visual_telemetry import ValidatorCheck

pytestmark = [pytest.mark.contract, pytest.mark.visual]

FIELDS = ("planned_type", "rendered_type", "downgrade_depth", "marks")
MODELS = (VisualDecision, ItemHealthRow)


def payload(model: type[VisualDecision] | type[ItemHealthRow]) -> dict[str, Any]:
    fixture = (
        "visual-decision/chart-rendered.json"
        if model is VisualDecision
        else "item-health-row/published.json"
    )
    return cast(dict[str, Any], json.loads(read_text(CONTRACT_FIXTURES_DIR / fixture)))


@pytest.mark.parametrize("model", MODELS)
def test_older_payloads_remain_unmeasured_without_inferred_types(
    model: type[VisualDecision] | type[ItemHealthRow],
) -> None:
    original = {name: value for name, value in payload(model).items() if name not in FIELDS}
    old = model.model_validate(original)
    assert all(getattr(old, name) is None for name in FIELDS)
    if isinstance(old, VisualDecision):
        assert old.deepest_downgrade_depth is None
        assert old.rejection_reason is None
        assert old.gate_floor_applied is None


def test_decision_evidence_round_trips_without_conflating_selected_and_reached_depth() -> None:
    document = json.loads(
        read_text(CONTRACT_FIXTURES_DIR / "visual-decision/none.json")
    ) | {
        "asked_the_model": True,
        "none_reason": "validation_failed",
        "drafted_chart": True,
        "planned_type": "pie",
        "downgrade_depth": 0,
        "deepest_downgrade_depth": 2,
        "rejection_reason": "pie_exhaustive",
        "gate_floor_applied": True,
    }

    decision = VisualDecision.model_validate(document)

    assert decision.downgrade_depth == 0
    assert decision.deepest_downgrade_depth == 2
    assert decision.rejection_reason is ValidatorCheck.PIE_EXHAUSTIVE
    assert decision.gate_floor_applied is True
    assert VisualDecision.from_json(decision.to_json()) == decision


@pytest.mark.parametrize(
    "changed",
    [
        {"deepest_downgrade_depth": 0},
        {"rejection_reason": "pie_exhaustive"},
        {"gate_floor_applied": False},
        {
            "planned_type": "bar",
            "downgrade_depth": 0,
            "deepest_downgrade_depth": 0,
            "gate_floor_applied": False,
        },
    ],
)
def test_decision_evidence_requires_a_typed_request_and_reached_rung(
    changed: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        VisualDecision.model_validate(payload(VisualDecision) | changed)


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize(
    ("planned", "rendered", "depth"),
    [("bar", "bar", 0), ("dot", "bar", 1)],
)
def test_a_delivery_records_the_request_separately_from_the_compiled_type(
    model: type[VisualDecision] | type[ItemHealthRow],
    planned: str,
    rendered: str,
    depth: int,
) -> None:
    document = payload(model) | {
        "planned_type": planned,
        "rendered_type": rendered,
        "downgrade_depth": depth,
        "marks": 4,
    }
    measured = model.model_validate(document)
    assert measured.planned_type == planned
    assert measured.rendered_type == rendered
    assert measured.downgrade_depth == depth
    assert measured.marks == 4
    assert model.from_json(measured.to_json()) == measured


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize(
    "changed",
    [
        {"planned_type": None},
        {"downgrade_depth": None},
        {"rendered_type": "bar", "marks": None},
        {"rendered_type": None, "marks": 4},
        {"planned_type": "bar", "rendered_type": "bar", "downgrade_depth": 1},
        {"planned_type": "dot", "rendered_type": "bar", "downgrade_depth": 0},
        {"marks": 0},
        {"downgrade_depth": -1},
    ],
)
def test_partial_or_contradictory_outcomes_are_refused(
    model: type[VisualDecision] | type[ItemHealthRow], changed: dict[str, Any],
) -> None:
    document = payload(model) | {
        "planned_type": "dot", "rendered_type": "bar", "downgrade_depth": 1, "marks": 4,
    }
    with pytest.raises(ValidationError):
        model.model_validate(document | changed)


def test_a_refusal_preserves_the_known_request_and_selected_depth() -> None:
    document = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision/none.json"))
    refused = VisualDecision.model_validate(
        document | {"planned_type": "dot", "downgrade_depth": 1}
    )
    assert refused.planned_type is VisualType.DOT
    assert refused.downgrade_depth == 1
    assert refused.rendered_type is None
    assert refused.marks is None


def test_an_unwritten_visual_cannot_claim_a_delivered_type() -> None:
    document = json.loads(read_text(CONTRACT_FIXTURES_DIR / "visual-decision/none.json"))
    with pytest.raises(ValidationError, match="rendered"):
        VisualDecision.model_validate(document | {
            "planned_type": "bar", "rendered_type": "bar", "downgrade_depth": 0, "marks": 4,
        })


def test_all_native_names_remain_selectable_with_both_policies_off_by_default() -> None:
    knobs = VisualsConfig()
    assert knobs.enabled_types == list(VisualType)
    assert not knobs.type_selection_enabled
    assert not knobs.downgrade_enabled
    for visual_type in VisualType:
        selected = VisualsConfig(enabled_types=[visual_type])
        assert selected.enabled_types == [visual_type]


@pytest.mark.parametrize("types", [[], ["bar", "bar"], ["not-a-visual-type"]])
def test_type_selection_refuses_empty_repeated_or_unknown_names(types: list[str]) -> None:
    with pytest.raises(ValidationError):
        VisualsConfig.model_validate({"enabled_types": types})


def test_enabled_rescue_requires_rungs_and_positive_population_bounds() -> None:
    for changed in (
        {"downgrade_enabled": True, "downgrade_floor_percentiles": []},
        {"downgrade_lookback_days": 0},
        {"downgrade_max_samples_per_type": 0},
    ):
        with pytest.raises(ValidationError):
            VisualsConfig.model_validate(changed)
