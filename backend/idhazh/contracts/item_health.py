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
    LOWER_TOKEN_PATTERN,
    PRINTABLE_LINE_PATTERN,
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Slug,
    Timestamp,
    Url,
    UrlKey,
    fits_its_column,
)
from idhazh.contracts.call_cost import COST_FIELDS, CallKind
from idhazh.contracts.runtime_counters import ServerJob
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceTier

#: The two call slots, named for what each call does rather than for its turn.
#: Every per-call cell is this prefix plus the quantity, so a reader that pools
#: them needs one list and not two.
CALL_SLOTS: Final = ("label", "summary")

#: What a failure detail that folded away to nothing records, and what any other
#: recorded cell that did the same records. Neither is an empty string: a cell
#: that reached the fold had something to say, and a column with `min_length=1`
#: would refuse the emptiness and take the row reporting the fault with it.
UNSPECIFIED: Final = "unspecified failure"
UNPRINTABLE: Final = "unprintable"

#: One line of printable ASCII. A newline would break `merge=union` on the day
#: file, and a control character would break the CSV, so the shape is the
#: control rather than a promise in a docstring. The column folds its own cell,
#: so there is no door a producer can miss: a value this class cannot hold is
#: made to fit inside validation, whoever built the row.
_ONE_LINE: Final = StringConstraints(
    min_length=1, max_length=200, pattern=PRINTABLE_LINE_PATTERN
)
OneLine = Annotated[str, _ONE_LINE, fits_its_column(_ONE_LINE, absent=UNPRINTABLE)]

#: A whole exception message, which is what a person debugging a failure
#: actually needs. Longer than a label and still one line for the same reason,
#: and folding for the same reason too - the message quotes the value that was
#: refused, so a stranger's headline arrives inside it.
_DETAIL: Final = StringConstraints(
    min_length=1, max_length=2000, pattern=PRINTABLE_LINE_PATTERN
)
ItemHealthDetail = Annotated[str, _DETAIL, fits_its_column(_DETAIL, absent=UNSPECIFIED)]

#: A lowercase token the pipeline, the runtime or the config minted - a model id,
#: a finish reason, a clock name. Never fetched prose (Guardrail #11): the
#: pattern is what makes that true rather than the comment. It is not a promise
#: that the value arrives in the class either - `llama-server` mints its own
#: finish reasons and the config spells a quantisation `Q4_K_M` - so the column
#: folds rather than hoping.
_TOKEN: Final = StringConstraints(min_length=1, max_length=64, pattern=LOWER_TOKEN_PATTERN)
Token = Annotated[str, _TOKEN, fits_its_column(_TOKEN, absent=UNPRINTABLE)]

#: Headings a day file an earlier run wrote still carries, and the column each
#: one is read into now. Derived from CALL_SLOTS so a seventh cost quantity
#: cannot be added to one side and forgotten on the other.
RETIRED_CELLS: Final[Mapping[str, str]] = MappingProxyType(
    {
        f"call_{turn}_{field}": f"{slot}_{field}"
        for turn, slot in enumerate(CALL_SLOTS, start=1)
        for field in ("kind", *COST_FIELDS)
    }
)

#: Headings a day file an earlier run wrote still carries that this row no longer
#: names and that nothing replaced. A retired cell moves to another column; a
#: dropped one is gone, and the value it held is answered elsewhere - the host
#: record carries `runner_name` at job grain, which an item row reaches through
#: `job` and `shard` (`docs/reference/host-metrics.md`).
#:
#: **This is a contract, not a courtesy.** `ledger.migrate_header` refuses any
#: heading that is neither a current column nor one the reader carries, rather
#: than dropping cells silently - so a column deleted above without an entry here
#: raises on the first append to every committed day file.
DROPPED_CELLS: Final[frozenset[str]] = frozenset({"runner_name"})


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


# Declared here rather than beside the plan contract that first wrote it, for
# the reason `ElementClass` below states in full: a label a census row persists
# is declared at or below the row's own level. `run_plan` imports `article` and
# `article` imports this module, so a census column typed from `run_plan` would
# close a cycle. `run_plan.PlannedItem`, `digest_day.DigestItem` and
# `digest_view.DigestViewItem` take the type from here, so there is still one
# definition and the wire value is unchanged.
class TimeSource(StrEnum):
    """Which clock the time on an item came from.

    `rank.appeared_at` prefers the feed's own date and falls back to when we
    first saw the address. Both answers used to land in one field, so nothing
    downstream could tell them apart - and the fallback is the one a reader
    would want flagged, because it is our clock and not the publisher's.
    """

    #: The feed's own publish date.
    FEED = "feed"
    #: When this project first saw the address. The feed gave no usable date.
    FIRST_SEEN = "first_seen"
    #: Neither clock gave a time, so the item carries none.
    UNKNOWN = "unknown"

    @property
    def names_a_clock(self) -> bool:
        """`unknown` is the one member that goes with no time at all."""
        return self is not TimeSource.UNKNOWN


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
    other closed vocabularies this census row carries, because
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
    #: The item reached extract with no headline - the feed carried none, or the
    #: one it carried was whitespace. Separate from `no_text` because the fix is
    #: a different one: `no_text` sends an operator to the extractor or the page,
    #: and this sends them to the feed. Reusing `no_text` would also file a feed
    #: metadata fault under the extractor in the source-health yield.
    NO_TITLE = "no_title"
    TOO_SHORT = "too_short"
    NOT_PROSE = "not_prose"
    BOILERPLATE = "boilerplate"
    PAYWALLED = "paywalled"
    UNSUPPORTED_FORM = "unsupported_form"
    #: Nothing answered at the model's address - the process is gone, the port is
    #: closed, the connection was refused.
    MODEL_UNREACHABLE = "model_unreachable"
    #: The server answered, and the answer was an error it could not explain as
    #: a context overflow. A different morning from `model_unreachable`: that
    #: one sends an operator to the process and the port, this one to the
    #: request - the flags the entry declares, the grammar, the body. Gemma
    #: named the wrong speculation kind on 2026-09-15 and every item read as a
    #: network fault while the server was up and answering.
    MODEL_REFUSED = "model_refused"
    #: The server took the request and did not answer inside
    #: `request_timeout_minutes`. **Not the same finding as `model_unreachable`,
    #: and the difference is where an operator should look.** Unreachable sends
    #: them to the process; this sends them to the output budget, because a call
    #: that times out is almost always one decoding more tokens than the clock
    #: admits. The two were one code until 2026-09-15, because a socket timeout
    #: is an `OSError` and the handler caught the parent: 30 items across three
    #: days were filed as a dead server that was serving their neighbours fine.
    MODEL_TIMED_OUT = "model_timed_out"
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
    #: The worker ran out of its own clock before this item's model work began.
    #: Distinct from `not_attempted`, which is the run's plan never reaching the
    #: item at all: this one was planned, fetched and extracted, and the shard
    #: chose not to start work it could not finish. Naming it apart is what lets
    #: an operator tell a supply problem from a throughput problem.
    SHARD_OUT_OF_TIME = "shard_out_of_time"
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
        FailureCode.NO_TITLE: frozenset({ItemStage.EXTRACT}),
        FailureCode.TOO_SHORT: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.NOT_PROSE: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.BOILERPLATE: frozenset({ItemStage.EXTRACT, ItemStage.PUBLISH}),
        FailureCode.PAYWALLED: frozenset({ItemStage.EXTRACT}),
        FailureCode.UNSUPPORTED_FORM: frozenset({ItemStage.EXTRACT}),
        FailureCode.MODEL_UNREACHABLE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.MODEL_REFUSED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.MODEL_TIMED_OUT: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.CONTEXT_EXCEEDED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.OUTPUT_TRUNCATED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LABELS_TRUNCATED: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.BAD_SHAPE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LENGTH_OUT_OF_RANGE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.COPIED_SOURCE: frozenset({ItemStage.SUMMARIZE}),
        FailureCode.LEAKED_ADDRESS: frozenset({ItemStage.SUMMARIZE}),
        # An item the worker's own clock stopped. It is recorded at the stage it
        # was waiting to enter, which is the one it never got to run.
        FailureCode.SHARD_OUT_OF_TIME: frozenset({ItemStage.SUMMARIZE}),
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
        FailureCode.MODEL_REFUSED,
        FailureCode.MODEL_TIMED_OUT,
        FailureCode.SHARD_OUT_OF_TIME,
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
            version="2026-09-17T12:00",
            change="Retired runner_name; the host record carries it at job grain.",
            why="Nothing read the item-row copy, and a second copy is a thing that can disagree.",
        ),
        ChangelogEntry(
            version="2026-09-17",
            change="job names the workflow job whose machine took this row's readings.",
            why="Shard alone does not reach the host record: more than one job spells shard 0.",
        ),
        ChangelogEntry(
            version="2026-09-16T12:30",
            change="The three slot columns carry the item's first call.",
            why="All three were declared with no producer; the pinned build reports them.",
        ),
        ChangelogEntry(
            version="2026-09-16",
            change="label_ms and summary_ms are a stopwatch; both finish reasons may be null.",
            why="A clock that was its two neighbours summed could not see a wait.",
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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
        description=(
            "Our own one-line reason, on any failed row. Never source text "
            "(Guardrail #11). Two hundred characters used to be the cap and it cut "
            "the exception message off before the part that said what broke, so a "
            "person debugging a failure had to reproduce it to read it."
        ),
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
    job: ServerJob | None = Field(
        default=None,
        description=(
            "Which workflow job's machine took this row's readings - never which job "
            "wrote the row. With `shard` this is the whole of `HOST_FINGERPRINT_KEY`, "
            "so an item resolves to exactly one host record. Null on the same terms as "
            "`shard`: assemble writes the day's census and cannot know whose machine an "
            "item ran on, and every row written before this column predates it."
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
    label_kind: CallKind | None = Field(
        default=None,
        description="Which call the stage made first. Empty where no split was recorded.",
    )
    label_prefill_ms: int | None = Field(default=None, ge=0)
    label_decode_ms: int | None = Field(default=None, ge=0)
    label_input_tokens: int | None = Field(default=None, ge=0)
    label_output_tokens: int | None = Field(default=None, ge=0)
    label_cached_tokens: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Prompt tokens the first call reused. Zero here is the cold-slot answer and "
            "is a measurement; empty means no split was recorded at all."
        ),
    )
    summary_kind: CallKind | None = Field(
        default=None, description="Which call the stage made second, or empty where it made one."
    )
    summary_prefill_ms: int | None = Field(default=None, ge=0)
    summary_decode_ms: int | None = Field(default=None, ge=0)
    summary_input_tokens: int | None = Field(default=None, ge=0)
    summary_output_tokens: int | None = Field(default=None, ge=0)
    summary_cached_tokens: int | None = Field(default=None, ge=0)
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

    # --- Why this item was in the run at all ---------------------------------
    #
    # The ranker computes each of these and then throws all but the total away.
    # Recorded here, a person can ask which term carried an item onto the page
    # and what the runner-up was; without them the only honest answer to "why
    # did this publish" is "the score said so", which is not an answer.
    selection_score: float | None = Field(
        default=None,
        description=(
            "The total the ranker ordered this item by. Empty on a row written "
            "before 2026-09-15 and on any item the ranker never scored."
        ),
    )
    authority_score: float | None = Field(
        default=None, description="The source-authority term of selection_score."
    )
    tier_score: float | None = Field(
        default=None, description="The tier term of selection_score."
    )
    feed_weight: float | None = Field(
        default=None, description="The configured weight of the feed this item came from."
    )
    feed_reliability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "The feed's own recorded reliability at the moment of the run, 0 to 1. "
            "Read from feed health, so a later read of feed health cannot answer "
            "what the ranker actually used on the day."
        ),
    )
    lens_bonus: float | None = Field(
        default=None, description="The lens term of selection_score."
    )
    recency_bonus: float | None = Field(
        default=None, description="The recency term of selection_score."
    )
    carriage_step: float | None = Field(
        default=None, description="The carriage term of selection_score."
    )
    watchlist_bonus: float | None = Field(
        default=None, description="The watchlist term of selection_score."
    )
    carried_by: int | None = Field(
        default=None,
        ge=0,
        description="How many runs have carried this item forward without publishing it.",
    )
    watchlist_hit: bool | None = Field(
        default=None, description="Did a watchlist entry match this item?"
    )
    on_front_page: bool | None = Field(
        default=None, description="Did this item reach the published front page?"
    )
    tier: SourceTier | None = Field(
        default=None, description="The source's tier at the moment of the run."
    )
    source_form: SourceForm | None = Field(
        default=None, description="The source's form at the moment of the run."
    )
    published_at: Timestamp | None = Field(
        default=None,
        description="The time the item carries, from whichever clock time_source names.",
    )
    time_source: TimeSource | None = Field(
        default=None,
        description=(
            "Which clock published_at came from - feed, first_seen or unknown. A "
            "closed set the pipeline mints, so the column is the enum and a "
            "producer selects a member rather than spelling one. A clock name "
            "nobody declared is refused here rather than folded into a token, "
            "which is the difference between a value this project can act on and "
            "one it can only read. Null where no run recorded the choice."
        ),
    )

    # --- Where the time went -------------------------------------------------
    #
    # `summarize_ms` already said how long the model stage took whole. A stage
    # that got slower says nothing about which of its parts did, so these split
    # it, and `stage_gap_ms` holds what none of the named parts claimed.
    item_started_at: Timestamp | None = Field(
        default=None, description="When the worker picked this item up."
    )
    item_ended_at: Timestamp | None = Field(
        default=None, description="When the worker wrote this row."
    )
    item_index: int | None = Field(
        default=None,
        ge=0,
        description=(
            "This item's position inside its shard, counting from zero. It is what "
            "makes a cold first item legible as a cold first item rather than as a "
            "slow one, because the prefix cache is empty only at index 0."
        ),
    )
    shard_item_count: int | None = Field(
        default=None, ge=0, description="How many items that shard was given."
    )
    queue_wait_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How long the item waited before its worker started it - its own fetch "
            "and extract subtracted, because both are work rather than waiting. "
            "Discounted from item_total_ms, so a shard's items do not each count "
            "the queue ahead of them."
        ),
    )
    fetch_connect_ms: int | None = Field(
        default=None, ge=0, description="The connect half of fetch_ms."
    )
    fetch_ttfb_ms: int | None = Field(
        default=None, ge=0, description="Time to the first byte of the response body."
    )
    robots_ms: int | None = Field(
        default=None, ge=0, description="Time spent fetching or waiting on robots.txt."
    )
    retry_count: int | None = Field(
        default=None, ge=0, description="How many times the fetch was retried."
    )
    retry_total_ms: int | None = Field(
        default=None, ge=0, description="Total wall time spent inside retries and their backoff."
    )
    label_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall time of the label call: our own stopwatch around the request, so the "
            "wait is inside it. Subtract label_prefill_ms and label_decode_ms to get "
            "what the server did not claim for itself - transport, and any queue."
        ),
    )
    summary_ms: int | None = Field(
        default=None,
        ge=0,
        description="Wall time of the summarize-and-plan call, on the same stopwatch.",
    )
    visual_plan_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall time attributed to producing the visual plan. The plan is decoded "
            "inside the summarize-and-plan call, so this is an apportionment and not "
            "a separate clock - visual_plan_ms_is_estimate says which."
        ),
    )
    visual_plan_ms_is_estimate: bool | None = Field(
        default=None,
        description=(
            "True where visual_plan_ms was apportioned out of the second call rather "
            "than timed on its own. An estimate that does not say it is one is the "
            "failure this column exists to prevent (Guardrail #10)."
        ),
    )
    faithfulness_ms: int | None = Field(
        default=None, ge=0, description="Wall time of the model-free faithfulness scorers."
    )
    model_wait_ms: int | None = Field(
        default=None,
        ge=0,
        description="Time the item spent waiting on the model server rather than being served.",
    )
    item_total_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "What the item cost, from item_started_at to item_ended_at with "
            "queue_wait_ms taken out. The stage fetches every item and then runs the "
            "model over them in a different order, so the raw wall clock counts the "
            "whole queue ahead of each item and the column summed to the shard's own "
            "duration once per item."
        ),
    )
    stage_gap_ms: int | None = Field(
        default=None,
        description=(
            "item_total_ms minus every named stage. **This is the one column that can "
            "catch a regression in a stage nobody named**, which is why it is recorded "
            "rather than derived at read time by a reader who would have to know the "
            "list. It is signed on purpose: a negative value means two named stages "
            "overlapped, or two clocks disagreed, and silently clamping it to zero "
            "would hide exactly that."
        ),
    )

    # --- What the cache and the decoder did ----------------------------------
    visual_plan_tokens_written: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Output tokens of the second call that belong to the visual plan rather "
            "than to the summary. Null where the run asked for no plan."
        ),
    )
    label_cache_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description=(
            "label_cached_tokens as a percentage of label_input_tokens. Recorded "
            "rather than derived so a reader pooling rows does not have to weight "
            "the ratio itself and get it wrong."
        ),
    )
    summary_cache_pct: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="summary_cached_tokens as a percentage of summary_input_tokens.",
    )
    slot_id: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Which llama-server prefix-cache slot served this item, from id_slot on the "
            "reply to its FIRST model call. The row holds one set of these three columns "
            "for a stage that makes two calls, and the first call is the only one whose "
            "slot was last touched by the item before this one. Null where the reply "
            "named no slot, which is not the same as slot 0."
        ),
    )
    kv_tokens_at_start: int | None = Field(
        default=None,
        ge=0,
        description=(
            "What that slot held once the item's first call had been prefilled, from "
            "tokens_cached on the same reply. It is where the item's second call starts "
            "from, and then the next item. label_cached_tokens is the other half of the "
            "pair and answers the opposite question: what the call read back out."
        ),
    )
    prefix_shared_with_previous: bool | None = Field(
        default=None,
        description=(
            "Did the item's first call read anything at all out of the slot? Taken from "
            "the same timings.cache_n that label_cached_tokens is, so the boolean and "
            "the count cannot disagree about one reply. The second call is excluded on "
            "purpose: its prompt IS the first one's extended, so it reuses a prefix on "
            "every row and says nothing about the item before it. Null where the reply "
            "carried no cache_n at all."
        ),
    )
    label_prefill_tokens_per_s: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Prefill throughput of the label call, over the tokens the server really "
            "evaluated - label_input_tokens minus label_cached_tokens. Counting the "
            "cached ones as work makes this and label_cache_pct the same number "
            "twice, and reads as a fast server rather than as a cache hit."
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
            "server really evaluated. This call reuses the label call's prompt almost "
            "whole, so the two readings differ by two orders of magnitude: on "
            "2026-09-14 one item read 787 tokens a second over the whole prompt and "
            "8.4 over the 52 tokens that were new."
        ),
    )
    summary_decode_tokens_per_s: float | None = Field(
        default=None, ge=0.0, description="Decode throughput of the summarize-and-plan call."
    )
    label_finish_reason: Token | None = Field(
        default=None,
        description=(
            "Why the label decode stopped, as the server reported it - stop, length, "
            "and whatever else the runtime mints. A token and not an enum: the "
            "vocabulary belongs to llama-server rather than to this project, and a "
            "row that could not be written because the runtime added a reason would "
            "lose the whole item over a label. Null where the reply named no reason "
            "at all, which is not the same fact as a clean stop."
        ),
    )
    summary_finish_reason: Token | None = Field(
        default=None, description="Why the summarize-and-plan decode stopped, on the same terms."
    )
    recovered: bool | None = Field(
        default=None,
        description=(
            "Did a cut reply have to be recovered before it parsed? A run where this "
            "turns true across many items is a budget that no longer fits."
        ),
    )

    # --- What it ran on ------------------------------------------------------
    #
    # A throughput number with no machine beside it is not a measurement
    # (Guardrail #10). These are what let a row from a slower runner be read as
    # a slower runner rather than as a regression.
    #
    # `runner_name` was here until 2026-09-17 and is in `DROPPED_CELLS`. The host
    # record carries it once a job rather than once an item, and `job` with
    # `shard` is what reaches that record - a second copy of it here was a thing
    # that could disagree. `cpu_model` stays, and its reason is the one thing
    # that separates the two: it crosses to the browser as
    # `PublicTelemetryRow.cpu_model`, and a browser cannot join.
    cpu_model: OneLine | None = Field(
        default=None, description="The CPU the runner reported, verbatim."
    )
    cpu_busy_pct: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Mean CPU busy over the item."
    )
    cpu_busy_max: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Peak CPU busy over the item."
    )
    cpu_busy_min: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Trough CPU busy over the item."
    )
    load_1m: float | None = Field(
        default=None, ge=0.0, description="One-minute load average when the item ended."
    )
    llama_rss_bytes: int | None = Field(
        default=None, ge=0, description="Resident memory of the model server when the item ended."
    )
    llama_rss_peak_bytes: int | None = Field(
        default=None, ge=0, description="Peak resident memory of the model server over the item."
    )
    python_rss_bytes: int | None = Field(
        default=None, ge=0, description="Resident memory of the worker process when the item ended."
    )
    cgroup_peak_bytes: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Peak memory the job's cgroup reported. This is the number the runner "
            "kills the job over, so it is the one that answers whether a bigger "
            "model would have fitted (Guardrail #2)."
        ),
    )

    # --- What it ran with ----------------------------------------------------
    #
    # A row that records what a knob produced without recording the knob cannot
    # answer the only question worth asking of an archive: did changing this
    # help? Config is committed, but a run reads the config of its own day, and
    # git history is not a join key.
    model_id: Token | None = Field(
        default=None, description="The model this run summarised with."
    )
    model_quantisation: Token | None = Field(
        default=None, description="The quantisation of those weights."
    )
    n_ctx_configured: int | None = Field(
        default=None, ge=1, description="The context window the server was started with."
    )
    n_parallel: int | None = Field(
        default=None, ge=1, description="How many prefix-cache slots the server was started with."
    )
    n_threads: int | None = Field(default=None, ge=1, description="Threads the server was given.")
    n_batch: int | None = Field(default=None, ge=1, description="The server's prefill batch size.")
    max_output_tokens: int | None = Field(
        default=None, ge=1, description="The configured ceiling on any one decode."
    )
    label_budget_tokens: int | None = Field(
        default=None, ge=1, description="The output budget the label call ran under."
    )
    summary_budget_tokens: int | None = Field(
        default=None, ge=1, description="The output budget the summarize-and-plan call ran under."
    )
    run_visual_decision: bool | None = Field(
        default=None, description="Did this run ask the second call for a visual plan?"
    )
    temperature: float | None = Field(
        default=None, ge=0.0, description="The sampling temperature both calls ran at."
    )

    # --- What broke --------------------------------------------------------
    failed_field: OneLine | None = Field(
        default=None,
        description=(
            "The field a schema refusal named, where the failure was a refusal. Our "
            "own field name and never fetched text (Guardrail #11)."
        ),
    )
    failed_rule: OneLine | None = Field(
        default=None, description="The rule that refused it, named by our own validator."
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
        if self.code is FailureCode.UNKNOWN and self.detail is None:
            raise ValueError("unknown item-health failure must carry detail")
        return self

    @model_validator(mode="after")
    def _a_named_job_names_a_worker_too(self) -> Self:
        """`job` implies `shard`, and deliberately not the other way round.

        The pair is `HOST_FINGERPRINT_KEY` minus the date and the run, so a job
        with no shard points at no host record - it is half a key, and half a key
        resolves to every shard that job ran.

        **The converse is not a rule, and that is the load-bearing half.** Every
        row written before this column carries a shard and no job; the archive is
        read back through `from_csv_row` on the next append
        (`ledger.append_item_health`), so `job iff shard` would refuse the whole
        of it on the first run after this lands.
        """
        if self.job is not None and self.shard is None:
            raise ValueError("a job on an item-health row names a shard as well")
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
        for slot in CALL_SLOTS:
            cells = [getattr(self, f"{slot}_{field}") for field in COST_FIELDS]
            kind = getattr(self, f"{slot}_kind")
            if kind is None and all(cell is None for cell in cells):
                continue
            if kind is None or any(cell is None for cell in cells):
                raise ValueError(f"the {slot} call is recorded whole or not at all")
            if getattr(self, f"{slot}_cached_tokens") > getattr(self, f"{slot}_input_tokens"):
                raise ValueError(f"{slot}_cached_tokens cannot exceed {slot}_input_tokens")
            filled += 1
        if filled == 0:
            if self.model_calls is not None:
                raise ValueError("model_calls is recorded only beside the calls it counts")
            return self
        if self.label_kind is None:
            raise ValueError("a second call is recorded only after a first")
        if self.model_calls != filled:
            raise ValueError("model_calls must equal the number of recorded calls")
        for field in COST_FIELDS:
            total = sum(
                getattr(self, f"{slot}_{field}")
                for slot in CALL_SLOTS
                if getattr(self, f"{slot}_kind") is not None
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
        """The inverse. An empty cell is an absent value, never the empty string.

        **A cell under a retired heading is read into the column that replaced
        it.** Every day file an earlier run wrote heads its six first-call cells
        `call_1_*` and its six second-call cells `call_2_*`, and those files are
        the archive - a reader that cannot open them has not migrated the
        ledger, it has abandoned it. The map is one direction only: nothing
        writes a retired heading again.
        """
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for retired, current in RETIRED_CELLS.items():
            if payload[current] == "":
                payload[current] = row.get(retired, "")
        # Derived, never listed: a hand-written roll of the nullable columns is one
        # a new nullable column gets left out of, and the row then refuses to parse.
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        return cls.model_validate(payload)
