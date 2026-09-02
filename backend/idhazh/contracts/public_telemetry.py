"""The browser-safe projection of the item-health census.

`state/item-health/<YYYY-MM>.csv` is the census - one row per planned item per
run - and it carries three cells a reader must never receive. This is the narrow
shape that does cross, written to `frontend/public/telemetry/<YYYY-MM>.csv` and
fetched a month at a time as the console pans its viewport.

It is a contract rather than a tuple of names in the writer because the list is
a trust boundary (Rule #11). A projection spelled as strings gains a cell by a
one-word edit and nothing refuses it; a projection spelled as a model cannot
carry `canonical_url`, `url_key` or `detail` at all, and adding one fails at
import rather than in the published tree.

**`version` is a field and never a cell.** The published header is a browser
contract read as a prefix - `parseTelemetryCsv` in
`frontend/src/lib/charts/series.ts` compares position by position - so a twelfth
name at position zero would shift every position the console reads and blank its
charts on every cached bundle. The shape's own stamp lives in
`schemas/public-telemetry.schema.json`, which is where a reader of an old shard
looks it up. A new cell is appended at the end, never inserted
(`docs/architecture/publishing/telemetry-series.md`).
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Slug
from idhazh.contracts.item_health import FailureCode, ItemOutcome, ItemStage

#: The three source-ledger cells that may never reach a browser. `detail` is
#: diagnostic free text and the two address fields identify the page rather than
#: the measurement, so none of them is needed to draw a rate or a compression.
FORBIDDEN_COLUMNS: Final[frozenset[str]] = frozenset({"canonical_url", "url_key", "detail"})

#: The item's address, carried as an OPAQUE key rather than as `ItemId`.
#:
#: Item identity is minted once, by `ItemHealthRow`, and no other writer reaches
#: this file - so re-spelling the grammar here would put it in two contracts and
#: buy nothing. It would also cost something real: a published shard is a file
#: with no writer left, so the day the id grammar moves, every shard already
#: published would stop loading, and a payload an earlier run wrote that today's
#: build cannot read is a release blocker (`CLAUDE.md` section 11). Bounded and
#: non-empty is what the console needs of it: the id is a join key on the page
#: and never a path segment.
PublicItemKey = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class PublicTelemetryRow(Contract):
    """One planned item on one run, as the console is allowed to read it."""

    __schema_stem__: ClassVar[str] = "public-telemetry"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-02",
            change=(
                "Initial shape: the eleven published columns, typed, with "
                "canonical_url, url_key and detail refused at import."
            ),
            why=(
                "The only thing standing between the item-health census and a "
                "browser was a tuple of eleven strings in publish_telemetry.py and a "
                "set of three more it was checked against. Both are readable code and "
                "neither is a contract, so the projection had no schema, no version "
                "stamp and no changelog while every other persisted surface has all "
                "three (Rule #3). Typing it also gives the migration something to read "
                "a committed shard back through, which is what proves a published file "
                "still loads rather than merely still parses. item_id is the one cell "
                "carried as an opaque key: identity is minted by ItemHealthRow, and a "
                "published shard has no writer left to re-mint it if that grammar "
                "moves."
            ),
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: PublicItemKey
    vertical: Slug
    source_id: Slug
    stage: ItemStage
    outcome: ItemOutcome
    code: FailureCode | None = None
    source_words: int | None = Field(default=None, ge=0)
    summary_words: int | None = Field(default=None, ge=0)
    source_words_before_cap: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Words in the extracted body before extract.truncation_cap_tokens cut it. "
            "A count of our own extraction, never the text, so it crosses on the same "
            "terms source_words always has. Empty on every row written before "
            "2026-08-28, and empty means unknown rather than uncut."
        ),
    )

    @model_validator(mode="after")
    def _a_published_failure_says_why(self) -> Self:
        """The console groups failures by code, so a failure with none is a bar
        it can draw and cannot label."""
        if self.outcome is ItemOutcome.FAILED and self.code is None:
            raise ValueError("a failed published telemetry row must carry a failure code")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The published header. `version` is a field of the shape, not a cell."""
        return tuple(name for name in cls.model_fields if name != "version")

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. An absent optional is an empty cell."""
        payload = self.model_dump(mode="json")
        return {
            name: "" if payload[name] is None else str(payload[name])
            for name in self.csv_columns()
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never the empty string.

        A shard carries no `version` cell, so the row is stamped with the current
        one on read the way any document that omits it is.
        """
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.csv_columns()}
        for name, field in cls.model_fields.items():
            if name in payload and field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)


if FORBIDDEN_COLUMNS & set(PublicTelemetryRow.model_fields):
    raise AssertionError(
        "a source-ledger field a reader may never receive is on the published "
        f"projection: {sorted(FORBIDDEN_COLUMNS & set(PublicTelemetryRow.model_fields))}"
    )
