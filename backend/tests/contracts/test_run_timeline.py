"""Does the run timeline's shape say what the chart will need, and only that?

The producers do not exist yet, and neither does the chart that draws from them -
so everything here is asked of the shape itself: the eight
steps it names, the two numbers it adds, the subtraction it owns, and the
addresses it refuses to carry.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SCHEMAS_DIR, read_text
from pydantic import ValidationError

from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.run_timeline import STEP_COLUMNS, RunTimelineRow

pytestmark = pytest.mark.contract


#: The eight steps, in the order the pipeline runs them. Written out once here
#: rather than read off the module, because a test that derives the list from the
#: thing it is checking agrees with any list at all.
THE_EIGHT_STEPS: tuple[str, ...] = (
    "plan_ms",
    "fetch_ms",
    "extract_ms",
    "label_ms",
    "summary_ms",
    "visual_plan_ms",
    "score_ms",
    "publish_ms",
)

#: What a published projection may not carry, from the trust-boundary table in
#: `docs/architecture/publishing/console-payloads.md`. One shape serves the
#: committed row and the published mirror only while none of these can appear.
AN_ADDRESS_OR_FETCHED_TEXT: frozenset[str] = frozenset(
    {"canonical_url", "source_url", "url", "url_key", "endpoint_key", "title", "detail"}
)


def _fixture(name: str) -> RunTimelineRow:
    return RunTimelineRow.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-timeline-row" / name))


def _a_row(**cells: Any) -> RunTimelineRow:
    """A row carrying only what the shape requires, plus whatever the case needs."""
    payload: dict[str, Any] = {
        "date": "2026-09-15",
        "run_id": "2026-09-15-34941020965",
        "shard": 1,
        "item_id": "ai-0123456789abcdef",
        "start_offset_ms": 0,
        "item_total_ms": 1_000,
    }
    payload.update(cells)
    return RunTimelineRow.model_validate(payload)


def test_a_row_carrying_every_step_round_trips_byte_identically() -> None:
    """The oracle's first arm: all eight steps, through the shape and back."""
    text = read_text(CONTRACT_FIXTURES_DIR / "run-timeline-row" / "every-step.json")
    row = RunTimelineRow.from_json(text)
    assert row.to_json() == text
    assert all(value is not None for value in row.steps().values())


def test_a_row_that_died_at_fetch_loads_with_the_other_seven_null() -> None:
    """The oracle's second arm: one step filled, seven absent, and it still draws.

    A bar needs a start and a length, and this row has both. Nothing else about
    it is required, which is what lets an item that never reached the model
    appear on the chart beside one that finished.
    """
    row = _fixture("died-at-fetch.json")
    filled = {name for name, value in row.steps().items() if value is not None}
    assert filled == {"fetch_ms"}
    assert row.item_total_ms > 0


def test_the_eight_steps_are_the_eight_the_chart_draws_in_the_order_they_happen() -> None:
    assert STEP_COLUMNS == THE_EIGHT_STEPS
    columns = RunTimelineRow.csv_columns()
    assert [name for name in columns if name in THE_EIGHT_STEPS] == list(THE_EIGHT_STEPS), (
        "the columns are declared out of order, so a reader of the row cannot "
        "read the pipeline's order off it"
    )


def test_every_step_is_optional_and_an_absent_one_is_not_a_zero() -> None:
    row = _a_row()
    assert set(row.steps()) == set(THE_EIGHT_STEPS)
    assert all(value is None for value in row.steps().values())
    assert row.named_total_ms() == 0
    assert row.residual_ms == row.item_total_ms, (
        "a step nothing timed leaves its time in the residual, where a reader can "
        "see there is time nobody accounted for"
    )


def test_the_residual_is_derived_when_the_writer_omits_it() -> None:
    row = _a_row(item_total_ms=1_000, fetch_ms=600, extract_ms=100)
    assert row.residual_ms == 300


def test_a_residual_that_disagrees_with_the_arithmetic_is_refused() -> None:
    """One subtraction, in one place. A second one is what this refuses."""
    with pytest.raises(ValidationError, match="minus the eight named steps"):
        _a_row(item_total_ms=1_000, fetch_ms=600, extract_ms=100, residual_ms=299)


def test_a_residual_that_agrees_is_accepted_so_a_written_row_reads_back() -> None:
    """The refusal above must not make the row unreadable off its own CSV."""
    row = _a_row(item_total_ms=1_000, fetch_ms=600, extract_ms=100, residual_ms=300)
    assert row.residual_ms == 300


def test_the_residual_is_signed_because_the_visual_plan_sits_inside_the_summary_call() -> None:
    """The known overlap, and why clamping to zero would hide it.

    `visual_plan_ms` is apportioned out of `summary_ms` rather than timed beside
    it (`ItemHealthRow.visual_plan_ms`), so adding the eight steps can exceed the
    bar. A negative residual is the only signal that says two steps overlapped.
    """
    row = _a_row(item_total_ms=402_300, summary_ms=402_300, visual_plan_ms=11_700)
    assert row.residual_ms == -11_700


def test_a_step_may_not_be_negative() -> None:
    with pytest.raises(ValidationError):
        _a_row(fetch_ms=-1)


def test_the_two_numbers_this_row_adds_are_the_two_no_ledger_holds() -> None:
    """Six of the eight steps keep a ledger's own spelling; two name untimed steps.

    The point is not that the durations are new - they are not, and re-filing them
    against a clock is what the row is for. It is that exactly two cells here are
    a measurement no committed ledger keeps, so the row adds two numbers rather
    than a second account of eight.
    """
    census = set(ItemHealthRow.csv_columns())
    scores = set(EvalRow.csv_columns())
    already_spelled = census | scores

    assert {"fetch_ms", "extract_ms", "label_ms", "summary_ms", "visual_plan_ms"} <= census
    assert "score_ms" in scores
    assert "item_total_ms" in census, "the bar's length is the census's own number"

    assert not already_spelled & {"start_offset_ms", "residual_ms"}
    assert not already_spelled & {"plan_ms", "publish_ms"}, (
        "a step a ledger already times must keep that ledger's spelling"
    )


def test_the_row_carries_no_address_so_one_shape_serves_the_ledger_and_the_mirror() -> None:
    """Why there is no second `public-run-timeline` contract to declare.

    Every other published projection cuts named cells out of a wider row because
    the wider row carries an address or fetched text. This row carries neither,
    so the committed columns and the published columns are the same columns.
    """
    carried = set(RunTimelineRow.csv_columns())
    assert not carried & AN_ADDRESS_OR_FETCHED_TEXT
    assert AN_ADDRESS_OR_FETCHED_TEXT & set(ItemHealthRow.csv_columns()), (
        "the forbidden list stopped naming anything the census carries, so this "
        "check has stopped proving the projection is narrower than its source"
    )


def test_a_csv_row_round_trips_and_an_absent_step_is_an_empty_cell() -> None:
    row = _fixture("died-at-fetch.json")
    cells = row.csv_row()
    assert set(cells) == set(RunTimelineRow.csv_columns())
    assert cells["plan_ms"] == ""
    assert cells["fetch_ms"] == str(row.fetch_ms)
    assert RunTimelineRow.from_csv_row(cells) == row


def test_the_generated_schema_says_what_the_shape_says() -> None:
    """The artefact a later reader parses against, checked rather than assumed."""
    schema: dict[str, Any] = json.loads(read_text(SCHEMAS_DIR / "run-timeline-row.schema.json"))
    properties = schema["properties"]
    assert set(properties) == set(RunTimelineRow.csv_columns())

    for step in THE_EIGHT_STEPS:
        kinds = {branch.get("type") for branch in properties[step]["anyOf"]}
        assert kinds == {"integer", "null"}, f"{step} must be optional in the generated schema"
        assert step not in schema["required"]

    residual = properties["residual_ms"]
    assert residual["type"] == "integer"
    assert "minimum" not in residual, "the residual is signed; a floor would hide an overlap"
    assert "residual_ms" in schema["required"]
