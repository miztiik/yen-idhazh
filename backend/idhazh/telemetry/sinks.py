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
from dataclasses import dataclass
from pathlib import Path

from idhazh.telemetry.spans import Span


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
