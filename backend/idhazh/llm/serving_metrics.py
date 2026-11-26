"""Which load and prompt readings did one model server actually report?"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final

from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.task_performance import TaskPerformanceOutcome

# The existing capture limit applies to a startup log prefix and to the final metrics body.
CAPTURE_BYTES: Final = 1 << 20
_STAMP: Final = re.compile(r"^(\d+)\.([0-5]\d)\.(\d{3})\.(\d{3}) [A-Z] srv +")
_LOADING: Final = "load_model: loading model "
_LOADED: Final = "llama_server: model loaded"
PROMPT_TOKENS: Final = "llamacpp:prompt_tokens_total"
PROMPT_SECONDS: Final = "llamacpp:prompt_seconds_total"


@dataclass(frozen=True, slots=True)
class PromptTotals:
    tokens: int
    seconds: float


def read_startup_log(path: Path) -> str:
    """Only startup markers are needed, even when later inference fills the log."""
    with path.open("rb") as handle:
        raw = handle.read(CAPTURE_BYTES)
    # A bounded prefix may end inside a marker. Never interpret a partial line.
    return raw[: raw.rfind(b"\n") + 1].decode("utf-8", errors="replace")


def legacy_model_load_ms(text: str | None) -> float | None:
    """Keep the old server setup interval, which also includes context initialization."""
    started = None
    for line in (text or "").splitlines():
        stamp = _STAMP.match(line)
        if stamp is None:
            continue
        minutes, seconds, milliseconds, microseconds = map(int, stamp.groups())
        instant = (((minutes * 60) + seconds) * 1000 + milliseconds) * 1000 + microseconds
        message = line[stamp.end() :]
        if message.startswith(_LOADING) and started is None:
            started = instant
        elif message == _LOADED and started is not None:
            return (instant - started) / 1000 if instant >= started else None
    return None


def server_prompt_totals(text: str | None) -> tuple[int | None, float | None]:
    """Decode the original wire totals without rounding a count or inventing a zero."""
    found: dict[str, str] = {}
    for line in (text or "").splitlines():
        series, _, value = line.strip().partition(" ")
        if series in (PROMPT_TOKENS, PROMPT_SECONDS):
            if series in found:
                raise ValueError(f"duplicate {series}")
            found[series] = value.strip()
    tokens = None
    if PROMPT_TOKENS in found:
        try:
            count = Decimal(found[PROMPT_TOKENS])
        except InvalidOperation:
            raise ValueError(f"invalid {PROMPT_TOKENS}") from None
        if not count.is_finite() or not 0 <= count <= (1 << 53) - 1 or count % 1:
            raise ValueError(f"invalid {PROMPT_TOKENS}: expected a nonnegative safe integer")
        tokens = int(count)
    seconds = float(found[PROMPT_SECONDS]) if PROMPT_SECONDS in found else None
    if seconds is not None and (not math.isfinite(seconds) or seconds < 0):
        raise ValueError(f"invalid {PROMPT_SECONDS}")
    return tokens, seconds


def _prompt_pair(text: str) -> PromptTotals | None:
    """A pair is usable only when this one response contains both raw counters."""
    tokens, seconds = server_prompt_totals(text)
    return PromptTotals(tokens, seconds) if tokens is not None and seconds is not None else None


def serving_measurement(
    text: str, *, subject_id: str, outcome: TaskPerformanceOutcome,
    started_at: str | None = None, finished_at: str | None = None,
) -> dict[str, object] | None:
    """The pinned server reports no weights-only close marker or timer."""
    totals = _prompt_pair(text)
    if totals is None:
        return None
    return {
        "task_kind": "model-serving",
        "outcome": outcome,
        "subject_id": subject_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "model_load_ms": None,
        "server_prompt_tokens": totals.tokens,
        "server_prompt_seconds": totals.seconds,
    }


def retain_serving_capture(
    path: Path, body: bytes, *, subject_id: str, outcome: TaskPerformanceOutcome,
    started_at: str, finished_at: str,
) -> dict[str, object] | None:
    """Keep the verified raw capture even when it cannot supply a serving row."""
    write_atomic_bytes(path, body)
    return serving_measurement(
        body.decode("utf-8"), subject_id=subject_id, outcome=outcome,
        started_at=started_at, finished_at=finished_at,
    )
