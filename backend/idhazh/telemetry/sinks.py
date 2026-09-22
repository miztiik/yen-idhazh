"""Where does a finished span go?

A committed file, and nowhere else. A developer gets the tree with no account
and no key, CI needs no secret, and nothing this pipeline traces leaves the
machine that traced it - which is what Guardrail #1 and CLAUDE.md section 1b ask
of a build-time producer.

Every sink takes the same validated payload `spans.py` builds, so adding a
destination cannot change what a span says (Guardrail #11).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from idhazh.telemetry.spans import Span, SpanSink


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
    """One JSON line per span, under `backend/var/`, and the only destination.

    A file is where a span goes. So a developer gets the tree with no account
    and no key, CI needs no secret, and no span this pipeline opens reaches a
    third party.
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
    """Every sink gets every span, so a second reader is added to the file rather than instead."""

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
