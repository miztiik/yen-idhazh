"""Does a feed retirement keep its cause and distinct evidence through a ledger round trip?"""

from __future__ import annotations

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause

pytestmark = pytest.mark.contract


def test_a_retirement_names_distinct_runs_and_matches_its_cause() -> None:
    """Five failures inside one run is one run's evidence, not five runs' worth."""
    assert [cause.value for cause in RetirementCause] == ["http_410", "low_yield"]

    row = FeedRetirementRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-retirement-row" / "gone.json")
    )
    repeated = row.model_dump(mode="json") | {"evidence_run_ids": ["2026-08-23-1"] * 5}

    with pytest.raises(ValidationError, match="distinct runs"):
        FeedRetirementRow.model_validate(repeated)

    crossed = row.model_dump(mode="json") | {"cause": "low_yield"}
    with pytest.raises(ValidationError, match="stayed under the mark"):
        FeedRetirementRow.model_validate(crossed)

    bare = row.model_dump(mode="json") | {"evidence_run_ids": []}
    with pytest.raises(ValidationError, match="read the 410"):
        FeedRetirementRow.model_validate(bare)


def test_a_retirement_row_survives_the_ledger_round_trip() -> None:
    """The evidence list is one cell, so the header cannot grow with the evidence."""
    row = FeedRetirementRow.from_json(
        read_text(CONTRACT_FIXTURES_DIR / "feed-retirement-row" / "gone.json")
    )
    cells = row.csv_row()

    assert cells["evidence_run_ids"].count(" ") == len(row.evidence_run_ids) - 1
    assert "," not in cells["evidence_run_ids"], "a comma would need quoting in a union merge"
    assert FeedRetirementRow.from_csv_row(cells) == row
