"""Source-backed visual labels fit without changing their source wording."""

from __future__ import annotations

from typing import Final

import pytest
from pydantic import TypeAdapter, ValidationError
from support.paths import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.element import ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualPlan
from idhazh.render.chart import CompileError, compile_chart
from idhazh.text_fit import fit_source_span

pytestmark = pytest.mark.visual

ARTICLE_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "articles"
PLAN_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "plans"
TABLE_FIXTURES: Final = FIXTURES_DIR / "visual-validator" / "tables"
TEXT_FIT_PLAN: Final = PLAN_FIXTURES / "text-fit.json"
TEXT_FIT_TABLE: Final = TABLE_FIXTURES / "text-fit.json"
COLLISION_ARTICLE: Final = ARTICLE_FIXTURES / "text-fit-collision.txt"
COLLISION_BAR_PLAN: Final = PLAN_FIXTURES / "text-fit-collision-bar.json"
COLLISION_LINE_PLAN: Final = PLAN_FIXTURES / "text-fit-collision-line.json"
COLLISION_TABLE: Final = TABLE_FIXTURES / "text-fit-collision.json"
STACKED_PLAN: Final = PLAN_FIXTURES / "stacked-valid.json"
STACKED_TABLE: Final = TABLE_FIXTURES / "stacked-whole.json"


def committed_visuals() -> VisualsConfig:
    return AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json")).visuals


def visuals_with_label_limit(max_characters: int) -> VisualsConfig:
    values = committed_visuals().model_dump(mode="json")
    return VisualsConfig.model_validate(values | {"max_label_characters": max_characters})


def test_source_span_fitting_is_exact_and_includes_its_suffix_in_the_limit() -> None:
    assert fit_source_span("Canada", max_characters=6) == "Canada"
    assert fit_source_span("abcdef", max_characters=4) == "a..."
    with pytest.raises(ValueError, match="one source character"):
        fit_source_span("abcdef", max_characters=3)


def test_label_limit_is_configured_and_leaves_room_for_the_suffix() -> None:
    assert VisualsConfig().max_label_characters == 40
    with pytest.raises(ValidationError):
        VisualsConfig(max_label_characters=3)


def test_chart_labels_are_deterministic_source_prefixes_at_the_configured_limit() -> None:
    plan = VisualPlan.read(TEXT_FIT_PLAN)
    table = ElementTable.read(TEXT_FIT_TABLE)
    source_by_id = {element.element_id: element.span_excerpt for element in table.elements}
    default_limit = committed_visuals().max_label_characters

    for limit in (12, default_limit, 500):
        visuals = visuals_with_label_limit(limit)
        first = compile_chart(plan, table, visuals=visuals)
        second = compile_chart(plan, table, visuals=visuals)
        assert first == second

        marks = {mark.element_id: mark for mark in first.data.marks if mark.element_id is not None}
        for element_id in plan.encodings.category:
            source_span = source_by_id[element_id]
            displayed = marks[element_id].text
            assert displayed is not None
            assert displayed == fit_source_span(source_span, max_characters=limit)
            assert len(displayed) <= limit
            if len(source_span) > limit:
                assert displayed.endswith("...")
                assert source_span.startswith(displayed.removesuffix("..."))
            else:
                assert displayed == source_span
            if limit == default_limit:
                assert displayed in first.alt_text


def test_source_span_limit_remains_500_characters() -> None:
    source_span = ElementTable.read(TEXT_FIT_TABLE).elements[0].span_excerpt
    source_line = TypeAdapter(UntrustedLine)
    assert len(source_span) == 500
    assert source_line.validate_python(source_span) == source_span
    with pytest.raises(ValidationError):
        source_line.validate_python(f"{source_span}x")


def test_distinct_labels_that_shorten_to_the_same_text_refuse_the_chart() -> None:
    article = read_text(COLLISION_ARTICLE).replace("\r\n", "\n")
    table = ElementTable.read(COLLISION_TABLE)
    assert table.span_drift(article) is None
    assert table.source_text_length == len(article)

    source_labels = {
        element.span_excerpt for element in table.elements if element.kind is ElementKind.PLACE
    }
    assert len(source_labels) == 2
    assert {
        fit_source_span(label, max_characters=committed_visuals().max_label_characters)
        for label in source_labels
    } == {"Northern Atlantic offshore developmen..."}

    for plan_path, role in (
        (COLLISION_BAR_PLAN, "category"),
        (COLLISION_LINE_PLAN, "series"),
    ):
        with pytest.raises(
            CompileError,
            match=f"different source labels in {role} become identical after shortening",
        ):
            compile_chart(
                VisualPlan.read(plan_path),
                table,
                visuals=committed_visuals(),
            )


def test_stacked_bar_labels_remain_uncapped() -> None:
    plan = VisualPlan.read(STACKED_PLAN)
    table = ElementTable.read(STACKED_TABLE)
    compiled = compile_chart(plan, table, visuals=visuals_with_label_limit(4))
    marks = {
        mark.element_id: mark.text for mark in compiled.data.marks if mark.element_id is not None
    }
    source_by_id = {element.element_id: element.span_excerpt for element in table.elements}

    for element_id in [*plan.encodings.category, *plan.encodings.series]:
        assert marks[element_id] == source_by_id[element_id]
        assert source_by_id[element_id] in compiled.alt_text
