"""Does a census column whose values come from a fixed set refuse a value outside it?"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SCHEMAS_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.item_health import ItemHealthRow, TimeSource
from idhazh.contracts.run_plan import PlannedItem

pytestmark = pytest.mark.contract


def published_payload(**cells: Any) -> dict[str, Any]:
    """One real census row as a payload, read inside the test that needs it."""
    payload = json.loads(read_text(CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json"))
    return {**payload, **cells}


def test_the_column_holds_the_member_and_not_a_spelling_of_it() -> None:
    """A producer selects from the set. It does not type a word that looks like one."""
    row = ItemHealthRow.model_validate(published_payload(time_source="first_seen"))

    assert row.time_source is TimeSource.FIRST_SEEN
    assert row.csv_row()["time_source"] == "first_seen"
    assert ItemHealthRow.from_csv_row(row.csv_row()).time_source is TimeSource.FIRST_SEEN


def test_a_clock_nobody_declared_is_refused_and_not_folded() -> None:
    """The refusal is the whole change, so it is the assertion.

    `wall_clock` is a well-formed lowercase token, so the column this census row
    used to carry would have taken it, written it to the ledger, and left every
    reader of that ledger to guess what it meant. Two producers could disagree
    about the name of one clock and nothing would say so.
    """
    assert "wall_clock".islower(), "the refused value is a legal token, which is the point"

    with pytest.raises(ValidationError, match="time_source"):
        ItemHealthRow.model_validate(published_payload(time_source="wall_clock"))

    row = ItemHealthRow.model_validate(published_payload())
    with pytest.raises(ValidationError, match="time_source"):
        ItemHealthRow.from_csv_row({**row.csv_row(), "time_source": "wall_clock"})


def test_the_generated_schema_carries_every_member() -> None:
    """The schema is what a reader outside Python validates against (Guardrail #3)."""
    schema = json.loads(read_text(SCHEMAS_DIR / "item-health-row.schema.json"))

    assert schema["$defs"]["TimeSource"]["enum"] == [member.value for member in TimeSource]


def test_a_row_written_before_the_column_was_filled_still_reads() -> None:
    """Section 11's release blocker: an empty cell is absence, not a bad member."""
    cells = ItemHealthRow.model_validate(published_payload()).csv_row()

    assert cells["time_source"] == ""
    assert ItemHealthRow.from_csv_row(cells).time_source is None


def test_the_plan_and_the_census_name_one_vocabulary() -> None:
    """Two declarations of one set is the drift this column exists to close.

    The plan labels the clock and the census row persists the label. A second
    `TimeSource` declared beside the plan would let the two disagree while both
    sides still type-check, so the assertion is that one class types both.
    """
    assert (
        PlannedItem.model_fields["time_source"].annotation
        == ItemHealthRow.model_fields["time_source"].annotation
    )
    assert TimeSource.FEED.names_a_clock
    assert not TimeSource.UNKNOWN.names_a_clock
