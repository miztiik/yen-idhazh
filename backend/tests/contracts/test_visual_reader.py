"""Does the chart reader copy the current native shape and reject old framing?"""
from __future__ import annotations

import re

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts.appearance_config import StoryChartGeometryConfig
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.contracts.visual_data import (
    RENDERER_VERSION,
    VisualData,
    VisualEncoding,
    VisualMark,
)
from idhazh.render.chart import DISPLAY_UNIT_SYMBOLS, can_compile
from idhazh.visual_vocabulary import UNIT_DIMENSIONS

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("model", [VisualData, VisualMark, VisualEncoding])
def test_frontend_chart_fields_match_the_native_contract(
    model: type[VisualData] | type[VisualMark] | type[VisualEncoding],
) -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/payload/types.ts")
    found = re.search(rf"export interface {model.__name__} \{{(.*?)\n\}}", source, re.S)
    assert found is not None
    fields = set(re.findall(r"^\t(\w+):", found[1], re.M))
    assert fields == set(model.model_fields)


def test_frontend_story_chart_geometry_matches_its_native_contract() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/server/config.ts")
    found = re.search(r"export interface StoryChartGeometryConfig \{(.*?)\n\}", source, re.S)
    assert found is not None
    fields = set(re.findall(r"^\t(\w+):", found[1], re.M))
    assert fields == set(StoryChartGeometryConfig.model_fields)


def test_frontend_chart_vocabularies_match_the_native_contract() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/payload/drawing.ts")
    assert f"export const RENDERER_VERSION = '{RENDERER_VERSION}';" in source
    for name, expected in (
        ("ENCODING_ROLES", [role.value for role in EncodingRole]),
        ("DRAWABLE", [visual_type.value for visual_type in VisualType if can_compile(visual_type)]),
    ):
        found = re.search(rf"export const {name} = \[(.*?)\] as const;", source, re.S)
        assert found is not None
        assert re.findall(r"'([^']*)'", found[1]) == expected


def test_frontend_stacked_unit_symbols_match_the_native_renderer() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/visual/bar.ts")
    found = re.search(r"const DISPLAY_UNIT_SYMBOLS\b[^=]*= \{(.*?)\n\};", source, re.S)
    assert found is not None
    symbols = dict(re.findall(r"^\s*(\w+): '([^']*)',?$", found[1], re.M))
    assert symbols == DISPLAY_UNIT_SYMBOLS
    assert set(symbols) == set(UNIT_DIMENSIONS)


@pytest.mark.parametrize("change", ["old-renderer", "missing-emphasis", "category-emphasis"])
def test_incompatible_chart_data_is_refused_without_migration(change: str) -> None:
    data = VisualData.read(
        CONTRACT_FIXTURES_DIR / "visual-data/bars-from-the-committed-plan.json"
    ).model_dump(mode="json")
    if change == "old-renderer":
        data["renderer_version"] = "2026-09-13"
    elif change == "missing-emphasis":
        del data["emphasized_mark_id"]
    else:
        data["emphasized_mark_id"] = data["encoding"]["category"][0]
    with pytest.raises(ValidationError):
        VisualData.model_validate(data)


def test_slope_reader_rejects_repeated_time_labels() -> None:
    data = VisualData.model_validate_json(
        read_text(CONTRACT_FIXTURES_DIR / "visual-data/slope-from-wind.json")
    ).model_dump(mode="json")
    data["marks"][5]["text"] = data["marks"][4]["text"]
    with pytest.raises(ValidationError, match="two distinct time labels"):
        VisualData.model_validate(data)


def test_slope_reader_rejects_duplicate_series_names_without_entities() -> None:
    data = VisualData.model_validate_json(
        read_text(CONTRACT_FIXTURES_DIR / "visual-data/slope-from-wind.json")
    ).model_dump(mode="json")
    data["encoding"]["series"] = data["encoding"]["entity"]
    data["encoding"]["entity"] = []
    data["marks"][7]["text"] = data["marks"][6]["text"]
    with pytest.raises(ValidationError, match="distinct series labels"):
        VisualData.model_validate(data)


@pytest.mark.parametrize("change", ["missing-x", "missing-entity", "duplicate-entity"])
def test_scatter_reader_requires_every_entity_and_both_measures(change: str) -> None:
    data = VisualData.read(
        CONTRACT_FIXTURES_DIR / "visual-data/scatter-relationship.json"
    ).model_dump(mode="json")
    if change == "duplicate-entity":
        held = {mark["mark_id"]: mark for mark in data["marks"]}
        entities = data["encoding"]["entity"]
        held[entities[1]]["element_id"] = held[entities[0]]["element_id"]
    else:
        role = "quantity_x" if change == "missing-x" else "entity"
        dropped = data["encoding"][role].pop()
        data["marks"] = [mark for mark in data["marks"] if mark["mark_id"] != dropped]
    with pytest.raises(ValidationError, match="scatter"):
        VisualData.model_validate(data)


def test_stacked_reader_accepts_the_compiled_whole_and_rejects_a_missing_part_label() -> None:
    data = VisualData.read(
        CONTRACT_FIXTURES_DIR / "visual-data/stacked-bar-from-whole.json"
    )
    assert data.type is VisualType.STACKED_BAR

    payload = data.model_dump(mode="json")
    dropped = payload["encoding"]["series"].pop()
    payload["marks"] = [mark for mark in payload["marks"] if mark["mark_id"] != dropped]
    with pytest.raises(ValidationError, match="one series label per part"):
        VisualData.model_validate(payload)


def test_stacked_reader_requires_a_separate_source_quantity_for_its_whole() -> None:
    data = VisualData.read(
        CONTRACT_FIXTURES_DIR / "visual-data/stacked-bar-from-whole.json"
    ).model_dump(mode="json")
    data["marks"][0]["element_id"] = "entity-22-29"
    with pytest.raises(ValidationError, match="whole label cites a source quantity"):
        VisualData.model_validate(data)

    data = VisualData.read(
        CONTRACT_FIXTURES_DIR / "visual-data/stacked-bar-from-whole.json"
    ).model_dump(mode="json")
    whole_id = data["marks"][0]["element_id"]
    data["marks"][1]["element_id"] = whole_id
    with pytest.raises(ValidationError, match="declared whole is separate from its parts"):
        VisualData.model_validate(data)
