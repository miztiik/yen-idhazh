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
#: A second copy of `idhazh.itemrecord.NAMED_STAGE_MS`, which is what writes the
#: cell. Contracts are the bottom of the dependency graph and may not import the
#: module that fills them, so the two lists are held equal by a test rather than
#: by an import.
GAP_NAMED_STAGES: Final = ("fetch_ms", "extract_ms", "summarize_ms", "faithfulness_ms")


class PublicTelemetryRow(Contract):
    """One planned item on one run, as the console is allowed to read it."""

    __schema_stem__: ClassVar[str] = "public-telemetry"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-15T22:10",
            change=(
                "FailureCode gained model_timed_out and shard_out_of_time."
            ),
            why=(
                "Both were being reported under a name that sends an operator to the wrong "
                "place.\n\nA socket timeout is a TimeoutError, which subclasses OSError, so the "
                "handler that meant 'nothing answered' caught 'the server answered too slowly' as "
                "well. Thirty items across 2026-09-13, 09-14 and 09-15 were filed as a dead model "
                "server that was serving their neighbours fine: on one shard nine of the fourteen "
                "items after the first such failure published normally. The fix an operator needs "
                "is the output budget, and model_unreachable sends them to the process "
                "instead.\n\nshard_out_of_time is the worker stopping on its own clock rather than "
                "being killed on the platform's. not_attempted already means the run's plan never "
                "reached the item; this means the item was planned, fetched, extracted, and the "
                "shard declined to start work it could not finish. Filing both under one name "
                "would hide a throughput problem inside a supply one.\n\nWidening only. No row an "
                "earlier run wrote carries either code, because no run could emit one, and every "
                "reader takes the enum by value."
            ),
        ),
        ChangelogEntry(
            version="2026-09-15T19:40",
            change=(
                "queue_wait_ms, item_total_ms and the two prefill rates keep their "
                "names and change what they mean, following the census columns they "
                "are projected from."
            ),
            why=(
                "queue_wait_ms now sits outside item_total_ms rather than inside it, so "
                "the stages still tile the item and the console's own check still "
                "holds. The wait was never work, and counting it made each item carry "
                "the queue ahead of it: a two-item shard published 2,786 seconds of "
                "item time over a shard that took 2,196.\n\n"
                "The prefill rates now divide by the tokens the server evaluated. The "
                "old cell said a warm slot was a fast machine, which is the one "
                "conclusion the number must not support - the cache share is published "
                "beside it and was already saying that.\n\n"
                "No cell is added or removed and no type moves, so every published row "
                "still parses. A page comparing a run from before this stamp with one "
                "from after it is comparing two different questions."
            ),
        ),
        ChangelogEntry(
            version="2026-09-15T08:20",
            change=(
                "Appended seventeen nullable cells: queue_wait_ms, label_ms, summary_ms, "
                "visual_plan_ms, visual_plan_ms_is_estimate, faithfulness_ms, "
                "model_wait_ms, item_total_ms, stage_gap_ms, visual_plan_tokens_written, "
                "the four per-call prefill and decode rates, cpu_model, cpu_busy_pct "
                "and load_1m."
            ),
            why=(
                "The census records 113 columns and this projection published 32, so "
                "three questions an operator asks had no answer on any page.\n\n"
                "Where did an item's time go? The published row carried fetch, extract "
                "and summarize and nothing else, so the queue wait, the faithfulness "
                "scorers, the wait on the model server and the split of the summarize "
                "stage between its two calls were all invisible - and so was the "
                "remainder. stage_gap_ms is the one that matters most and it is the "
                "reason the other eight come with it: it is item_total_ms minus every "
                "named stage, so it is the only cell that can catch a regression in a "
                "step nobody has thought to time, and it is worth nothing without the "
                "named stages beside it to subtract from.\n\n"
                "Is the model getting slower, or is there just more to write? A total "
                "cannot say. The four rates and visual_plan_tokens_written can: a "
                "decode rate that fell while the wall clock held still is a regression, "
                "and a wall clock that rose while the rate held still is a longer "
                "summary. The row already carried the tokens written per call, so the "
                "rates are what completes the pair.\n\n"
                "Was it the machine? cpu_busy_pct and load_1m are per item and vary "
                "item to item, so a slow row can be read as a busy box. cpu_model is "
                "constant inside a shard and is carried anyway, because a throughput "
                "number with no machine beside it is not a measurement (Guardrail #10) "
                "and the shard-grain counters that hold it are not published to a "
                "browser.\n\n"
                "Measured 2026-09-15 on the 12,037 committed rows of the two published "
                "shards, with every new cell filled the way its producer writes it "
                "(durations from the row's own recorded milliseconds, rates at "
                "round(x, 2), one 31-character processor string): a row goes from 142.7 "
                "to 219.5 raw bytes and from 32.12 to 54.50 gzipped. Fourteen months of "
                "retention at the busiest committed day goes from 5.58 to 8.59 percent "
                "of the 1 GB published cap. cpu_model is 32.00 of the 76.8 raw bytes "
                "and 1.54 of the 22.4 gzipped, so it is the one cell to drop first if "
                "the cap ever binds.\n\n"
                "Appended at the end and nullable, because the browser reads this "
                "header by position (parseTelemetryCsv compares a prefix). Every "
                "committed row is empty in all seventeen, so from_csv_row reads an "
                "absent cell as null and a shard published before today still loads. "
                "stage_gap_ms carries no lower bound: it is signed on purpose, and "
                "clamping it would hide the overlapping clocks it exists to show."
            ),
        ),
        ChangelogEntry(
            version="2026-09-15T04:30",
            change="The failure vocabulary this payload publishes gained no_title.",
            why=(
                "Extract gained a refusal for an item whose feed carried no headline. No "
                "field here changed; the vocabulary is inlined into this schema, so the "
                "generated file's bytes move and the change is stamped here rather than "
                "left to the drift gate to announce (section 11). Additive: a payload "
                "written before today names none of the new values and still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-09-15T00:00",
            change=(
                "The six first-call cells are named for what the call does - call_1_* "
                "became label_*. The six second-call cells were appended: "
                "summary_kind, summary_prefill_ms, summary_decode_ms, "
                "summary_input_tokens, summary_output_tokens, summary_cached_tokens."
            ),
            why=(
                "The projection published the first call and the total and stopped, on "
                "the reasoning that a browser could derive the second call by "
                "subtracting. It could not, in three ways that all read as plausible "
                "numbers rather than as errors. The remainder has no kind, so nothing "
                "on the page could say what the second call was. The remainder is one "
                "call only if model_calls is 2, and model_calls is empty on every row "
                "published before 2026-09-12. And a reader that wanted the second "
                "call's cache rate had to subtract two cells and divide, which is "
                "three chances to get a ratio wrong for a number the producer already "
                "held exactly.\n\n"
                "Appended at the end, so the positional prefix the console parses is "
                "unchanged and a cached bundle keeps working. from_csv_row reads a "
                "retired call_1_* heading into its label_* column, so a shard "
                "published before this change still parses."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T01:30",
            change="ItemStage gained visual. No row here can carry it.",
            why=(
                "The enum is inlined in this schema, so a name added for the event "
                "envelope's src becomes legal in this column too. It is unreachable: every "
                "row here projects an item-health row, and that census column refuses "
                "visual because an item whose picture failed still publishes. The entry "
                "exists so the widening is dated rather than inferred from a schema diff."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T16:20",
            change=(
                "Added nullable model_calls, label_kind and the first call's five cost "
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
                "cell, and a zero in label_cached_tokens is the cold-slot measurement."
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
            "Wall time of the label call, prefill and decode together. It is a slice of "
            "summarize_ms, never an addition to it."
        ),
    )
    summary_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall time of the summarize-and-plan call, prefill and decode together. The "
            "other slice of summarize_ms."
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
