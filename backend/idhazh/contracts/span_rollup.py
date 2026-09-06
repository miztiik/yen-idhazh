"""One shard's spans, folded to a count and a duration per committed span name
(`state/span-rollup/<YYYY-MM>.csv`).

A span is evidence that a step happened; this row is the record of it. The whole
span vocabulary is `telemetry.SpanName`, eleven names, and it lives with the
evidence because a span is evidence. Five of those names are committed here as a
record, and only five, because the row exists to hold what no ledger already
holds.

**The other six are left out because a ledger column already times them.**
`fetch`, `extract`, `summarize`, `score` and `visual_planner` each own a `*_ms`
column - `fetch_ms`, `extract_ms`, `summarize_ms` on the item-health row,
`score_ms` on the eval row, `decision_ms` on the visual decision. `model_call`
is `prefill_ms` plus `decode_ms`, reported by the model server after the call
returned. Committing any of those here would be a second account of a number a
ledger already keeps, and two accounts of one number is the thing this row
refuses to be (`docs/concepts/telemetry.md`). The five that remain -
`robots` inside `fetch`, `tag` inside `extract`, `render_prompt` and
`parse_reply` inside `summarize`, and the `item` they all hang under - are the
steps no column separates and no column should: a column per sub-step is a wider
ledger for a question asked once a quarter.

**The row is derived, not a fourth account.** It is a fold of the shard's own
spans - one row per `(date, run_id, shard, span_name)`, carrying how many spans
of that name the shard opened and how long they took added together. It restates
nothing: a test holds its columns disjoint, outside the key, from every
committed ledger's columns.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId


class RollupSpan(StrEnum):
    """The five spans a shard commits a count and a duration for.

    This is the committed subset of `telemetry.SpanName`, and it lives in the
    contract rather than beside the tracer because a committed column's ids are a
    contract: a reader a year from now parses `span_name` against this enum, not
    against the tracer's wider list. `telemetry` derives its filter from this
    enum, so the two cannot drift and this is the one place the committed set is
    written down.

    Declared in the order the fold emits them - the `item` parent first, then the
    four sub-steps in the order the pipeline runs them.
    """

    ITEM = "item"
    ROBOTS = "robots"
    TAG = "tag"
    RENDER_PROMPT = "render_prompt"
    PARSE_REPLY = "parse_reply"


class SpanRollupRow(Contract):
    """One `(date, run_id, shard, span_name)` group's span count and summed duration."""

    __schema_stem__: ClassVar[str] = "span-rollup-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-06",
            change=(
                "Initial shape: one row per (date, run_id, shard, span_name), carrying "
                "the span count and the summed duration for one of the five committed "
                "spans."
            ),
            why=(
                "Contracts before logic - the fold and the ledger are written against a "
                "fixed row. The row carries a count and a total and nothing else, because "
                "every other cut of a span's timing is already a ledger column and a "
                "second account of a number a ledger holds is what this row exists not to "
                "be. It commits five span names and not the eleven the tracer opens, for "
                "the same reason: the other six each have a column that already times "
                "them."
            ),
        ),
    )

    date: DateStamp
    run_id: RunId
    shard: int = Field(ge=0, description="Which work shard of the run these spans came from.")
    span_name: RollupSpan = Field(
        description="Which of the five committed spans this row folds, as the enum spells it."
    )
    count: int = Field(
        ge=1,
        description=(
            "How many spans of this name the shard opened. At least one: a name with no "
            "span produces no row rather than a zero row, so an absent row reads as never "
            "opened and never as opened-and-measured-nothing."
        ),
    )
    total_ms: int = Field(
        ge=0,
        description=(
            "Every span of this name added together, in whole milliseconds. A total and "
            "not a mean, because a mean cannot be re-summed across shards and the "
            "reconciliation that reads this row needs the sum. Zero is possible and "
            "honest: a counted span can round to nothing."
        ),
    )

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the row."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string."""
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)
