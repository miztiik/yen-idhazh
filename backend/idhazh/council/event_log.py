"""How does the council log events without carrying a judge's or exception's text?"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import override

from pydantic import ValidationError

from idhazh import event_lines
from idhazh.contracts.base import Model
from idhazh.contracts.council_events import Diagnostic
from idhazh.contracts.knobs.council import JudgeRefusalError
from idhazh.event_lines import cause_of as cause_of
from idhazh.event_lines import payload as payload

logger = logging.getLogger(__name__)
_captured: ContextVar[list[Model] | None] = ContextVar("council_events", default=None)
_transport = logging.getLogger(f"{__name__}.transport")
_transport.propagate = False


class EventFile(logging.FileHandler):
    """Use LF in the transient bundle before any transport or test reads it."""

    def __init__(self, path: Path, *, encoding: str) -> None:
        super().__init__(path, encoding=encoding)
        if self.stream is not None:
            self.stream.reconfigure(newline="\n")

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        raise


def emit(event: Model, *, level: int = logging.INFO, force: bool = False) -> None:
    captured = _captured.get()
    if captured is not None:
        captured.append(event)
    if _transport.handlers:
        event_lines.emit(event, logger=_transport, level=level, force=True)
    event_lines.emit(event, logger=logger, level=level, force=force)


@contextmanager
def capture() -> Iterator[list[Model]]:
    """Keep this invocation's declared events, even when progress logs are hidden."""
    events: list[Model] = []
    token = _captured.set(events)
    try:
        yield events
    finally:
        _captured.reset(token)


def failed(failure: BaseException, *, refused: bool = False) -> None:
    named = failure if isinstance(failure, JudgeRefusalError) else None
    if isinstance(failure, ValidationError):
        for detail in failure.errors(include_url=False, include_input=False):
            candidate = detail.get("ctx", {}).get("error")
            if isinstance(candidate, JudgeRefusalError):
                named = candidate
                break
    error, where = cause_of(
        named.__cause__ if named is not None and named.__cause__ is not None else failure
    )
    emit(
        Diagnostic(
            kind="refusal" if refused else "exception",
            judge_id=None if named is None else named.judge_id,
            error=error,
            where=where,
        ),
        level=logging.ERROR,
    )


def _without_text(record: logging.LogRecord) -> Diagnostic:
    error, where = cause_of(None if record.exc_info is None else record.exc_info[1])
    return Diagnostic(kind="log", error=error, where=where)


class OneJsonLine(event_lines.OneJsonLine):
    """Discard unstructured messages, even if a library put source text in one."""

    def __init__(self) -> None:
        super().__init__(_without_text)


def install(level: str = "INFO") -> None:
    """Configure one process's council handler and the shared crash printer."""
    event_lines.install_crash_printer()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(OneJsonLine())
    logging.basicConfig(level=level, handlers=[handler])
    logging.getLogger().setLevel(level)
    target = os.environ.get("COUNCIL_EVENT_FILE")
    for previous in tuple(_transport.handlers):
        _transport.removeHandler(previous)
        previous.close()
    if target:
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        output = EventFile(path, encoding="utf-8")
        output.setFormatter(OneJsonLine())
        _transport.addHandler(output)
