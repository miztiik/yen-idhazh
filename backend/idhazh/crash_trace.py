"""What does an idhazh program or command print when it crashes? Where it broke, never its text.

Python's own trace prints each exception's message, and the message of every
exception chained to it. A message can quote a ledger row or what GitHub's API
or a file returned, and that can be text fetched from the open web (Guardrail
#11). So the package command calls `install` before it reads argv or hands a
line to a subrouter, and each utility program that bypasses that router calls
`install` before its `main`. A program that catches an exception to end on an
exit code of its own prints it with `print_trace`.

**The trace keeps Python's layout and drops every word an exception carries.**
For the exception and each one chained to it, oldest first, with Python's own
sentence between two of them: `Traceback (most recent call last):`, one
`module:line` for each frame, most recent call last, and the type's name.
`module:line` is the form a gardener event's `where` takes, and `__main__` is
the program the step ran, or the command's own entry. Never a message, an
argument, a local, a source line, a note or a file path. An exception group is
not opened: none of these programs raises one.

**Printing the trace never raises.** When the hook raises, Python prints its own
trace of the exception that ended the program, text included. So a module's name
is read only when it is a plain string, and one that is not prints `?`.

**The exit code is still the interpreter's**: 1 for an exception, and an
interrupt's own code for an interrupt. A `SystemExit` never reaches the hook, so
a program's own refusals keep their words.

The standard library alone, as the package's `__init__.py` is, because two of
the programs that import it run before anything is installed.
"""

from __future__ import annotations

import sys
from types import TracebackType
from typing import Final

#: The line Python prints before an exception's frames.
_HEADER: Final = "Traceback (most recent call last):"

#: What Python prints between an exception and the one it was raised `from`.
_CAUSE: Final = "The above exception was the direct cause of the following exception:"

#: What Python prints between an exception and the one it was raised while handling.
_CONTEXT: Final = "During handling of the above exception, another exception occurred:"

#: What a module with no plain name prints as.
_UNNAMED: Final = "?"

#: The modules whose types Python names without the module.
_BARE_MODULES: Final = frozenset({"builtins", "__main__"})


def install() -> None:
    """Make `print_trace` what this process prints when an exception ends it."""
    sys.excepthook = _print_on_exit


def print_trace(failure: BaseException) -> None:
    """Write the trace of `failure` and its chain to stderr: types and frames, never text."""
    sys.stderr.write("\n".join(_lines(failure)) + "\n")


def _print_on_exit(
    kind: type[BaseException], failure: BaseException, trace: TracebackType | None
) -> None:
    """The shape `sys.excepthook` takes. The exception carries its own type and frames."""
    print_trace(failure)


def _lines(failure: BaseException) -> list[str]:
    """The trace, one line each: the oldest exception of the chain first."""
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
    """Each exception of the chain, newest first, with the sentence that comes before it.

    Walked as Python walks it: the exception it was raised `from`, otherwise the
    one it was raised while handling, unless `from None` hid that one. An
    exception already met ends the walk, so a chain that loops still ends.
    """
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
    """One `  module:line` for each frame, most recent call last."""
    frames: list[str] = []
    while trace is not None:
        module = _plain(trace.tb_frame.f_globals.get("__name__"))
        frames.append(f"  {module}:{trace.tb_lineno}")
        trace = trace.tb_next
    return frames


def _type_name(kind: type[BaseException]) -> str:
    """The type as Python's trace names it: a built-in bare, any other after its module."""
    module = _plain(kind.__module__)
    return kind.__qualname__ if module in _BARE_MODULES else f"{module}.{kind.__qualname__}"


def _plain(name: object) -> str:
    """A module's name when it is a plain string, else `?`: a subclass could print as anything."""
    return name if type(name) is str else _UNNAMED
