"""The independent, versioned contract for source-backed actor/claim grids."""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text

from idhazh.contracts.article import UNTRUSTED_LINE_MAX
from idhazh.contracts.visual import MAX_IDS_PER_ROLE
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.whowhat_grid import (
    MAX_WHOWHAT_ROWS,
    WhowhatClaimSpan,
    WhowhatEntitySpan,
    WhowhatGridData,
    WhowhatGridRow,
    WhowhatSourceSpan,
)

pytestmark = pytest.mark.contract

GRID_FIXTURE = CONTRACT_FIXTURES_DIR / "whowhat-grid" / "whowhat.json"
ARTICLE_FIXTURE = FIXTURES_DIR / "visual-validator" / "articles" / "whowhat.txt"


def test_the_grid_fixture_round_trips_and_both_cells_reslice_from_the_article() -> None:
    grid = WhowhatGridData.read(GRID_FIXTURE)
    article = read_text(ARTICLE_FIXTURE).rstrip("\n")

    assert grid.version == WhowhatGridData.schema_version()
    assert len(grid.rows) <= MAX_WHOWHAT_ROWS
    assert any(row.actor is None and row.claim is None for row in grid.rows)
    for row in grid.rows:
        assert (row.actor is None) == (row.claim is None)
        if row.actor is None or row.claim is None:
            continue
        assert row.actor.sentence_index == row.claim.sentence_index
        assert article[row.actor.span_start : row.actor.span_end] == row.actor.span_excerpt
        assert article[row.claim.span_start : row.claim.span_end] == row.claim.span_excerpt

    assert WhowhatGridData.from_json(grid.to_json()) == grid


def test_grid_cells_must_be_both_populated_or_both_empty() -> None:
    payload = json.loads(read_text(GRID_FIXTURE))
    payload["rows"][0]["claim"] = None

    with pytest.raises(ValidationError, match="both cells or leaves both empty"):
        WhowhatGridData.model_validate(payload)

    payload = json.loads(read_text(GRID_FIXTURE))
    payload["rows"][0].pop("claim")
    with pytest.raises(ValidationError, match="claim"):
        WhowhatGridData.model_validate(payload)


@pytest.mark.parametrize("cell", ["actor", "claim"])
def test_display_text_is_the_source_span_or_its_exact_prefix(cell: str) -> None:
    payload = json.loads(read_text(GRID_FIXTURE))
    payload["rows"][0][cell]["display_text"] = "invented text..."

    with pytest.raises(ValidationError, match="source prefix"):
        WhowhatGridData.model_validate(payload)


def test_a_populated_pair_must_come_from_the_same_sentence() -> None:
    payload = json.loads(read_text(GRID_FIXTURE))
    payload["rows"][0]["claim"]["sentence_index"] += 1

    with pytest.raises(ValidationError, match="same sentence"):
        WhowhatGridData.model_validate(payload)


def test_a_grid_needs_a_pair_and_stays_inside_both_structural_bounds() -> None:
    payload = json.loads(read_text(GRID_FIXTURE))
    for row in payload["rows"]:
        row["actor"] = None
        row["claim"] = None
    with pytest.raises(ValidationError, match="at least one paired source row"):
        WhowhatGridData.model_validate(payload)

    payload = json.loads(read_text(GRID_FIXTURE))
    payload["rows"].extend([{"actor": None, "claim": None}] * (MAX_WHOWHAT_ROWS + 1 - len(payload["rows"])))
    with pytest.raises(ValidationError, match="at most"):
        WhowhatGridData.model_validate(payload)

    payload = json.loads(read_text(GRID_FIXTURE))
    actor = payload["rows"][0]["actor"]
    actor.update(
        element_id="entity-0-501",
        span_end=501,
        span_excerpt="x" * 501,
    )
    with pytest.raises(ValidationError, match="String should have at most 500 characters"):
        WhowhatGridData.model_validate(payload)


def test_the_grid_has_its_own_contract_and_does_not_change_chart_data() -> None:
    assert WhowhatGridData.__schema_stem__ == "whowhat-grid"
    assert WhowhatGridData.schema_filename() != VisualData.schema_filename()
    assert WhowhatGridData.schema_version() == "2026-10-28"


def test_grid_row_bound_matches_the_plan_role_bound() -> None:
    assert MAX_WHOWHAT_ROWS == MAX_IDS_PER_ROLE


def test_the_browser_reader_constants_stay_bound_to_the_python_contract() -> None:
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "whowhat-grid.ts")
    expected = {
        "WHOWHAT_GRID_VERSION": WhowhatGridData.schema_version(),
        "WHOWHAT_GRID_MAX_ROWS": str(MAX_WHOWHAT_ROWS),
        "WHOWHAT_SOURCE_SPAN_MAX": str(UNTRUSTED_LINE_MAX),
    }

    for name, value in expected.items():
        match = re.search(rf"export const {name} = ([^;]+);", source)
        assert match, f"{name} is missing from the browser reader"
        assert match.group(1).strip("'\"") == value, name


def test_the_browser_payload_types_keep_the_python_contract_field_sets() -> None:
    source = read_text(REPO_ROOT / "frontend" / "src" / "lib" / "payload" / "types.ts")

    def declared_fields(name: str) -> set[str]:
        match = re.search(
            rf"export interface {name}(?:\s+extends\s+[^\{{]+)?\s*\{{(.*?)\n\}}",
            source,
            re.DOTALL,
        )
        assert match, f"{name} is missing from the browser payload types"
        return set(re.findall(r"^\s*(\w+)\??\s*:", match.group(1), re.MULTILINE))

    source_fields = declared_fields("WhowhatSourceSpan")
    assert source_fields == set(WhowhatSourceSpan.model_fields)
    assert source_fields | declared_fields("WhowhatEntitySpan") == set(
        WhowhatEntitySpan.model_fields
    )
    assert source_fields | declared_fields("WhowhatClaimSpan") == set(
        WhowhatClaimSpan.model_fields
    )
    assert declared_fields("WhowhatGridRow") == set(WhowhatGridRow.model_fields)
    assert declared_fields("WhowhatGridData") == set(WhowhatGridData.model_fields)
