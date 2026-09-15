"""Where does a finished span go?

A committed file by default, and a host only when an operator names one in the
environment (owner decision, 2026-08-30). So a developer gets the tree with no
account, no key and no third party, CI needs no secret, and the pipeline is
correct with nothing reachable.

Every sink takes the same validated payload `spans.py` builds, so adding a
destination cannot change what a span says (Guardrail #11).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from idhazh.telemetry.spans import AttrKey, AttrValue, Span, SpanSink


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


class CollectingSink:
    """Keeps every span in memory so a shard can fold its own tree at the end.

    Fanned out beside the file sink, never instead of it, so `roll_up_spans`
    folds the span objects themselves rather than re-reading the file it just
    wrote. The committed rollup and the committed trace then come off one set of
    spans and cannot disagree about what the shard did - and the fold is fed by
    every span, which is what the shard's wall-clock reconciliation depends on.
    """

    __slots__ = ("_spans",)

    def __init__(self) -> None:
        self._spans: list[Span] = []

    def emit(self, span: Span) -> None:
        self._spans.append(span)

    def flush(self) -> None:
        return None

    def spans(self) -> Sequence[Span]:
        return tuple(self._spans)


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
    set to nothing rather than left to a default (Guardrail #11, CLAUDE.md section
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
