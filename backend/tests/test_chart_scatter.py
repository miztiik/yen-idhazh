"""Do scatter points preserve both source measures for exactly the named entities?"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.element import ElementTable
from idhazh.contracts.visual import VisualPlan
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import VisualDecision, VisualKind
from idhazh.render import render_planned_visual
from idhazh.render.chart import CompileError, compile_chart
from idhazh.visual_validator import validate_plan

pytestmark = pytest.mark.visual


def _inputs() -> tuple[VisualPlan, ElementTable]:
    return (
        VisualPlan.read(FIXTURES_DIR / "visual-validator/plans/scatter-relationship.json"),
        ElementTable.read(FIXTURES_DIR / "visual-validator/tables/scatter-relationship.json"),
    )


def test_scatter_compiles_every_entity_with_both_source_measures() -> None:
    plan, table = _inputs()
    visuals = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals
    assert validate_plan(plan, table, visuals=visuals) == []
    chart = compile_chart(plan, table, visuals=visuals)
    assert chart.data == VisualData.read(
        FIXTURES_DIR / "contracts/visual-data/scatter-relationship.json"
    )
    source_text = read_text(FIXTURES_DIR / "visual-validator/articles/scatter-relationship.txt")
    assert table.span_drift(source_text) is None
    source = {element.element_id: element for element in table.elements}
    marks = {mark.mark_id: mark for mark in chart.data.marks}
    encoding = chart.data.encoding
    assert visuals.min_chart_points <= len(encoding.entity) <= visuals.max_chart_points
    for entity_id, x_id, y_id in zip(
        encoding.entity, encoding.quantity_x, encoding.quantity, strict=True
    ):
        entity, x, y = (marks[mark_id] for mark_id in (entity_id, x_id, y_id))
        assert entity.element_id is not None
        assert x.element_id is not None
        assert y.element_id is not None
        assert source[x.element_id].entity == source[y.element_id].entity
        assert source[x.element_id].entity == source[entity.element_id].entity
        for measured in (x, y):
            assert measured.element_id is not None
            element = source[measured.element_id]
            assert element.span_excerpt == source_text[element.span_start:element.span_end]
            assert Decimal(measured.value or "") == Decimal(element.value or "")
    assert chart.evidence.displayed_values == 2 * len(encoding.entity)
    assert "Scatter chart." in chart.alt_text


@pytest.mark.parametrize("change", [
    "wrong-purpose", "partial-pair", "different-entities", "reordered-measures",
    "missing-link", "duplicate-entity", "same-measure",
])
def test_scatter_refuses_incomplete_or_ambiguous_entity_pairs(
    change: str, tmp_path: Path
) -> None:
    plan, table = _inputs()
    raw = plan.model_dump(mode="json")
    elements = table.model_dump(mode="json")
    if change == "wrong-purpose":
        raw["purpose"] = "comparison"
    elif change == "partial-pair":
        raw["encodings"]["quantity_x"].pop()
    elif change == "reordered-measures":
        raw["encodings"]["quantity_x"].reverse()
    elif change == "same-measure":
        raw["encodings"]["quantity_x"] = raw["encodings"]["quantity"]
    else:
        target = (
            raw["encodings"]["entity"][0]
            if change == "duplicate-entity" else raw["encodings"]["quantity_x"][0]
        )
        for element in elements["elements"]:
            if element["element_id"] == target:
                element["entity"] = None if change == "missing-link" else "germany"
                if change == "missing-link":
                    element["label_source"] = None
                    element["ledger_version"] = None
    plan = VisualPlan.model_validate(raw)
    table = ElementTable.model_validate(elements)
    visuals = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals
    rejections = validate_plan(plan, table, visuals=visuals)
    assert any(reason.check.value == "roles_valid_for_type" for reason in rejections)
    with pytest.raises(CompileError):
        compile_chart(plan, table, visuals=visuals)
    # The real publication boundary must not turn refusal into a partial chart.
    decision = VisualDecision(
        version=VisualDecision.schema_version(), item_id=table.item_id, url_key=table.url_key,
        kind=VisualKind.NONE, spec=None, alt_text=None,
        model_id="recorded-fixture", decided_at="2026-10-26T04:00:00Z",
    )
    result = render_planned_visual(
        decision, plan, table, visuals=visuals, public_root=tmp_path,
        relpath=f"digest/2026/10/26/{table.item_id}.json",
    )
    assert result.spec is None
    assert result.data_path is None
    assert result.rationale
    assert not (tmp_path / f"digest/2026/10/26/{table.item_id}.json").exists()


def test_scatter_fixture_has_relationship_purpose_and_no_coordinates() -> None:
    plan, _ = _inputs()
    assert plan.purpose is not None and plan.purpose.value == "relationship"
    data = json.loads(read_text(FIXTURES_DIR / "contracts/visual-data/scatter-relationship.json"))
    assert all("cx" not in mark and "cy" not in mark for mark in data["marks"])
