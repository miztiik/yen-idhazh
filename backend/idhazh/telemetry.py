"""The structured-event envelope, the span tree, and one item's terminal state.

A log line and a span are evidence that something happened; the item-health row
is the record of it. All three shapes live here so no stage builds one by hand.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Protocol

from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.feed_health import RobotsOutcome
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.fetch import BLOCKED_REASONS, ROBOTS_REFUSALS
from idhazh.sanitize import sanitize

_FORMULA_PREFIXES: Final = ("=", "+", "-", "@", "\t", "\r")
_HTTP_DETAIL = re.compile(r"^HTTP (?P<status>[0-9]{3})$")

#: Which typed failure each robots refusal is. The reasons are `fetch`'s own
#: strings rather than copies, so a reworded one cannot quietly become
#: `unknown` here while every gate stays green.
_ROBOTS_FAILURE: Final[dict[str, FailureCode]] = {
    ROBOTS_REFUSALS[RobotsOutcome.DENIED]: FailureCode.ROBOTS_DENIED,
    ROBOTS_REFUSALS[RobotsOutcome.UNREACHABLE]: FailureCode.ROBOTS_UNREACHABLE,
}

#: Envelope version. It rides every record so a reader can evolve its parsing.
ENVELOPE_VERSION: Final = "1"

#: Extract signals that end an item without failing it. The article is kept, the
#: model is never asked, and the row publishes as `ok` carrying the signal.
DEGRADED_BUT_DONE: Final = frozenset(
    {FailureCode.TOO_SHORT, FailureCode.NOT_PROSE, FailureCode.BOILERPLATE}
)


class EventName(StrEnum):
    """Every event name a stage may emit.

    One member, because one stage emits. A name with no emitter cannot be told
    apart from one that fires, so a name is added here in the commit that emits
    it.
    """

    ITEM_SUMMARIZE_FAILED = "item.summarize.failed"


class EventLevel(StrEnum):
    """Severity, as the envelope spells it."""

    WARNING = "warning"


def event(
    *,
    ts: str,
    src: ItemStage,
    run: str | None,
    name: EventName,
    level: EventLevel,
    ctx: Mapping[str, str | None],
    data: Mapping[str, str | None],
) -> str:
    """Serialize one event as the single line a stage logs.

    `ctx` and `data` stay open because their keys vary by event. The envelope
    around them does not, and building it here rather than at the call site is
    what stops a second emitter shipping a second shape.
    """
    return json.dumps(
        {
            "ts": ts,
            "src": src.value,
            "v": ENVELOPE_VERSION,
            "run": run,
            "name": name.value,
            "level": level.value,
            "ctx": dict(ctx),
            "data": dict(data),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


# --- the span tree -----------------------------------------------------------
#
# What a span buys that a ledger column does not: a start instant, a parent, and
# a step too small to earn a column of its own. `fetch_ms`, `extract_ms` and
# `summarize_ms` already split a stage three ways; what they cannot say is that
# the robots read inside the fetch took most of it, or that the model answered
# before our own parsing spent another second on the reply.
#
# Everything below builds one plain payload per span. Langfuse is a sink for
# that payload and never its shape, which is what keeps an optional package out
# of the default install, out of `mypy`'s way, and out of the guard's way: the
# guard reads the same records the host would have received.


#: The longest a span attribute value may be. One SHA-256 digest is 64
#: characters, and nothing an attribute carries is wider - a value that needs
#: more room is prose, and prose does not leave the process (Rule #11,
#: CLAUDE.md section 0a).
MAX_ATTRIBUTE_CHARS: Final = 64

#: What a string attribute may be made of: lowercase, no whitespace, no sentence
#: punctuation. A digest, a slug, an enum value and an id all look like this and
#: a sentence never does.
_ATTRIBUTE_TOKEN: Final = re.compile(r"^[a-z0-9][a-z0-9._:+-]*$")


class SpanKind(StrEnum):
    """A span, or the model-call subtype a tracing tool draws differently."""

    SPAN = "span"
    GENERATION = "generation"


class SpanName(StrEnum):
    """Every span this pipeline opens.

    Five are the stages a ledger row already splits: `fetch`, `extract`,
    `summarize`, `score` and `visual_planner`. `item` is what they hang under.
    The other five are the reason this exists at all - `robots` nests inside
    `fetch`, `tag` nests inside `extract`, and `render_prompt`, `model_call` and
    `parse_reply` nest inside `summarize` in that order. Each of those is a step
    no column separates and no column should: a column per sub-step is a wider
    ledger for a question asked once a quarter.
    """

    ITEM = "item"
    FETCH = "fetch"
    ROBOTS = "robots"
    EXTRACT = "extract"
    TAG = "tag"
    SUMMARIZE = "summarize"
    RENDER_PROMPT = "render_prompt"
    MODEL_CALL = "model_call"
    PARSE_REPLY = "parse_reply"
    SCORE = "score"
    VISUAL_PLANNER = "visual_planner"


class AttrKey(StrEnum):
    """Every attribute name a span may carry, and the whole list of them.

    Closed on purpose, and this is the control the row exists for. Every tracing
    SDK offers a free-text `input` and `output` pair, fills them with the whole
    prompt and the whole completion by default, and ships them to a host. There
    is no such key here and there is no way to add one at a call site: a name
    absent from this enum cannot be recorded.

    A name with no setter is added in the commit that sets it, the same rule
    `EventName` keeps and for the same reason - a key nothing writes cannot be
    told apart from one that is always empty.

    Note what is missing beside the text. No `url`, no `title`, no
    `failure_detail`. A URL is not article text, but it is the address of it,
    and an attribute list is not the place to relitigate what counts as
    republishing.
    """

    RUN_ID = "run_id"
    SHARD = "shard"
    ITEM_ID = "item_id"
    URL_KEY = "url_key"
    SOURCE_ID = "source_id"
    VERTICAL = "vertical"
    OUTCOME = "outcome"
    STATUS = "status"
    FAILURE_CODE = "failure_code"
    HTTP_STATUS = "http_status"
    BODY_BYTES = "body_bytes"
    BODY_TRUNCATED = "body_truncated"
    ROBOTS_OUTCOME = "robots_outcome"
    ROBOTS_CACHED = "robots_cached"
    SOURCE_DIGEST = "source_digest"
    SOURCE_CHARS = "source_chars"
    SOURCE_WORDS = "source_words"
    SOURCE_WORDS_BEFORE_CAP = "source_words_before_cap"
    SOURCE_TOKENS = "source_tokens"
    TRUNCATED = "truncated"
    LENS_COUNT = "lens_count"
    ENTITY_COUNT = "entity_count"
    EVENT_COUNT = "event_count"
    MODEL_ID = "model_id"
    PROMPT_DIGEST = "prompt_digest"
    PROMPT_CHARS = "prompt_chars"
    OUTPUT_DIGEST = "output_digest"
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    CACHED_TOKENS = "cached_tokens"
    PREFILL_MS = "prefill_ms"
    DECODE_MS = "decode_ms"
    HIT_THE_BUDGET = "hit_the_budget"
    REASONED = "reasoned"
    SUMMARY_WORDS = "summary_words"
    KEY_POINTS = "key_points"
    BAND = "band"
    VISUAL_KIND = "visual_kind"
    VISUAL_STATE = "visual_state"
    DRAFTED_CHART = "drafted_chart"
    MODEL_ASKED = "model_asked"


AttrValue = str | int | float | bool


def attribute(key: AttrKey, value: AttrValue) -> AttrValue:
    """Refuse anything that is not a digest, a count, a flag or a closed name.

    The second control, not the first. The first is that every value a span
    carries is read off a typed payload - a digest, an int, an enum member - so
    prose has no route in. This is what makes that structural instead of a habit
    somebody has to keep.

    It raises rather than dropping the value. Everything handed to it is built
    by our own code out of a validated payload, so a refusal is a programming
    error and not something a run can produce; and article text reaching a third
    party is not a thing to degrade quietly around.
    """
    if isinstance(value, bool | int | float):
        return value
    if len(value) > MAX_ATTRIBUTE_CHARS:
        raise ValueError(
            f"span attribute {key.value} is {len(value)} characters, "
            f"over the {MAX_ATTRIBUTE_CHARS} a digest needs"
        )
    if _ATTRIBUTE_TOKEN.match(value) is None:
        raise ValueError(f"span attribute {key.value} is not digest-, name- or id-shaped")
    return value


@dataclass(frozen=True, slots=True)
class Span:
    """One finished span, in the shape every sink receives it.

    `started_at` and `duration_ms` are fields rather than attributes because
    they are what a span IS. Keeping them out of the bag also lets the bag hold
    one rule - lowercase, unspaced, 64 characters - that an ISO timestamp would
    have forced an exception into.
    """

    trace_id: str
    span_id: str
    parent_id: str | None
    name: SpanName
    kind: SpanKind
    started_at: str
    duration_ms: int
    attributes: Mapping[str, AttrValue]

    def as_record(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name.value,
            "kind": self.kind.value,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "attributes": dict(self.attributes),
        }


class SpanSink(Protocol):
    """Where finished spans go. One line of the pipeline knows which one."""

    def emit(self, span: Span) -> None: ...

    def flush(self) -> None: ...


class NullSink:
    """What the pipeline traces into when tracing is off.

    A sink rather than a branch at every call site. The stages open their spans
    unconditionally and this throws them away, so the code path a developer
    reads with tracing on is the code path CI runs with it off - which is the
    only way the off case stays correct.
    """

    def emit(self, span: Span) -> None:
        return None

    def flush(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class FileSink:
    """One JSON line per span, under `backend/var/`, and the default.

    Owner decision, 2026-08-30: a file is where a span goes unless somebody
    names a host. So a developer gets the tree with no account, no key and no
    third party, CI needs no secret, and the pipeline is correct with nothing
    reachable.
    """

    path: Path

    def emit(self, span: Span) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(span.as_record(), sort_keys=True, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def flush(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class FanOut:
    """Every sink gets every span. A host is added to the file, never instead of it."""

    sinks: Sequence[SpanSink]

    def emit(self, span: Span) -> None:
        for sink in self.sinks:
            sink.emit(span)

    def flush(self) -> None:
        for sink in self.sinks:
            sink.flush()


class OpenSpan:
    """A span that has started and has not finished.

    `set` is the only way to record an attribute, and it validates. A caller
    that has nothing to say passes `None` and nothing is written - an attribute
    absent reads as unknown, where a zero would read as measured (the same rule
    the ledgers already keep).
    """

    __slots__ = ("_attributes", "span_id")

    def __init__(self, span_id: str) -> None:
        self.span_id = span_id
        self._attributes: dict[str, AttrValue] = {}

    def set(self, key: AttrKey, value: AttrValue | None) -> None:
        if value is None:
            return
        self._attributes[key.value] = attribute(key, value)

    def attributes(self) -> Mapping[str, AttrValue]:
        return dict(self._attributes)


class Tracer:
    """The sink, and whichever spans are open above the one being started.

    Not a global and not ambient to the process. A tracer is an argument, the
    way the fetcher and the clock are arguments, so a test drives it with no
    network and no process state to reset between cases (Rule #7).

    It carries the open stack because the nesting a span buys has to survive a
    seam. The robots read is four call frames below `stage_work`, behind the
    `Fetcher` type the whole pipeline passes around, and a parent it cannot see
    is a parent it cannot record.

    Spans close in the order they opened, because the pipeline is one item at a
    time inside one shard. That stack is the whole of the nesting machinery.
    """

    __slots__ = ("_clock", "_now", "_opened", "_sink", "_stack", "_trace_id")

    def __init__(
        self,
        *,
        sink: SpanSink,
        now: Callable[[], str],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sink = sink
        self._now = now
        self._clock = clock
        self._stack: list[str] = []
        self._opened = 0
        self._trace_id = "unattributed"

    @contextmanager
    def trace(self, trace_id: str) -> Iterator[None]:
        """One item's tree. Every span opened inside it carries this id.

        The span counter is NOT reset, so an id is unique for the life of the
        tracer. The work stage touches an item twice - it fetches every item,
        then summarizes them in a different order - so one item's tree is opened
        twice, and a counter that restarted would give two different spans the
        same name inside one trace.
        """
        previous = self._trace_id
        self._trace_id = trace_id
        try:
            yield None
        finally:
            self._trace_id = previous

    @contextmanager
    def span(self, name: SpanName, *, kind: SpanKind = SpanKind.SPAN) -> Iterator[OpenSpan]:
        self._opened += 1
        span_id = f"{name.value}-{self._opened:03d}"
        parent_id = self._stack[-1] if self._stack else None
        started_at = self._now()
        started = self._clock()
        open_span = OpenSpan(span_id)
        self._stack.append(span_id)
        try:
            yield open_span
        finally:
            self._stack.pop()
            self._sink.emit(
                Span(
                    trace_id=self._trace_id,
                    span_id=span_id,
                    parent_id=parent_id,
                    name=name,
                    kind=kind,
                    started_at=started_at,
                    duration_ms=int((self._clock() - started) * 1000),
                    attributes=open_span.attributes(),
                )
            )

    def generation(self, name: SpanName = SpanName.MODEL_CALL) -> AbstractContextManager[OpenSpan]:
        """The model call.

        A generation and not three spans. llama-server reports prefill and
        decode as totals in the reply, after the call returned, so neither can
        be wrapped in anything - they land as attributes. Nesting a span around
        a duration that was reported retrospectively would draw a shape nobody
        measured.
        """
        return self.span(name, kind=SpanKind.GENERATION)

    def flush(self) -> None:
        self._sink.flush()


def item_attributes(span: OpenSpan, item: PlannedItem, *, run_id: str, shard: int) -> None:
    """Which item a tree is about, in ids and digests and nothing else.

    `item.title` and `item.canonical_url` are the two fields on a plan entry
    that came off somebody else's page, and neither is reachable from here.
    `url_key` is the SHA-256 of the address and is what identifies the item
    without naming it.
    """
    span.set(AttrKey.RUN_ID, run_id)
    span.set(AttrKey.SHARD, shard)
    span.set(AttrKey.ITEM_ID, item.item_id)
    span.set(AttrKey.URL_KEY, item.url_key)
    span.set(AttrKey.SOURCE_ID, item.source_id)
    span.set(AttrKey.VERTICAL, item.vertical)


def article_attributes(span: OpenSpan, article: Article, *, source_digest: str | None) -> None:
    """What an extract span records about an article: sizes and digests, no text.

    One function, so the shape cannot drift between the worker's span and a
    test's. `article.title`, `article.text` and `article.failure_detail` are the
    three fields on this payload that hold source words, and none of them is
    reachable from here.
    """
    span.set(AttrKey.STATUS, article.status.value)
    failure = article.failure_code
    span.set(AttrKey.FAILURE_CODE, None if failure is None else failure.value)
    span.set(AttrKey.SOURCE_DIGEST, source_digest)
    span.set(AttrKey.SOURCE_CHARS, len(article.text or ""))
    span.set(AttrKey.SOURCE_WORDS, article.word_count)
    span.set(AttrKey.SOURCE_WORDS_BEFORE_CAP, article.source_word_count)
    span.set(AttrKey.SOURCE_TOKENS, article.token_count)
    span.set(AttrKey.TRUNCATED, article.truncated)


def summary_attributes(span: OpenSpan, summary: Summary) -> None:
    """What a summarize span records about a reply: counts and digests, no words."""
    span.set(AttrKey.STATUS, summary.status.value)
    failure = summary.failure_code
    span.set(AttrKey.FAILURE_CODE, None if failure is None else failure.value)
    span.set(AttrKey.OUTPUT_DIGEST, summary.output_digest)
    span.set(AttrKey.SUMMARY_WORDS, len((summary.summary or "").split()))
    span.set(AttrKey.KEY_POINTS, len(summary.key_points))


def refuse_text(*, data: Any) -> None:
    """The SDK's own escape hatch, wired shut.

    Langfuse calls this on whatever is about to sit in `input` and `output`
    before it exports. We never fill those fields, so this should never have
    anything to refuse - which is exactly why it is worth wiring: it is the one
    control that still holds if a future SDK version, or an instrumentation
    somebody enables, starts filling them behind our back.
    """
    return None


def langfuse_sink(*, host: str, public_key: str, secret_key: str) -> SpanSink | None:
    """A host, when an operator names one in the environment, or nothing.

    Opt-in and never a default (owner decision, 2026-08-30). No secret in CI, no
    third party receiving span data on an ordinary day, and a pipeline that is
    correct with nothing reachable.

    The import is inside the function because `langfuse` is an optional extra: a
    default install does not have it, and a module-level import would make the
    package required for a feature that is off. An absent package degrades to
    the file sink rather than stopping a run (section 1a) - a job whose purpose
    is to publish may not fail on an observability dependency.
    """
    try:
        from langfuse import Langfuse
    except ImportError:
        return None
    return _LangfuseSink(
        client=Langfuse(
            host=host,
            public_key=public_key,
            secret_key=secret_key,
            mask=refuse_text,
        )
    )


@dataclass(frozen=True, slots=True)
class _LangfuseSink:
    """Our span payload, handed to the client one finished observation at a time.

    **`input` and `output` are passed explicitly as `None`.** They are the SDK's
    free-text fields, they are what its own decorator fills with the prompt and
    the completion, and this repository is public - so they are named here and
    set to nothing rather than left to a default (Rule #11, CLAUDE.md section
    0a). Everything we do send rides in `metadata`, which holds the same
    validated attribute bag the file sink writes and the guard reads.

    Two things it does NOT do, both measured against Langfuse 4.14.4 on
    2026-08-30 rather than assumed:

    - **It does not reproduce the nesting on the host.** A child span closes
      before its parent, so at the moment we hand a child over its parent has no
      handle yet, and the SDK generates its own span ids. Matching them would
      mean handing our tracer to `start_as_current_observation`, which is a
      second code path for the sink that is not opt-in. So the file keeps the
      exact tree and the host gets one trace per item with the parent named on
      each observation.
    - **It does not send a completion start time.** llama-server's reply carries
      prefill and decode as totals and no first-token instant, so the field
      would be a number we invented.
    """

    client: Any

    def emit(self, span: Span) -> None:
        record = span.as_record()
        attributes = dict(span.attributes)
        handle = self.client.start_observation(
            trace_context=_trace_context(self.client, span.trace_id),
            name=span.name.value,
            as_type=span.kind.value,
            input=None,
            output=None,
            metadata=record,
            model=_string_attribute(attributes, AttrKey.MODEL_ID),
            usage_details=_usage(attributes),
        )
        handle.end()

    def flush(self) -> None:
        self.client.flush()


def _trace_context(client: Any, trace_id: str) -> Any:
    """Group one item's observations, under an id the SDK will accept.

    Ours reads `<run>-<item>`; an OpenTelemetry trace id is 32 hex characters.
    `create_trace_id` is the SDK's own deterministic derivation, so the same
    item on the same run lands in the same trace without us inventing a second
    id scheme.
    """
    from langfuse.types import TraceContext

    return TraceContext(trace_id=client.create_trace_id(seed=trace_id))


def _string_attribute(attributes: Mapping[str, AttrValue], key: AttrKey) -> str | None:
    value = attributes.get(key.value)
    return value if isinstance(value, str) else None


def _usage(attributes: Mapping[str, AttrValue]) -> dict[str, int] | None:
    """Token counts, in the field Langfuse counts them in. Integers, never text."""
    counted = {
        "input": attributes.get(AttrKey.INPUT_TOKENS.value),
        "output": attributes.get(AttrKey.OUTPUT_TOKENS.value),
    }
    usage = {name: value for name, value in counted.items() if isinstance(value, int)}
    return usage or None


def is_final(article: Article | None, summary: Summary | None) -> bool:
    """Has this item stopped, or is a payload simply not written yet?

    `classify_item` answers for every planned item, including ones nothing ever
    touched, because assemble needs the denominator in the same file as the
    count. A worker recording rows while the run is still going needs the
    narrower question. It writes an article payload for every item it reaches and
    a summary payload for every item that got as far as the model, so an article
    the extractor accepted with no summary beside it means the shard stopped
    mid-item - and a row filed then would record an interruption as a failure
    that no later run can correct.
    """
    if article is None:
        return False
    if article.status is not ArticleStatus.OK:
        return True
    if article.failure_code in DEGRADED_BUT_DONE:
        return True
    return summary is not None


def detail_cell(text: str) -> str:
    """Sanitize an unknown-failure detail for a CSV cell."""
    cleaned = sanitize(text)
    while cleaned.startswith(_FORMULA_PREFIXES):
        cleaned = cleaned[1:].lstrip()
    collapsed = " ".join(cleaned.split())
    return collapsed[:200] or "unspecified failure"


def classify_item(
    *,
    planned: PlannedItem,
    article: Article | None,
    summary: Summary | None,
    date: str,
    run_id: str,
    shard: int | None = None,
) -> ItemHealthRow:
    """Return the one terminal row for this planned item in this run.

    `shard` is the worker that produced the payloads, and it is optional because
    only one of the two callers has one. A worker knows its own number; assemble
    runs once for the whole day and cannot know which machine an item was for, so
    the rows it adds leave the cell empty rather than naming a shard that may
    never have started.
    """
    if article is None:
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=ItemStage.PLAN,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.NOT_ATTEMPTED,
        )

    if article.status is not ArticleStatus.OK:
        code, stage, status, detail = _classify_article(article)
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=stage,
            outcome=ItemOutcome.FAILED,
            code=code,
            http_status=status,
            source_chars=len(article.text or "") if article.text is not None else None,
            source_words=article.word_count or None,
            source_words_before_cap=article.source_word_count,
            detail=detail,
        )

    if summary is None:
        if article.failure_code in DEGRADED_BUT_DONE:
            return _row(
                planned=planned,
                date=date,
                run_id=run_id,
                shard=shard,
                stage=ItemStage.PUBLISH,
                outcome=ItemOutcome.OK,
                code=article.failure_code,
                source_chars=len(article.text or ""),
                source_words=article.word_count,
                source_words_before_cap=article.source_word_count,
            )
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.UNKNOWN,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            source_words_before_cap=article.source_word_count,
            detail=detail_cell("summary payload missing"),
        )

    if summary.status is not SummaryStatus.OK:
        code = summary.failure_code or FailureCode.UNKNOWN
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=code,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            source_words_before_cap=article.source_word_count,
            fetch_ms=summary.fetch_ms,
            extract_ms=summary.extract_ms,
            summarize_ms=summary.summarize_ms,
            detail=(
                detail_cell("summary failure was not typed")
                if code is FailureCode.UNKNOWN
                else None
            ),
        )

    return _row(
        planned=planned,
        date=date,
        run_id=run_id,
        shard=shard,
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
        code=article.failure_code,
        source_chars=len(article.text or ""),
        source_words=article.word_count,
        source_words_before_cap=article.source_word_count,
        summary_words=len((summary.summary or "").split()),
        fetch_ms=summary.fetch_ms,
        extract_ms=summary.extract_ms,
        summarize_ms=summary.summarize_ms,
        prefill_ms=summary.prefill_ms,
        decode_ms=summary.decode_ms,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        cached_tokens=summary.cached_tokens,
    )


def _row(
    *,
    planned: PlannedItem,
    date: str,
    run_id: str,
    stage: ItemStage,
    outcome: ItemOutcome,
    shard: int | None = None,
    code: FailureCode | None = None,
    http_status: int | None = None,
    source_chars: int | None = None,
    source_words: int | None = None,
    summary_words: int | None = None,
    detail: str | None = None,
    fetch_ms: int | None = None,
    extract_ms: int | None = None,
    summarize_ms: int | None = None,
    prefill_ms: int | None = None,
    decode_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_tokens: int | None = None,
    source_words_before_cap: int | None = None,
) -> ItemHealthRow:
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=date,
        run_id=run_id,
        item_id=planned.item_id,
        url_key=planned.url_key,
        canonical_url=planned.canonical_url,
        vertical=planned.vertical,
        source_id=planned.source_id,
        stage=stage,
        outcome=outcome,
        code=code,
        http_status=http_status,
        source_chars=source_chars,
        source_words=source_words,
        summary_words=summary_words,
        detail=detail,
        fetch_ms=fetch_ms,
        extract_ms=extract_ms,
        summarize_ms=summarize_ms,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        source_words_before_cap=source_words_before_cap,
        shard=shard,
    )


def _classify_article(article: Article) -> tuple[FailureCode, ItemStage, int | None, str | None]:
    detail = article.failure_detail or ""
    if article.status is ArticleStatus.EXTRACT_FAILED:
        if article.failure_code is not None:
            return article.failure_code, ItemStage.EXTRACT, None, None
        if detail == "extractor found no article text":
            return FailureCode.NO_TEXT, ItemStage.EXTRACT, None, None
        if detail.startswith("only ") and detail.endswith(
            " words extracted; page furniture is short"
        ):
            return FailureCode.TOO_SHORT, ItemStage.EXTRACT, None, None
        return (
            FailureCode.UNKNOWN,
            ItemStage.EXTRACT,
            None,
            detail_cell("extract failed for an untyped reason"),
        )

    if article.status is ArticleStatus.ROBOTS_DENIED:
        refusal = _ROBOTS_FAILURE.get(detail)
        if refusal is not None:
            return refusal, ItemStage.FETCH, None, None
        if detail in BLOCKED_REASONS or detail.startswith("scheme "):
            return FailureCode.BLOCKED_ADDRESS, ItemStage.FETCH, None, None
        return (
            FailureCode.UNKNOWN,
            ItemStage.FETCH,
            None,
            detail_cell("fetch failed for an untyped reason"),
        )

    match = _HTTP_DETAIL.match(detail)
    if match is not None:
        status = int(match.group("status"))
        if status == 429:
            return FailureCode.HTTP_RATE_LIMITED, ItemStage.FETCH, status, None
        if 400 <= status < 500:
            return FailureCode.HTTP_CLIENT_ERROR, ItemStage.FETCH, status, None
        if 500 <= status < 600:
            return FailureCode.HTTP_SERVER_ERROR, ItemStage.FETCH, status, None

    if detail in {"URLError", "TimeoutError", "OSError"}:
        return FailureCode.NETWORK_ERROR, ItemStage.FETCH, None, None

    return (
        FailureCode.UNKNOWN,
        ItemStage.FETCH,
        None,
        detail_cell("fetch failed for an untyped reason"),
    )
