"""The browser-safe projection of the item-health census.

`state/item-health/<YYYY-MM>.csv` is the census - one row per planned item per
run - and it carries three cells a reader must never receive. This is the narrow
shape that does cross, written to `frontend/public/telemetry/<YYYY-MM>.csv` and
fetched a month at a time as the console pans its viewport.

It is a contract rather than a tuple of names in the writer because the list is
a trust boundary (Guardrail #11). A projection spelled as strings gains a cell by a
one-word edit and nothing refuses it; a projection spelled as a model cannot
carry `canonical_url`, `url_key` or `detail` at all, and adding one fails at
import rather than in the published tree.

**`version` is a field and never a cell.** The published header is a browser
contract read as a prefix - `parseTelemetryCsv` in
`frontend/src/lib/charts/series.ts` compares position by position - so one more
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
from idhazh.contracts.call_cost import COST_FIELDS, CallKind
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
            version="2026-09-12T16:20",
            change=(
                "Added nullable model_calls, call_1_kind and the first call's five cost "
                "cells at the end of the row. The second call is the remainder."
            ),
            why=(
                "The census records each model call's own cost and this projection kept "
                "only the item total, so the console's cache figures were about to stop "
                "meaning anything: readWhole counts items whose prompt was read whole, "
                "749 of the 5,197 rows carrying a cache figure on 2026-09-12, and a "
                "second call that reuses the first call's prompt takes it to zero for "
                "ever with no code change. The first call plus the total is the whole "
                "split, because the flat cells are their sum and the arithmetic is exact "
                "integers - so the second call is total minus first, and model_calls is "
                "what says how many calls that remainder covers rather than letting a "
                "third be absorbed in silence. Both calls spelled out would have cost "
                "more than the split is worth to a fetch: measured 2026-09-12 on the two "
                "committed shards with every timed row populated, twelve cells cost 72.9 "
                "and 80.1 percent more gzipped against 35.3 and 40.8 for these seven. "
                "Appended at the end and nullable, because the browser reads this header "
                "by position. Empty stays empty - a run that recorded no split writes no "
                "cell, and a zero in call_1_cached_tokens is the cold-slot measurement."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T20:00",
            change=(
                "Added nullable fetch_ms, extract_ms, summarize_ms, prefill_ms, "
                "decode_ms, input_tokens, output_tokens and cached_tokens at the end "
                "of the row."
            ),
            why=(
                "Every run since 2026-08-23 has measured these eight and written them "
                "to state/item-health/, and the projection dropped all eight on the "
                "way out - so the console could show that a stage failed and never "
                "how long the stage took. They are counts and durations of our own "
                "work, not the fetched page, so they cross on the same terms "
                "source_words always has. Appended at the end and nullable, because "
                "the browser reads this header by position: a name inserted anywhere "
                "else shifts every column the console already draws. Empty stays "
                "empty - an instrument that did not run writes no cell, never a zero, "
                "or a stage that was skipped reads as a stage that took no time."
            ),
        ),
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
                "three (Guardrail #3). Typing it also gives the migration something to read "
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
    fetch_ms: int | None = Field(
        default=None,
        ge=0,
        description="Milliseconds spent fetching the page. Empty where fetch did not run.",
    )
    extract_ms: int | None = Field(
        default=None,
        ge=0,
        description="Milliseconds spent extracting the body. Empty where extract did not run.",
    )
    summarize_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the summarizer held the item, prompt and summary together. "
            "Empty where summarize did not run."
        ),
    )
    prefill_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds of that spent reading the prompt. Reading and writing run at "
            "different rates, so summarize_ms alone cannot separate them."
        ),
    )
    decode_ms: int | None = Field(
        default=None,
        ge=0,
        description="Milliseconds of that spent writing the summary.",
    )
    input_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Tokens read. A rate needs its token count beside its milliseconds.",
    )
    output_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Tokens written.",
    )
    cached_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Tokens the server answered from its prompt cache rather than reading again, "
            "added over every call the row records. Zero is a real answer here and means "
            "nothing was cached; empty means the server reported no cache figure at all. "
            "Where call_1_cached_tokens is filled, read the cache per call rather than "
            "here: a second call reusing the first call's prompt makes this non-zero on "
            "every item."
        ),
    )
    model_calls: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many model calls the cells above add up over. Empty on every row "
            "published before 2026-09-12. It is what says whether the remainder - the "
            "total minus the first call - is one more call or several."
        ),
    )
    call_1_kind: CallKind | None = Field(
        default=None,
        description=(
            "Which call ran first: summarize, visual_plan, label or summarize_and_plan. "
            "It moves when the call structure moves, so a step change in these series "
            "reads as the design change it is rather than as a regression."
        ),
    )
    call_1_prefill_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the first call spent reading its prompt. A duration and never "
            "a rate: a prompt token costs more the deeper into the context it sits, so a "
            "per-call tok/s cannot be compared with another call's. The item's blended "
            "rate is the one that composes."
        ),
    )
    call_1_decode_ms: int | None = Field(default=None, ge=0)
    call_1_input_tokens: int | None = Field(default=None, ge=0)
    call_1_output_tokens: int | None = Field(default=None, ge=0)
    call_1_cached_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the first call reused. Zero is the cold-slot answer and is a "
            "measurement; empty means no split was published for this row."
        ),
    )

    @model_validator(mode="after")
    def _a_published_failure_says_why(self) -> Self:
        """The console groups failures by code, so a failure with none is a bar
        it can draw and cannot label."""
        if self.outcome is ItemOutcome.FAILED and self.code is None:
            raise ValueError("a failed published telemetry row must carry a failure code")
        return self

    @model_validator(mode="after")
    def _the_remainder_is_a_call_and_not_a_negative_number(self) -> Self:
        """The published split is the first call and the total; the rest is arithmetic.

        A browser derives the second call by subtracting, so the cells have to
        leave a subtraction that can be made and can be trusted: the first call
        fills whole or not at all, it never exceeds the total, and `model_calls`
        says how many calls the remainder covers.
        """
        cells = [getattr(self, f"call_1_{field}") for field in COST_FIELDS]
        if self.call_1_kind is None and all(cell is None for cell in cells):
            if self.model_calls is not None:
                raise ValueError("model_calls is published only beside the call it counts")
            return self
        if self.call_1_kind is None or any(cell is None for cell in cells):
            raise ValueError("the first call is published whole or not at all")
        if self.model_calls is None:
            raise ValueError("a published call carries the count of calls it is one of")
        if self.call_1_cached_tokens > self.call_1_input_tokens:  # type: ignore[operator]
            raise ValueError("call 1 cached_tokens cannot exceed its input_tokens")
        for field in COST_FIELDS:
            total = getattr(self, field)
            first = getattr(self, f"call_1_{field}")
            if total is None or first > total:
                raise ValueError(f"call_1_{field} must leave a remainder inside {field}")
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
