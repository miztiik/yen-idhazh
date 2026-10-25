"""Source-backed compilation for the position-and-length story charts."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.element import ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualPlan, VisualType
from idhazh.contracts.visual_data import VisualData
from idhazh.render.chart import compile_chart

PLAN: Final = FIXTURES_DIR / "visual-validator" / "plans" / "passes.json"
WIND: Final = FIXTURES_DIR / "visual-validator" / "tables" / "wind.json"
SLOPE: Final = FIXTURES_DIR / "visual-validator" / "tables" / "wind-slope.json"
DOT_OUTPUT: Final = FIXTURES_DIR / "contracts" / "visual-data" / "dot-from-wind.json"
SLOPE_OUTPUT: Final = FIXTURES_DIR / "contracts" / "visual-data" / "slope-from-wind.json"


def _visuals() -> VisualsConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals


def _quantities(table: ElementTable, plan: VisualPlan) -> list[Decimal]:
    by_id = {element.element_id: element for element in table.elements}
    return [Decimal(str(by_id[element_id].value)) for element_id in plan.encodings.quantity]


def test_dot_compilation_keeps_the_source_order_and_each_stated_measure() -> None:
    table = ElementTable.read(WIND)
    base = VisualPlan.read(PLAN)
    plan = VisualPlan.model_validate(
        base.model_dump(mode="json")
        | {
            "type": VisualType.DOT.value,
            "caption": "Dots place each country's figure on one shared scale.",
        }
    )

    visuals = _visuals()
    compiled = compile_chart(plan, table, visuals=visuals)

    assert compiled.data == VisualData.model_validate_json(read_text(DOT_OUTPUT))
    by_id = {mark.mark_id: mark for mark in compiled.data.marks}
    source = {element.element_id: element for element in table.elements}
    categories = compiled.data.encoding.category
    quantities = compiled.data.encoding.quantity
    assert compiled.data.type is VisualType.DOT
    assert visuals.min_chart_points <= len(quantities) <= visuals.max_chart_points
    assert [by_id[mark_id].text for mark_id in categories] == [
        source[element_id].span_excerpt
        for element_id in plan.encodings.category
    ]
    assert [Decimal(by_id[mark_id].value or "0") for mark_id in quantities] == _quantities(table, plan)
    assert compiled.data.emphasized_mark_id == quantities[1]
    assert "Dot chart." in compiled.alt_text


def test_slope_compilation_pairs_two_source_values_for_each_named_entity() -> None:
    table = ElementTable.read(SLOPE)
    base = VisualPlan.read(PLAN).model_dump(mode="json")
    quantities = [
        "quantity-12-19",
        "quantity-32-39",
        "quantity-61-68",
        "quantity-81-88",
    ]
    times = ["date-23-27", "date-43-47"]
    entities = ["entity-0-7", "entity-49-56"]
    ids = [*times, *entities, *quantities]
    plan = VisualPlan.model_validate(
        base
        | {
            "purpose": "change",
            "type": VisualType.SLOPE.value,
            "caption": "Each line joins a country's figures across two years.",
            "element_ids": ids,
            "labels": [*times, *entities],
            "annotations": [quantities[1]],
            "encodings": {
                "category": [],
                "quantity": quantities,
                "quantity_x": [],
                "time": times,
                "series": [],
                "size": [],
                "bins": [],
                "entity": entities,
                "event_label": [],
            },
        }
    )

    visuals = _visuals()
    compiled = compile_chart(plan, table, visuals=visuals)

    assert compiled.data == VisualData.model_validate_json(read_text(SLOPE_OUTPUT))
    by_id = {mark.mark_id: mark for mark in compiled.data.marks}
    assert compiled.data.type is VisualType.SLOPE
    assert visuals.min_chart_points <= len(compiled.data.encoding.quantity) <= visuals.max_chart_points
    assert len(compiled.data.encoding.quantity) % 2 == 0
    assert [by_id[mark_id].text for mark_id in compiled.data.encoding.time] == ["2024", "2025"]
    assert [by_id[mark_id].text for mark_id in compiled.data.encoding.entity] == ["Denmark", "Germany"]
    assert [Decimal(by_id[mark_id].value or "0") for mark_id in compiled.data.encoding.quantity] == [
        Decimal("1200"),
        Decimal("1500"),
        Decimal("2800"),
        Decimal("3400"),
    ]
    assert compiled.data.emphasized_mark_id == compiled.data.encoding.quantity[1]
    assert "Slope chart." in compiled.alt_text
