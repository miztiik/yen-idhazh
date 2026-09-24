"""How does one span open, nest and close, and what may it carry?

What a span buys that a ledger column does not: a start instant, a parent, and a
step too small to earn a column of its own. `fetch_ms`, `extract_ms` and
`summarize_ms` already split a stage three ways; what they cannot say is that the
robots read inside the fetch took most of it, or that the model answered before
our own parsing spent another second on the reply.

Everything here builds one plain payload per span. Where that payload then goes
is `sinks.py`, so a host is a destination and never a shape - which is what keeps
an optional package out of the default install, out of `mypy`'s way, and out of
the guard's way: the guard reads the same records a host would have received.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from idhazh.contracts.article import Article
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary

#: The longest a span attribute value may be. One SHA-256 digest is 64
#: characters, and nothing an attribute carries is wider - a value that needs
#: more room is prose, and prose does not leave the process (Guardrail #11,
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
    network and no process state to reset between cases (Guardrail #7).

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
