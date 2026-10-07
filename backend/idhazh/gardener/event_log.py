"""How a gardener event becomes one log line.

Every line the gardener logs is one event: a model declared in
`idhazh.contracts.gardener_events`, written as one line of JSON on stderr
through the standard `logging` module (CLAUDE.md section 1b). `emit` hands the
event to `logging` on the record itself, so a test takes the payload back with
`payload` and never parses the text. `OneJsonLine` writes the line: `event`
first, the event's name in kebab case; `at`, the instant the record was made,
in UTC with a `Z` (CLAUDE.md section 2); `level`; then the model's fields in the
order it declares them, every None left out and a nested model kept nested. The
line is ASCII, because JSON escapes every other character, and a line break
inside a value is escaped too, so one event is always one line - and no text
inside one can start a line GitHub would read as a workflow command.

**A record that carries no event is still one event.** A module outside the
gardener that a task calls - the ledger door's own warnings, a library - logs
text. The line wraps it as `LoggedText`: the logger's name and the message as it
was said, so every line of a gardener run reads the same way.

**An exception is named by its type and its place, never its text** (`cause_of`).
An exception's message can carry a ledger row, and a row can hold text fetched
from the open web (Guardrail #11). Its type and the deepest line of this
package's own code it passed through are code, and say where to look.

**The record's message is the event's JSON too.** `one_at_a_time.take` and the
compaction also run under commands that write their records as text -
`idhazh telemetry prune`, the ledger migrator - and those print the message.

**`install` puts one handler on the root logger.** The gardener's two command
lines call it from `cli.settings_or_none`, at the level `config/` names. It is
`logging.basicConfig`, so once the root logger has a handler a second call does
nothing.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, Final, NamedTuple

from idhazh.contracts.base import Model
from idhazh.contracts.gardener_events import LoggedText

#: The record attribute an event travels on, from `emit` to the formatter.
_ATTRIBUTE: Final = "gardener_event"

#: Where a word starts inside a class name, for the kebab-case event name.
_WORD_START: Final = re.compile(r"(?<!^)(?=[A-Z])")

#: The package whose code a `where` names: the one this module is part of.
_PACKAGE: Final = __name__.partition(".")[0]

logger = logging.getLogger(__name__)


class Cause(NamedTuple):
    """An exception as a line may name it: its type, and where in this package it was raised."""

    error: str | None
    where: str | None


def name_of(kind: type[Model]) -> str:
    """The name an event's line carries: its class name in kebab case, `task-planned`."""
    return _WORD_START.sub("-", kind.__name__).lower()


def fields_of(event: Model) -> dict[str, Any]:
    """The event as its line holds it: its name, then its fields in order, every None left out."""
    return {"event": name_of(type(event)), **event.model_dump(mode="json", exclude_none=True)}


def cause_of(failure: BaseException | None) -> Cause:
    """An exception's type name, and the deepest `module:line` of this package it passed through.

    Never its message. None for both when there is no exception; `where` is
    None when no frame of the traceback is this package's own code.
    """
    if failure is None:
        return Cause(error=None, where=None)
    where: str | None = None
    frame = failure.__traceback__
    while frame is not None:
        module = str(frame.tb_frame.f_globals.get("__name__", ""))
        if module == _PACKAGE or module.startswith(f"{_PACKAGE}."):
            where = f"{module}:{frame.tb_lineno}"
        frame = frame.tb_next
    return Cause(error=type(failure).__name__, where=where)


def emit(event: Model, *, level: int = logging.INFO) -> None:
    """Log one event at `level`, carried on the record whole, its JSON the record's message."""
    if logger.isEnabledFor(level):
        logger.log(level, _dumped(fields_of(event)), extra={_ATTRIBUTE: event})


def payload(record: logging.LogRecord) -> Model | None:
    """The event a record carries, or None for a record some other module logged as text."""
    held = getattr(record, _ATTRIBUTE, None)
    return held if isinstance(held, Model) else None


def instant(record: logging.LogRecord) -> str:
    """The UTC instant a record was made, to the millisecond, as ISO-8601 with `Z`."""
    made = datetime.fromtimestamp(record.created, UTC)
    return made.isoformat(timespec="milliseconds").removesuffix("+00:00") + "Z"


class OneJsonLine(logging.Formatter):
    """Each record as one line of ASCII JSON: `event`, `at`, `level`, then what it says."""

    def format(self, record: logging.LogRecord) -> str:
        event = payload(record) or _as_text(record)
        said = fields_of(event)
        line = {"event": said.pop("event"), "at": instant(record), "level": _level(record)}
        return _dumped({**line, **said})


def install(level: str) -> None:
    """One `OneJsonLine` handler on stderr for the root logger, at `level`, unless it has one."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(OneJsonLine())
    logging.basicConfig(level=level, handlers=[handler])


def _as_text(record: logging.LogRecord) -> LoggedText:
    """A record some other module logged as text, as the event that keeps what it said."""
    error, where = cause_of(None if record.exc_info is None else record.exc_info[1])
    return LoggedText(logger=record.name, message=record.getMessage(), error=error, where=where)


def _level(record: logging.LogRecord) -> str:
    """The record's level as its line names it: `info`, `warning`, `error`."""
    return record.levelname.lower()


def _dumped(line: dict[str, Any]) -> str:
    """One line of JSON, ASCII, with no space after a separator."""
    return json.dumps(line, ensure_ascii=True, separators=(",", ":"))
