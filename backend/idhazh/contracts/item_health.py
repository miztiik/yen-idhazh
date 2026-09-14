"""What happened to one planned item on one run.

One row per planned item per run, appended to
`state/item-health/<YYYY>/<MM>/<DD>.csv`. The row is a census: successes and
failures share one file, because a rate needs its denominator beside its
numerator.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Slug,
    Url,
    UrlKey,
)
from idhazh.contracts.call_cost import COST_FIELDS, CallKind

ItemHealthDetail = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ItemStage(StrEnum):
    """The pipeline's stage vocabulary - one name per step an item passes through.

    **Three contracts take this type and only one of them means "terminal".**
    `ItemHealthRow.stage` is the census column and records where an item
    STOPPED, so it takes `TERMINAL_STAGES` and refuses anything else.
    `DayStageTiming.stage` names the step a clock was read at, and
    `telemetry.event(src=...)` names the step that logged a line. Neither of
    those two is an ending, and neither is exhaustive - `publish_day_metrics`
    times three of these names and one emitter writes one of them.

    Declaration order is the funnel a person reads down, and
    `retention.fold_month` sorts a month's groups by it. The order is free to
    change: this is a `StrEnum`, so the wire value is the string and never the
    position.
    """

    PLAN = "plan"
    FETCH = "fetch"
    EXTRACT = "extract"
    SUMMARIZE = "summarize"
    #: Planning and drawing a picture, which happen inside the work stage once a
    #: summary is accepted. **Not terminal**: an item whose picture failed still
    #: reaches the digest, so it leaves a `publish` row and the census column
    #: refuses this name. It exists so the step that draws can say so in a log
    #: line - `telemetry.event(src=...)` names the step that wrote the line, and
    #: a render failure had no name and made no sound until it did.
    VISUAL = "visual"
    PUBLISH = "publish"


#: The stages an item can STOP at, and the only values `ItemHealthRow.stage`
#: accepts. Spelled out rather than derived from the enum, so a stage added for
#: the event envelope or for a clock has to say whether it is terminal instead
#: of inheriting the answer from `frozenset(ItemStage)`.
TERMINAL_STAGES: Final[frozenset[ItemStage]] = frozenset(
    {
        ItemStage.PLAN,
        ItemStage.FETCH,
        ItemStage.EXTRACT,
        ItemStage.SUMMARIZE,
        ItemStage.PUBLISH,
    }
)


class ItemOutcome(StrEnum):
    """Whether the item reached the digest."""

    OK = "ok"
    FAILED = "failed"


class ElementClass(StrEnum):
    """What one article's numbers say it could carry, and nothing else.

    **Three classes, and the count is the point.** The visual programme names
    five, and only two of them are a question about numbers. `comparative` and
    `processual` are claims about how an article is written, so they have no
    query yet and land with the diagram plan. Anything reporting per class before
    then names three and says so, rather than letting a reader take three for the
    whole taxonomy.

    The query rests on the element table's Tier 1 fields alone - `kind`, `value`
    and `unit` - so it is byte-exact and carries no model judgement.
    `idhazh.elements.classify` is the query; this is its vocabulary, and
    `docs/architecture/extraction/elements.md` is the page that owns it.

    **It is declared here rather than beside the element contract**, with the
    three other closed vocabularies this census row carries, because
    `contracts/element.py` sits above `contracts/article.py`, which sits above
    this module. A label a census row persists has to be declared at or below the
    row's own level, and this is the level.
    """

    #: The article states at least `visuals.min_chart_points` distinct quantities
    #: that share a unit, so bars could be drawn from what it says.
    CHARTABLE = "chartable"
    #: The article states no quantity at all. There is nothing to draw.
    NARRATIVE = "narrative"
    #: Quantities, but no unit shared widely enough to make a comparison. It may
    #: turn out to be `comparative` or `processual`, and neither has a query yet.
    UNCLASSIFIED = "unclassified"


class FailureCode(StrEnum):
    """Stable failure vocabulary for item-health rows.

    **Membership is one member per knob an operator turns, not one per gate.**
    Four HTTP members answer to one fetch, because the fix for a 404 is not the
    fix for a rate limit. `output_truncated` and `labels_truncated` are the two
    output budgets, derived from two different grammars, for the same reason.
    """

    NOT_ATTEMPTED = "not_attempted"
    ROBOTS_DENIED = "robots_denied"
    ROBOTS_UNREACHABLE = "robots_unreachable"
    BLOCKED_ADDRESS = "blocked_address"
    HTTP_CLIENT_ERROR = "http_client_error"
    HTTP_RATE_LIMITED = "http_rate_limited"
    HTTP_SERVER_ERROR = "http_server_error"
    NETWORK_ERROR = "network_error"
    NO_TEXT = "no_text"
    TOO_SHORT = "too_short"
    NOT_PROSE = "not_prose"
    BOILERPLATE = "boilerplate"
    PAYWALLED = "paywalled"
    UNSUPPORTED_FORM = "unsupported_form"
    MODEL_UNREACHABLE = "model_unreachable"
    CONTEXT_EXCEEDED = "context_exceeded"
    OUTPUT_TRUNCATED = "output_truncated"
    #: The two-call path's labelling reply ran out of its own output budget, so
    #: the call that writes the summary was never sent and the item is lost
    #: whole. `output_truncated` is the summary-writing call meeting its budget,
    #: which is a different derivation over a different grammar and a different
    #: number to move.
    LABELS_TRUNCATED = "labels_truncated"
    BAD_SHAPE = "bad_shape"
    LENGTH_OUT_OF_RANGE = "length_out_of_range"
    COPIED_SOURCE = "copied_source"
    LEAKED_ADDRESS = "leaked_address"
    UNKNOWN = "unknown"


FAILURE_CODE_STAGES: Final[Mapping[FailureCode, frozenset[ItemStage]]] = MappingProxyType(
    {
        FailureCode.NOT_ATTEMPTED: frozenset({ItemStage.PLAN}),
        FailureCode.ROBOTS_DENIED: frozenset({ItemStage.FETCH}),
        FailureCode.ROBOTS_UNREACHABLE: frozenset({ItemStage.FETCH}),
        FailureCode.BLOCKED_ADDRESS: frozenset({ItemStage.FETCH}),
        FailureCode.HTTP_CLIENT_ERROR: frozenset({ItemStage.FETCH}),
        FailureCode.HTTP_RATE_LIMITED: frozenset({ItemStage.FETCH}),
        FailureCode.HTTP_SERVER_ERROR: frozenset({ItemStage.FETCH}),
        FailureCode.NETWORK_ERROR: frozenset({ItemStage.FETCH}),
        FailureCode.NO_TEXT: frozenset({ItemStage.EXTRACT}),
        FailureCode.TOO_SHORT: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.NOT_PROSE: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.BOILERPLATE: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.PAYWALLED: frozenset({ItemStage.EXTRACT}),
        FailureCode.UNSUPPORTED_FORM: frozenset({ItemStage.EXTRACT}),
        FailureCode.MODEL_UNREACHABLE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.CONTEXT_EXCEEDED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.OUTPUT_TRUNCATED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LABELS_TRUNCATED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.BAD_SHAPE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LENGTH_OUT_OF_RANGE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.COPIED_SOURCE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LEAKED_ADDRESS: frozenset({ItemStage.SUMMARIZE}),
        # The catch-all covers every stage an item can stop at, and no more. It
        # read `frozenset(ItemStage)` until 2026-09-14, which meant a stage
        # added for any other reason became a legal census row the day it was
        # declared - the one line that would have let a new member in silently.
        FailureCode.UNKNOWN: TERMINAL_STAGES,
    }
)

SOURCE_NEUTRAL_FAILURE_CODES: Final[frozenset[FailureCode]] = frozenset(
    {
        FailureCode.NOT_ATTEMPTED,
        FailureCode.ROBOTS_DENIED,
        FailureCode.ROBOTS_UNREACHABLE,
        FailureCode.BLOCKED_ADDRESS,
        FailureCode.HTTP_RATE_LIMITED,
        FailureCode.TOO_SHORT,
        FailureCode.MODEL_UNREACHABLE,
        FailureCode.CONTEXT_EXCEEDED,
        FailureCode.NOT_PROSE,
        FailureCode.BOILERPLATE,
        FailureCode.OUTPUT_TRUNCATED,
        FailureCode.LABELS_TRUNCATED,
        FailureCode.BAD_SHAPE,
        FailureCode.LENGTH_OUT_OF_RANGE,
        FailureCode.COPIED_SOURCE,
        FailureCode.LEAKED_ADDRESS,
    }
)


class ItemHealthRow(Contract):
    """One item, one run, one terminal outcome."""

    __schema_stem__: ClassVar[str] = "item-health-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-14T02:00",
            change="Added nullable truncation_cap_tokens at the end of the row.",
            why=(
                "source_words_before_cap says a cut happened; nothing said which cap did "
                "it. So a reader asking which runs shared one cap had to compare "
                "source_words against int(truncation_cap_tokens / TOKENS_PER_WORD) as "
                "that ratio stands today - and the ratio is a reading that gets retaken. "
                "When it moved from 1.3 to 1.3628 on 2026-09-14 the implied ceiling went "
                "1,000 words to 953 and every historical row stopped matching at once, "
                "which reads as an empty population rather than as a broken question. "
                "The cap that cut a row is known at the moment of the cut and is now "
                "written there, taken from Article.truncated_at_tokens. Appended at the "
                "end and nullable: a row an earlier run wrote recorded no cap, and an "
                "empty cell is the honest answer rather than today's cap backfilled onto "
                "a run that never used it."
            ),
        ),
        ChangelogEntry(
            version="2026-09-14T01:30",
            change=(
                "ItemStage gained visual. The generated schema lists it because the enum "
                "is inlined here; the stage column refuses it and no row may carry it."
            ),
            why=(
                "The pipeline had no name for the step that draws a picture, so a render "
                "failure was silent: render.write caught the OSError, recorded "
                "render_failed on the day's own payload and logged nothing at all. The "
                "name exists for telemetry.event(src=...), which says which step wrote a "
                "line rather than where an item ended, and item.visual.failed is the "
                "first event to use it. It is not terminal - an item whose picture failed "
                "still publishes - so a visual row here would say the item stopped where "
                "it did not, and would shrink the publish count that publish_day_metrics "
                "and the console read. TERMINAL_STAGES is what this column accepts and a "
                "validator refuses the rest, so the widening is legal in the schema and "
                "unreachable in this ledger. No read-side migration is owed: no row an "
                "earlier run wrote can carry a value that did not exist."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13T14:20",
            change=(
                "A failed summarize row carries the five cost cells and the call slots, "
                "which it left empty whatever the reply had cost."
            ),
            why=(
                "This is the ledger a cost question is answered from, and it was the layer "
                "that dropped the numbers. The summary payload is where the defect was "
                "filed, but reconcile_prefill reads this row, and this branch passed the "
                "three stage timings and none of the five model cells - so a reply the "
                "stage refused arrived here with the numbers in hand and left as blanks. "
                "pool_ledger skips a row whose prefill_ms or input_tokens cell is empty, so "
                "the server counted those requests and the ledger pooled none of them, and "
                "the gap sat inside the 5 percent tolerance as unnamed drift. No field "
                "moved: the cells and the slots have been nullable since 2026-09-12T16:20 "
                "and the sum rule already binds them. A row an earlier run wrote keeps its "
                "blanks, and on a failed summarize row written before this version an empty "
                "cost cell means never recorded rather than free - which is the same reading "
                "'a null is not a zero' already asks for in "
                "docs/architecture/sources/item-health.md."
            ),
        ),
        ChangelogEntry(
            version="2026-09-13",
            change=(
                "Added the labels_truncated summarize failure code, source-neutral like "
                "every other code the model owns."
            ),
            why=(
                "The two-call path's labelling reply can run out of its output budget on "
                "an ordinary article - measured 2026-09-12, one article of three, 346 "
                "words, 900 tokens decoded and the JSON cut mid-string - and the item is "
                "then lost whole, because the call that writes the summary replays that "
                "reply and is never sent. It was recorded as bad_shape, which is also "
                "what a reply that held valid JSON and violated the schema records, and "
                "also what a stray reasoning channel records; the only thing separating "
                "them was a sentence in a log line. The same commit derives that budget "
                "from the labelling grammar instead of from the summariser's knob, and "
                "this counter is how anyone sees whether that worked - folded into "
                "output_truncated it would move with call 2's cuts and answer nothing. "
                "It is a separate member rather than a second reading of output_truncated "
                "because the two are two derivations over two grammars: two numbers to "
                "move, so two counts to read. No read-side migration is owed - the code "
                "is additive and no run has written it - but a reader trending bad_shape "
                "across 2026-09-13 sees a step down that nothing else in the CSV "
                "explains, and this entry is where that is written."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T18:40",
            change=(
                "item_id accepts a second shape: sixteen Crockford base32 symbols "
                "beside the decimal digits it already took."
            ),
            why=(
                "Ten decimal digits is 33 bits of the address, which collides often "
                "enough that the collision had to be resolved - and the only way to "
                "resolve one is to step the loser past whatever else the run planned, "
                "so a collided id depended on the day's pool rather than on the "
                "address alone. Two runs of one day draw different pools, so the same "
                "article came back under a second id and published twice. Eighty bits "
                "do not collide. This widens and never contracts: every day published "
                "before today carries the decimal shape and a published day is frozen, "
                "so nothing was rewritten and no read-side migration is owed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-12T16:20",
            change=(
                "Added nullable model_calls, call_1_kind, call_2_kind and the five cost "
                "cells for each call at the end of the row; the five flat cost cells are "
                "now the item's total across the calls the row records."
            ),
            why=(
                "This is the only ledger that carries every planned item, so it is where "
                "a per-call cost has to land - and it kept one call's five numbers "
                "without saying which. Folded, cached_tokens stops answering the "
                "question it exists for: measured on the one two-call run, 0 and 1,493 "
                "fold to 1,493 against 3,886 prompt tokens, so an item whose first call "
                "read its whole prompt reads as an item that cached most of it. The kind "
                "is carried beside each slot because the call structure moves under this "
                "row rather than beside it, and without it the day a flag flips reads as "
                "a regression. Appended at the end and nullable, so a row an earlier run "
                "wrote still reads: those runs recorded a total and no split, and their "
                "cells stay empty rather than carrying a number invented today. Where a "
                "slot is filled the flat cells must equal the sum over the filled slots, "
                "which is what keeps reconcile_prefill and every console rate correct "
                "with no edit of their own."
            ),
        ),
        ChangelogEntry(
            version="2026-09-08T21:00",
            change=(
                "Added nullable span_integrity, elements_found and element_class at the "
                "end of the row."
            ),
            why=(
                "The visual planner draws nothing on most items and nothing said whether "
                "the article had anything to draw, so a fall in published charts read the "
                "same whether the planner stopped choosing them or the extractor stopped "
                "finding numbers - and those have different fixes. The class is a query "
                "over the element table's Tier 1 fields alone, so it is byte-exact and "
                "carries no model judgement. It lands here rather than beside the visual "
                "decision because two writers append this ledger and the earlier one runs "
                "in the work job, hours before a plan exists: a cell only assemble could "
                "fill would be dropped for every item a shard had already recorded. "
                "Counts and a class label, never article text - span_excerpt stays inside "
                "the process that cut it (CLAUDE.md section 0a). Appended at the end and "
                "nullable, so a row an earlier run wrote still reads: those runs measured "
                "nothing here and their cells stay empty."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30",
            change="Added nullable shard at the end of the row.",
            why=(
                "A run splits into as many as eight workers on eight different hosts, "
                "and they are not alike: over the seven runs in "
                "state/runtime-counters.csv on 2026-08-30, the fastest shard of a run "
                "read the prompt between 1.10x and 4.19x faster than the slowest shard "
                "of the same run. Nothing on this row said which worker produced it, so "
                "the only figure available was pooled over the run, which averages away "
                "exactly that difference - a slow day and a slow machine looked the "
                "same. state/runtime-counters.csv already carries shard at the run "
                "grain, so the same cell here is what lets the two ledgers join. "
                "Appended at the end and nullable, so a row an earlier run wrote still "
                "reads - and an empty cell means no worker claimed the row, never "
                "shard 0."
            ),
        ),
        ChangelogEntry(
            version="2026-08-28",
            change="Added nullable source_words_before_cap at the end of the row.",
            why=(
                "Nothing on this row said how long the body was before the truncation "
                "cap cut it, so a cut could only be guessed at by comparing source_words "
                "against int(extract.truncation_cap_tokens / 1.3) - a constant that moves "
                "when the cap moves, and that mislabels an article sitting exactly on the "
                "boundary. With the pre-cap count on the row beside the post-cap one, "
                "source_words_before_cap > source_words is the cut and nothing else, and "
                "the difference says by how much. Appended at the end and nullable, so a "
                "row an earlier run wrote still reads: those runs measured nothing here "
                "and their cell stays empty rather than carrying a number invented today."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change="Added the copied_source and leaked_address summarize failure codes.",
            why=(
                "Two things the project forbids outright had no code to record them. A "
                "brief published on 2026-08-26 was a 44-word summary of which every word "
                "was one unbroken copy of its 53-word source, which republishes an "
                "article body (CLAUDE.md section 0a); and nothing on the output side "
                "refused an address in our own text, so the sanitizer running before the "
                "model was the only control on Guardrail #11. Both codes are source-neutral: "
                "a copied brief and a leaked address are the model's failures, and "
                "counting either against the feed would quarantine a wire service for a "
                "defect we own. Additive and the vocabulary is closed, so a row an "
                "earlier run wrote still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25",
            change="Added the context_exceeded summarize failure code.",
            why=(
                "A prompt the server refused for length answered with an HTTP 400, and the "
                "worker recorded model_unreachable - so a running server read as a dead "
                "one and the fix was sized as an outage instead of a context budget. The "
                "code is additive and the vocabulary is closed, so a row an earlier run "
                "wrote still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T18:30",
            change=(
                "Added nullable prefill_ms, decode_ms, input_tokens, output_tokens and "
                "cached_tokens at the end of the row."
            ),
            why=(
                "This is the only ledger that carries every planned item, so it is the "
                "only place a day's model throughput can be read without keeping a "
                "runtime log. Reading the prompt and writing the summary run at "
                "different rates, and summarize_ms blends them. A rate needs its token "
                "count beside its milliseconds, so both land here. Appended at the end "
                "and nullable, so a row an earlier run wrote still reads."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:40",
            change="Added nullable fetch_ms, extract_ms and summarize_ms at the end of the row.",
            why=(
                "The console was charting stage timings from the scored subset, which never "
                "carried those columns. The per-item census is the row that exists for every "
                "planned item, so stage timings belong there."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change=(
                "Added not_prose, boilerplate, paywalled and unsupported_form codes; "
                "allowed too_short, not_prose and boilerplate as ok-row extract signals."
            ),
            why=(
                "Extract now records shape signals separately from paywall and unsupported "
                "form drops, so the item-health ledger can group each cause without free text."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Initial shape: one census row per planned item per run.",
            why=(
                "A run that publishes eight of seventeen items needs a durable row for "
                "all seventeen, or the next run and the console cannot explain the rate."
            ),
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: ItemId
    url_key: UrlKey
    canonical_url: Url
    vertical: Slug
    source_id: Slug
    stage: ItemStage
    outcome: ItemOutcome
    code: FailureCode | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    source_chars: int | None = Field(default=None, ge=0)
    source_words: int | None = Field(default=None, ge=0)
    summary_words: int | None = Field(default=None, ge=0)
    detail: ItemHealthDetail | None = Field(
        default=None,
        description="Our own one-line reason, only for unknown. Never source text.",
    )
    fetch_ms: int | None = Field(default=None, ge=0)
    extract_ms: int | None = Field(default=None, ge=0)
    summarize_ms: int | None = Field(default=None, ge=0)
    prefill_ms: int | None = Field(default=None, ge=0)
    decode_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    source_words_before_cap: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Words in the extracted body before extract.truncation_cap_tokens cut it, "
            "taken from Article.source_word_count. source_words is the same counter "
            "after the cut, so source_words_before_cap > source_words is the cut and "
            "nothing else. A count, never the text. Null before 2026-08-28."
        ),
    )
    shard: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Which worker of the run produced this row, numbered the way stages.common.shard_of "
            "numbers them. state/runtime-counters.csv carries the same number at the "
            "run grain, so a per-shard rate can be read against the machine that ran "
            "it. Null means no worker claimed the row: assemble writes the day's "
            "census from one job and cannot know which machine an item was for, and "
            "every row written before 2026-08-30 predates the column. Never read an "
            "empty cell as shard 0."
        ),
    )
    span_integrity: bool | None = Field(
        default=None,
        description=(
            "Did every element span cut its own characters out of the article text? "
            "Empty means the pass never ran, because the item carried no text. False "
            "means it ran and the table would not re-slice, which degrades this item "
            "alone. The two cells after this one are filled only when it is true."
        ),
    )
    elements_found: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Tier 1 elements the candidate pass kept for this article, after the rule "
            "that settles two passes claiming one span and after "
            "elements.max_per_article. A count, never the elements. Null before "
            "2026-09-08 and whenever span_integrity is not true."
        ),
    )
    element_class: ElementClass | None = Field(
        default=None,
        description=(
            "What the article's own numbers say it could carry: chartable, narrative, "
            "or unclassified. Three classes and not five - the other two are claims "
            "about language and have no query yet. Null on the same terms as "
            "elements_found."
        ),
    )
    model_calls: int | None = Field(
        default=None,
        ge=1,
        description=(
            "How many model calls this row records the cost of. Empty on every row "
            "written before 2026-09-12, which recorded a total and no split. It is the "
            "count of filled call slots below, so a reader of the narrower published "
            "projection can tell what the remainder it derives covers."
        ),
    )
    call_1_kind: CallKind | None = Field(
        default=None,
        description="Which call the stage made first. Empty where no split was recorded.",
    )
    call_1_prefill_ms: int | None = Field(default=None, ge=0)
    call_1_decode_ms: int | None = Field(default=None, ge=0)
    call_1_input_tokens: int | None = Field(default=None, ge=0)
    call_1_output_tokens: int | None = Field(default=None, ge=0)
    call_1_cached_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the first call reused. Zero here is the cold-slot answer and "
            "is a measurement; empty means no split was recorded at all."
        ),
    )
    call_2_kind: CallKind | None = Field(
        default=None, description="Which call the stage made second, or empty where it made one."
    )
    call_2_prefill_ms: int | None = Field(default=None, ge=0)
    call_2_decode_ms: int | None = Field(default=None, ge=0)
    call_2_input_tokens: int | None = Field(default=None, ge=0)
    call_2_output_tokens: int | None = Field(default=None, ge=0)
    call_2_cached_tokens: int | None = Field(default=None, ge=0)
    truncation_cap_tokens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "The cap that cut this row, taken from Article.truncated_at_tokens. Filled "
            "only where the cut happened, so it is non-null exactly where "
            "source_words_before_cap > source_words. It says which cap did the cutting, "
            "which the pair of word counts cannot: they say a cut happened and nothing "
            "about the setting behind it. Never re-derive this from the configured cap "
            "and the tokens-a-word ratio - both move, and the row was written under the "
            "pair in force that day. Null before 2026-09-14 and on every uncut row."
        ),
    )

    @property
    def counts_against_source(self) -> bool:
        """Does this failure count against the source in later source-health reads?"""
        return self.code is not None and self.code not in SOURCE_NEUTRAL_FAILURE_CODES

    @model_validator(mode="after")
    def _state_is_complete(self) -> Self:
        if self.stage not in TERMINAL_STAGES:
            raise ValueError("an item-health row records where an item stopped")
        if self.outcome is ItemOutcome.OK:
            if self.code not in {
                None,
                FailureCode.TOO_SHORT,
                FailureCode.NOT_PROSE,
                FailureCode.BOILERPLATE,
            }:
                raise ValueError("an ok item-health row carries only a recorded extract signal")
            if self.detail is not None:
                raise ValueError("an ok item-health row carries no detail")
        elif self.code is None:
            raise ValueError("a failed item-health row must carry a failure code")

        if self.code is not None and self.stage not in FAILURE_CODE_STAGES[self.code]:
            raise ValueError("failure code does not belong to item stage")
        if self.http_status is not None and self.stage is not ItemStage.FETCH:
            raise ValueError("http_status belongs only on fetch item-health rows")
        if self.code is FailureCode.UNKNOWN:
            if self.detail is None:
                raise ValueError("unknown item-health failure must carry detail")
        elif self.detail is not None:
            raise ValueError("detail belongs only to unknown item-health failures")
        return self

    @model_validator(mode="after")
    def _a_counted_element_was_re_sliced_first(self) -> Self:
        """The three extraction cells fill together, and only behind a passed re-slice.

        A count taken from a table that would not cut its own characters is a
        number about a string nobody holds, and it reads as a plausible integer.
        """
        counted = (self.elements_found, self.element_class)
        if (self.elements_found is None) != (self.element_class is None):
            raise ValueError("elements_found and element_class are recorded together")
        if any(cell is not None for cell in counted) and self.span_integrity is not True:
            raise ValueError("an element count is recorded only where every span re-sliced")
        return self

    @model_validator(mode="after")
    def _a_recorded_call_is_recorded_whole(self) -> Self:
        """A slot fills entirely or not at all, and the flat cells are their sum.

        The sum rule is what lets every reader that pools these cells -
        `reconcile_prefill`, `publish_day_metrics`, `publish_console_band` and the
        console's own pooled rates - stay correct with no edit of its own the day a
        second call starts being recorded. A row that recorded one call and left
        the total at that call's numbers would send all four quietly wrong.
        """
        filled = 0
        for slot in (1, 2):
            cells = [getattr(self, f"call_{slot}_{field}") for field in COST_FIELDS]
            kind = getattr(self, f"call_{slot}_kind")
            if kind is None and all(cell is None for cell in cells):
                continue
            if kind is None or any(cell is None for cell in cells):
                raise ValueError(f"call {slot} is recorded whole or not at all")
            if getattr(self, f"call_{slot}_cached_tokens") > getattr(
                self, f"call_{slot}_input_tokens"
            ):
                raise ValueError(f"call {slot} cached_tokens cannot exceed its input_tokens")
            filled += 1
        if filled == 0:
            if self.model_calls is not None:
                raise ValueError("model_calls is recorded only beside the calls it counts")
            return self
        if self.call_1_kind is None:
            raise ValueError("a second call is recorded only after a first")
        if self.model_calls != filled:
            raise ValueError("model_calls must equal the number of recorded calls")
        for field in COST_FIELDS:
            total = sum(
                getattr(self, f"call_{slot}_{field}")
                for slot in (1, 2)
                if getattr(self, f"call_{slot}_kind") is not None
            )
            if getattr(self, field) != total:
                raise ValueError(f"{field} must equal the sum over the recorded calls")
        return self

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
        # Derived, never listed: a hand-written roll of the nullable columns is one
        # a new nullable column gets left out of, and the row then refuses to parse.
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        return cls.model_validate(payload)
