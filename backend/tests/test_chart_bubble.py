"""Does every bubble keep three source measures attached to its entity?"""

from __future__ import annotations

from decimal import Decimal

import pytest
from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.element import ElementTable
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_data import VisualData
from idhazh.render.chart import CompileError, can_compile, compile_chart
from idhazh.visual_validator import validate_plan

pytestmark = pytest.mark.visual


def _inputs() -> tuple[VisualPlan, ElementTable]:
    return (
        VisualPlan.read(FIXTURES_DIR / "visual-validator/plans/bubble-relationship.json"),
        ElementTable.read(FIXTURES_DIR / "visual-validator/tables/scatter-relationship.json"),
    )


def test_bubble_compiles_three_source_measures_for_each_entity() -> None:
    plan, table = _inputs()
    visuals = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals
    assert can_compile(VisualType.BUBBLE)
    assert validate_plan(plan, table, visuals=visuals) == []
    chart = compile_chart(plan, table, visuals=visuals)
    assert chart.data == VisualData.read(
        FIXTURES_DIR / "contracts/visual-data/bubble-relationship.json"
    )

    source_text = read_text(FIXTURES_DIR / "visual-validator/articles/scatter-relationship.txt")
    assert table.span_drift(source_text) is None
    source = {element.element_id: element for element in table.elements}
    marks = {mark.mark_id: mark for mark in chart.data.marks}
    encoding = chart.data.encoding
    assert len(encoding.entity) == 4
    for entity_id, x_id, y_id, size_id in zip(
        encoding.entity,
        encoding.quantity_x,
        encoding.quantity,
        encoding.size,
        strict=True,
    ):
        entity, x, y, size = (marks[mark_id] for mark_id in (entity_id, x_id, y_id, size_id))
        assert entity.element_id is not None
        assert x.element_id is not None
        assert y.element_id is not None
        assert size.element_id is not None
        entity_name = source[entity.element_id].entity
        assert {source[mark.element_id].entity for mark in (x, y, size)} == {entity_name}
        for measured in (x, y, size):
            element = source[measured.element_id]
            assert source_text[element.span_start:element.span_end] == element.span_excerpt
            assert Decimal(measured.value or "") == Decimal(element.value or "")
        assert Decimal(size.value or "") > 0
    assert chart.evidence.displayed_values == 3 * len(encoding.entity)
    assert "Bubble chart." in chart.alt_text
    assert "area 14 turbine" in chart.alt_text


@pytest.mark.parametrize(
    "change", ["wrong-purpose", "missing-size", "mismatched-entity", "reused-measure", "zero-size"]
)
def test_bubble_refuses_missing_or_ambiguous_relationship_measures(
    change: str,
) -> None:
    plan, table = _inputs()
    raw_plan = plan.model_dump(mode="json")
    raw_table = table.model_dump(mode="json")
    if change == "wrong-purpose":
        raw_plan["purpose"] = "comparison"
    elif change == "missing-size":
        raw_plan["encodings"]["size"].pop()
    elif change == "reused-measure":
        raw_plan["encodings"]["size"][0] = raw_plan["encodings"]["quantity_x"][0]
    else:
        target = raw_plan["encodings"]["size"][0]
        for element in raw_table["elements"]:
            if element["element_id"] == target:
                element["value"] = "0" if change == "zero-size" else element["value"]
                if change == "mismatched-entity":
                    element["entity"] = "germany"
    plan = VisualPlan.model_validate(raw_plan)
    table = ElementTable.model_validate(raw_table)
    visuals = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals

    rejections = validate_plan(plan, table, visuals=visuals)
    assert any(reason.check.value == "roles_valid_for_type" for reason in rejections)
    with pytest.raises(CompileError):
        compile_chart(plan, table, visuals=visuals)
