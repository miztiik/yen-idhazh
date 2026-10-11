"""How are event lines and text-free crash diagnostics written?"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, Final, NamedTuple

if TYPE_CHECKING:
    from idhazh.contracts.base import Model

# The existing record key is a transport constant, not the event's owner.
_ATTRIBUTE: Final = "gardener_event"
_WORD_START: Final = re.compile(r"(?<!^)(?=[A-Z])")
_PACKAGE: Final = __name__.partition(".")[0]
_DATA_ESCAPES: Final = (("%", "%25"), ("\r", "%0D"), ("\n", "%0A"))
_PROPERTY_ESCAPES: Final = (*_DATA_ESCAPES, (":", "%3A"), (",", "%2C"))


class Cause(NamedTuple):
    """An exception's type and deepest place in this package, never its text."""

    error: str | None
    where: str | None


def name_of(kind: type[Model]) -> str:
    """Name an event by its class name in kebab case."""
    return _WORD_START.sub("-", kind.__name__).lower()


def fields_of(event: Model) -> dict[str, Any]:
    """Return the event name and declared fields, leaving out nulls."""
    return {"event": name_of(type(event)), **event.model_dump(mode="json", exclude_none=True)}


def cause_of(failure: BaseException | None) -> Cause:
    """Return an exception's type and deepest package frame without reading its message."""
    if failure is None:
        return Cause(None, None)
    where: str | None = None
    frame = failure.__traceback__
    while frame is not None:
        module = frame.tb_frame.f_globals.get("__name__", "")
        if type(module) is str and (module == _PACKAGE or module.startswith(f"{_PACKAGE}.")):
            where = f"{module}:{frame.tb_lineno}"
        frame = frame.tb_next
    return Cause(type(failure).__name__, where)


def emit(event: Model, *, logger: logging.Logger, level: int = logging.INFO) -> None:
    """Carry the event whole on a record, with its JSON as the record's message."""
    if logger.isEnabledFor(level):
        logger.log(level, _dumped(fields_of(event)), extra={_ATTRIBUTE: event})


def payload(record: logging.LogRecord) -> Model | None:
    """Return a record's declared event, or None for a text record."""
    from idhazh.contracts.base import Model

    held = getattr(record, _ATTRIBUTE, None)
    return held if isinstance(held, Model) else None


def instant(record: logging.LogRecord) -> str:
    """Stamp a record in UTC to milliseconds with a Z."""
    made = datetime.fromtimestamp(record.created, UTC)
    return made.isoformat(timespec="milliseconds").removesuffix("+00:00") + "Z"


class OneJsonLine(logging.Formatter):
    """Write one event per line; the caller declares how text records are represented."""

    def __init__(self, fallback: Callable[[logging.LogRecord], Model]) -> None:
        super().__init__()
        self.fallback = fallback

    def format(self, record: logging.LogRecord) -> str:
        said = fields_of(payload(record) or self.fallback(record))
        line = {
            "event": said.pop("event"),
            "at": instant(record),
            "level": record.levelname.lower(),
        }
        return _dumped({**line, **said})


def escaped_data(text: str) -> str:
    """Escape workflow command data so it cannot start another command."""
    return _replaced(text, _DATA_ESCAPES)


def escaped_property(text: str) -> str:
    """Escape workflow command properties, including their delimiters."""
    return _replaced(text, _PROPERTY_ESCAPES)


def _replaced(text: str, escapes: tuple[tuple[str, str], ...]) -> str:
    for character, escape in escapes:
        text = text.replace(character, escape)
    return text


def _dumped(line: dict[str, Any]) -> str:
    return json.dumps(line, ensure_ascii=True, separators=(",", ":"))


_HEADER: Final = "Traceback (most recent call last):"
_CAUSE: Final = "The above exception was the direct cause of the following exception:"
_CONTEXT: Final = "During handling of the above exception, another exception occurred:"
_UNNAMED: Final = "?"
_BARE_MODULES: Final = frozenset({"builtins", "__main__"})


def install_crash_printer() -> None:
    """Install the text-free crash printer without importing application dependencies."""
    sys.excepthook = _print_on_exit


def print_trace(failure: BaseException) -> None:
    """Write exception types and frames to stderr, never messages, paths or source lines."""
    sys.stderr.write("\n".join(_lines(failure)) + "\n")


def _print_on_exit(
    kind: type[BaseException], failure: BaseException, trace: TracebackType | None
) -> None:
    print_trace(failure)


def _lines(failure: BaseException) -> list[str]:
    lines: list[str] = []
    for link, sentence in reversed(_chain(failure)):
        if sentence is not None:
            lines.extend(("", sentence, ""))
        frames = _frames(link.__traceback__)
        if frames:
            lines.append(_HEADER)
        lines.extend(frames)
        lines.append(_type_name(type(link)))
    return lines


def _chain(failure: BaseException) -> list[tuple[BaseException, str | None]]:
    chain: list[tuple[BaseException, str | None]] = []
    seen: set[int] = set()
    link: BaseException | None = failure
    while link is not None:
        seen.add(id(link))
        older: BaseException | None = None
        sentence: str | None = None
        if link.__cause__ is not None:
            older, sentence = link.__cause__, _CAUSE
        elif link.__context__ is not None and not link.__suppress_context__:
            older, sentence = link.__context__, _CONTEXT
        if older is not None and id(older) in seen:
            older, sentence = None, None
        chain.append((link, sentence))
        link = older
    return chain


def _frames(trace: TracebackType | None) -> list[str]:
    frames: list[str] = []
    while trace is not None:
        module = _plain(trace.tb_frame.f_globals.get("__name__"))
        frames.append(f"  {module}:{trace.tb_lineno}")
        trace = trace.tb_next
    return frames


def _type_name(kind: type[BaseException]) -> str:
    module = _plain(kind.__module__)
    return kind.__qualname__ if module in _BARE_MODULES else f"{module}.{kind.__qualname__}"


def _plain(name: object) -> str:
    return name if type(name) is str else _UNNAMED
