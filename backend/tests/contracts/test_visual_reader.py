"""Does the chart reader copy the current native shape and reject old framing?"""
from __future__ import annotations

import re

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.contracts.visual_data import (
    RENDERER_VERSION,
    VisualData,
    VisualEncoding,
    VisualMark,
)

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


def test_frontend_chart_vocabularies_match_the_native_contract() -> None:
    source = read_text(REPO_ROOT / "frontend/src/lib/payload/drawing.ts")
    assert f"export const RENDERER_VERSION = '{RENDERER_VERSION}';" in source
    for name, expected in (
        ("ENCODING_ROLES", [role.value for role in EncodingRole]),
        ("DRAWABLE", [VisualType.BAR.value]),
    ):
        found = re.search(rf"export const {name} = \[(.*?)\] as const;", source, re.S)
        assert found is not None
        assert re.findall(r"'([^']*)'", found[1]) == expected


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
