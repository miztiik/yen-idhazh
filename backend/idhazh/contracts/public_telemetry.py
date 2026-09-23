"""The browser-safe projection of the item-health census.

`state/item-health/<YYYY>/<MM>/<DD>.csv` is the census - one row per planned item
per run - and it carries three cells a reader must never receive. This is the
narrow shape that does cross, written to `frontend/public/telemetry/<YYYY-MM>.csv`
and fetched a month at a time as the console pans its viewport. The two grains
differ on purpose: the ledger files by what a run writes, the mirror by what a
browser fetches (`docs/concepts/partitions.md`).

It is a contract rather than a tuple of names in the writer because the list is
a trust boundary (Guardrail #11). A projection spelled as strings gains a cell by a
one-word edit and nothing refuses it; a projection spelled as a model cannot
carry `canonical_url`, `url_key` or `detail` at all, and adding one fails at
import rather than in the published tree.

**`version` is a field and never a cell.** The published header is a browser
contract read as a prefix - `parseTelemetryCsv` in
`frontend/src/lib/charts/series.ts` compares position by position - so one more
name at position zero would shift every position the console reads and blank its
charts on every cached bundle. The shape's own stamp lives on this model, which
is where a reader of an old shard looks it up. A new cell is appended at the
end, never inserted
(`docs/architecture/publishing/telemetry-series.md`).
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Slug
from idhazh.contracts.call_cost import COST_FIELDS, CallKind
from idhazh.contracts.item_health import (
    CALL_SLOTS,
    RETIRED_CELLS,
    FailureCode,
    ItemOutcome,
    ItemStage,
    OneLine,
)

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

#: The stages `stage_gap_ms` is the remainder of. They tile the item without
#: overlapping, which is why `label_ms` and `summary_ms` are not among them: the
#: two are a split of `summarize_ms`, so counting them here would charge the
#: model stage twice and drive the gap negative on every item.
#:
#: A second copy of `idhazh.telemetry.record.NAMED_STAGE_MS`, which is what
#: writes the cell. Contracts are the bottom of the dependency graph and may not
#: import the module that fills them, so the two lists are held equal by a test
#: rather than by an import.
GAP_NAMED_STAGES: Final = ("fetch_ms", "extract_ms", "summarize_ms", "faithfulness_ms")


class PublicTelemetryRow(Contract):
    """One planned item on one run, as the console is allowed to read it."""

    __schema_stem__: ClassVar[str] = "public-telemetry"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-16",
            change="label_ms and summary_ms keep their names and change what they measure.",
            why="Each is now a stopwatch around its own request rather than the server's sum.",
        ),
        ChangelogEntry(
            version="2026-09-15T22:10",
            change="FailureCode gained model_timed_out and shard_out_of_time.",
            why="Both were being reported under a name that sends an operator to the wrong place.",
        ),
        ChangelogEntry(
            version="2026-09-15T20:00",
            change="The failure vocabulary gained model_refused.",
            why="It follows item-health-row, where the vocabulary is declared.",
        ),
        ChangelogEntry(
            version="2026-09-15T19:40",
            change="Four columns keep their names and change what they mean.",
            why="Queue wait now sits outside the item total rather than inside it.",
        ),
        ChangelogEntry(
            version="2026-09-02",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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
            "Where label_cached_tokens is filled, read the cache per call rather than "
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
    label_kind: CallKind | None = Field(
        default=None,
        description=(
            "Which call ran first: summarize, visual_plan, label or summarize_and_plan. "
            "It moves when the call structure moves, so a step change in these series "
            "reads as the design change it is rather than as a regression."
        ),
    )
    label_prefill_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the first call spent reading its prompt. A duration and never "
            "a rate: a prompt token costs more the deeper into the context it sits, so a "
            "per-call tok/s cannot be compared with another call's. The item's blended "
            "rate is the one that composes."
        ),
    )
    label_decode_ms: int | None = Field(default=None, ge=0)
    label_input_tokens: int | None = Field(default=None, ge=0)
    label_output_tokens: int | None = Field(default=None, ge=0)
    label_cached_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the first call reused. Zero is the cold-slot answer and is a "
            "measurement; empty means no split was published for this row."
        ),
    )
    summary_kind: CallKind | None = Field(
        default=None,
        description=(
            "Which call ran second, or empty where the item made one call. The pair of "
            "kinds is what lets a reader see a two-call item as two calls rather than "
            "inferring it from a subtraction."
        ),
    )
    summary_prefill_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Milliseconds the second call spent reading its prompt. Small on a warm "
            "slot, because that prompt is the first call's prompt extended and the "
            "server answers the shared head from its cache."
        ),
    )
    summary_decode_ms: int | None = Field(default=None, ge=0)
    summary_input_tokens: int | None = Field(default=None, ge=0)
    summary_output_tokens: int | None = Field(default=None, ge=0)
    summary_cached_tokens: int | None = Field(default=None, ge=0)

    # --- Where the item's time went ------------------------------------------
    #
    # The eight named stages and the remainder. They tile the item: every one of
    # them is a slice of item_total_ms, and stage_gap_ms is what is left. A
    # named stage published without the gap beside it would let a regression
    # move into an unnamed step and read as nothing at all.
    queue_wait_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How long the item waited before its worker started it - its own fetch "
            "and extract subtracted, because both are work rather than waiting. It "
            "sits outside item_total_ms rather than inside it."
        ),
    )
    label_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall time of the label call, on our own stopwatch around the request. It "
            "is a slice of summarize_ms, never an addition to it, and label_prefill_ms "
            "plus label_decode_ms taken off it is the part the server did not claim."
        ),
    )
    summary_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall time of the summarize-and-plan call, on the same stopwatch. The other "
            "slice of summarize_ms."
        ),
    )
    visual_plan_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall time attributed to producing the visual plan. The plan is decoded "
            "inside the summarize-and-plan call, so this is a share of summary_ms and "
            "not a clock of its own - visual_plan_ms_is_estimate says which."
        ),
    )
    visual_plan_ms_is_estimate: bool | None = Field(
        default=None,
        description=(
            "True where visual_plan_ms was apportioned out of the second call rather "
            "than timed on its own. An estimate that does not say it is one is the "
            "failure this column exists to prevent (Guardrail #10), and a page drawing "
            "the plan's share has to be able to mark it."
        ),
    )
    faithfulness_ms: int | None = Field(
        default=None,
        ge=0,
        description="Wall time of the model-free faithfulness scorers.",
    )
    model_wait_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Time the item spent waiting on the model server rather than being served. "
            "It is inside summarize_ms, so a rising wait with a flat decode rate is a "
            "queue and never a slower model."
        ),
    )
    item_total_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "What the item cost, from the item starting to the item ending with "
            "queue_wait_ms taken out. The denominator every stage share on the page is "
            "taken against, and the reason the wait is excluded: the stage runs its "
            "fetch loop and its model loop in different orders, so the raw clock "
            "counts the whole queue ahead of each item and a column summed across a "
            "shard reported the shard's own duration once per item."
        ),
    )
    stage_gap_ms: int | None = Field(
        default=None,
        description=(
            "item_total_ms minus every named stage. **This is the one cell that can "
            "catch a regression in a step nobody named**, which is why it is published "
            "rather than derived by a reader who would have to know the list. It is "
            "signed on purpose: a negative value means two named stages overlapped, or "
            "two clocks disagreed, and clamping it to zero would hide exactly that."
        ),
    )

    # --- Whether the model slowed or the work grew ---------------------------
    #
    # A total cannot tell those apart and a rate can. The row already carries
    # the tokens each call wrote, so these four are what completes the pair.
    visual_plan_tokens_written: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Output tokens of the second call that belong to the visual plan rather "
            "than to the summary. Empty where the run asked for no plan."
        ),
    )
    label_prefill_tokens_per_s: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Prefill throughput of the label call, over the tokens the server really "
            "evaluated - the input minus whatever the cache already held."
        ),
    )
    label_decode_tokens_per_s: float | None = Field(
        default=None, ge=0.0, description="Decode throughput of the label call."
    )
    summary_prefill_tokens_per_s: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Prefill throughput of the summarize-and-plan call, over the tokens the "
            "server really evaluated. A warm slot answers almost the whole prompt from "
            "the cache, and that shows up in summary_cache_pct rather than here: this "
            "cell is about the machine, so counting the skipped tokens as work would "
            "make a cache hit read as a fast server."
        ),
    )
    summary_decode_tokens_per_s: float | None = Field(
        default=None, ge=0.0, description="Decode throughput of the summarize-and-plan call."
    )

    # --- What it ran on ------------------------------------------------------
    #
    # A throughput number with no machine beside it is not a measurement
    # (Guardrail #10). These let a row from a slower runner be read as a slower
    # runner rather than as a regression.
    cpu_model: OneLine | None = Field(
        default=None,
        description=(
            "The processor the runner reported, verbatim. Constant inside a shard and "
            "carried per row anyway, because the shard-grain counters that hold it are "
            "read at build time and never published for a browser to join against. It "
            "is 32 of the row's raw bytes and 1.54 of its gzipped bytes, so it is the "
            "first cell to drop if the published cap ever binds."
        ),
    )
    cpu_busy_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "Mean busy share of every processor over this item. Busy ticks over "
            "available ticks across the item, so it is a figure a reader can add up."
        ),
    )
    load_1m: float | None = Field(
        default=None,
        ge=0.0,
        description="One-minute load average when the item ended.",
    )

    @model_validator(mode="after")
    def _a_published_failure_says_why(self) -> Self:
        """The console groups failures by code, so a failure with none is a bar
        it can draw and cannot label."""
        if self.outcome is ItemOutcome.FAILED and self.code is None:
            raise ValueError("a failed published telemetry row must carry a failure code")
        return self

    @model_validator(mode="after")
    def _a_published_call_is_published_whole(self) -> Self:
        """A slot fills entirely or not at all, and the flat cells are their sum.

        **The browser used to derive the second call by subtracting it from the
        total, and the subtraction was the bug.** The month shard published six
        first-call cells and stopped, so a reader that wanted the second call had
        to assume the remainder was one call, could not name what kind of call it
        was, and got a plausible number on any row where the assumption was
        false. The cells are published now, and the rule here is the same one the
        source ledger holds itself to - filled whole, and the flat cells equal the
        sum - so the two can be compared without either side reinterpreting the
        other.
        """
        filled = 0
        for slot in CALL_SLOTS:
            cells = [getattr(self, f"{slot}_{field}") for field in COST_FIELDS]
            kind = getattr(self, f"{slot}_kind")
            if kind is None and all(cell is None for cell in cells):
                continue
            if kind is None or any(cell is None for cell in cells):
                raise ValueError(f"the {slot} call is published whole or not at all")
            if getattr(self, f"{slot}_cached_tokens") > getattr(self, f"{slot}_input_tokens"):
                raise ValueError(f"{slot}_cached_tokens cannot exceed {slot}_input_tokens")
            filled += 1
        if filled == 0:
            if self.model_calls is not None:
                raise ValueError("model_calls is published only beside the calls it counts")
            return self
        if self.label_kind is None:
            raise ValueError("a second call is published only after a first")
        if self.model_calls != filled:
            raise ValueError("model_calls must equal the number of published calls")
        for field in COST_FIELDS:
            total = sum(
                getattr(self, f"{slot}_{field}")
                for slot in CALL_SLOTS
                if getattr(self, f"{slot}_kind") is not None
            )
            if getattr(self, field) != total:
                raise ValueError(f"{field} must equal the sum over the published calls")
        return self

    @model_validator(mode="after")
    def _the_published_stages_tile_the_item(self) -> Self:
        """The gap is exactly what the named stages left over.

        The console draws these cells as shares of one bar, so the shares have to
        add up to the bar. `stage_gap_ms` is recorded rather than derived - a
        reader deriving it would need the list of named stages, and the list is
        the thing that moves - which means the published row can carry a gap that
        disagrees with the stages beside it. A chart drawn from that is a chart
        whose slices miss the total by an amount nobody can see.

        Checked only where both ends are published: every row written before
        today carries neither, and `label_ms` and `summary_ms` are a split of
        `summarize_ms` rather than stages of their own, so they are not here.
        """
        if self.item_total_ms is None or self.stage_gap_ms is None:
            return self
        named = sum(getattr(self, name) or 0 for name in GAP_NAMED_STAGES)
        if self.stage_gap_ms != self.item_total_ms - named:
            raise ValueError(
                "stage_gap_ms must equal item_total_ms minus "
                f"{', '.join(GAP_NAMED_STAGES)}"
            )
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

        **A cell under a retired heading is read into the column that replaced
        it.** Every month shard published before this change heads its six
        first-call cells `call_1_*`, and those shards are what a reader's browser
        has cached.
        """
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.csv_columns()}
        for retired, current in RETIRED_CELLS.items():
            if current in payload and payload[current] == "":
                payload[current] = row.get(retired, "")
        for name, field in cls.model_fields.items():
            if name in payload and field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)


if FORBIDDEN_COLUMNS & set(PublicTelemetryRow.model_fields):
    raise AssertionError(
        "a source-ledger field a reader may never receive is on the published "
        f"projection: {sorted(FORBIDDEN_COLUMNS & set(PublicTelemetryRow.model_fields))}"
    )
