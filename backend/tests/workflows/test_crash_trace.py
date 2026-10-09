"""Does a crash's trace name every exception of its chain by type and frames, and quote none?

`backend/idhazh/crash_trace.py` is what each program the gardener's workflow
runs prints when an exception ends it. Each case here raises a real exception in
code this file holds and reads what `print_trace` writes to stderr. Every
exception carries planted text, the way a message can quote a fetched page, so a
line that repeated it would show (Guardrail #11). What each program prints when
it crashes is `test_gardener_crash_trace.py`.
"""

from __future__ import annotations

import json
import traceback
from typing import Final

import pytest

from idhazh import crash_trace

pytestmark = pytest.mark.workflow

#: What a fetched page might say, planted in every exception; and the part of it
#: no line may hold.
FETCHED: Final = "Breaking: click https://example.invalid/now"
PLANTED: Final = "example.invalid"

HEADER: Final = "Traceback (most recent call last):"
CAUSE: Final = "The above exception was the direct cause of the following exception:"
CONTEXT: Final = "During handling of the above exception, another exception occurred:"


class Unprintable:
    """A module name whose `str` raises, as a printer that called it would."""

    def __str__(self) -> str:
        raise RuntimeError(FETCHED)


def frames(failure: BaseException) -> list[str]:
    """The frame lines of `failure`'s own traceback, when every frame is this file's code."""
    return [f"  {__name__}:{entry.lineno}" for entry in traceback.extract_tb(failure.__traceback__)]


def printed(failure: BaseException, capsys: pytest.CaptureFixture[str]) -> list[str]:
    """What `print_trace` writes, line by line, once the planted text is shown absent."""
    crash_trace.print_trace(failure)
    said = capsys.readouterr()
    assert said.out == ""
    assert PLANTED not in said.err, said.err
    return said.err.splitlines()


def read_the_page() -> None:
    raise KeyError(FETCHED)


def refuse_the_page() -> None:
    try:
        read_the_page()
    except KeyError as cause:
        refusal = ValueError(FETCHED, 7)
        refusal.add_note(FETCHED)
        raise refusal from cause


def report_the_page() -> None:
    raise RuntimeError(FETCHED)


def report_while_reading() -> None:
    try:
        read_the_page()
    except KeyError:
        report_the_page()


def refuse_and_hide_the_page() -> None:
    try:
        read_the_page()
    except KeyError:
        raise ValueError(FETCHED) from None


def test_an_exception_raised_from_another_prints_both_oldest_first_and_neither_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The message, a second argument and a note all hold the planted text; none is printed."""
    with pytest.raises(ValueError) as raised:
        refuse_the_page()
    refusal = raised.value
    cause = refusal.__cause__
    assert cause is not None

    assert printed(refusal, capsys) == [
        HEADER,
        *frames(cause),
        "KeyError",
        "",
        CAUSE,
        "",
        HEADER,
        *frames(refusal),
        "ValueError",
    ]


def test_an_exception_raised_while_another_was_handled_prints_that_one_first(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(RuntimeError) as raised:
        report_while_reading()
    report = raised.value
    handled = report.__context__
    assert handled is not None

    assert printed(report, capsys) == [
        HEADER,
        *frames(handled),
        "KeyError",
        "",
        CONTEXT,
        "",
        HEADER,
        *frames(report),
        "RuntimeError",
    ]


def test_an_exception_raised_from_none_prints_alone_as_python_prints_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ValueError) as raised:
        refuse_and_hide_the_page()

    assert printed(raised.value, capsys) == [HEADER, *frames(raised.value), "ValueError"]


@pytest.mark.parametrize(
    "namespace",
    [{}, {"__name__": Unprintable()}],
    ids=["no-name", "a-name-that-will-not-print"],
)
def test_a_frame_whose_module_has_no_plain_name_prints_a_mark_and_never_raises(
    namespace: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    """A hook that raised would make Python print its own trace of the crash, text included."""
    code = compile(f"raise LookupError({FETCHED!r})", "<planted>", "exec")
    with pytest.raises(LookupError) as raised:
        exec(code, namespace)
    here, planted = traceback.extract_tb(raised.value.__traceback__)

    assert printed(raised.value, capsys) == [
        HEADER,
        f"  {__name__}:{here.lineno}",
        f"  ?:{planted.lineno}",
        "LookupError",
    ]


def test_a_type_whose_module_has_no_plain_name_prints_a_mark(
    capsys: pytest.CaptureFixture[str],
) -> None:
    odd = type("Odd", (Exception,), {"__module__": Unprintable()})

    assert printed(odd(FETCHED), capsys) == ["?.Odd"]


def test_a_type_outside_the_builtins_is_named_after_its_module(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The decoder keeps the text it could not read; the trace names only where and what."""
    with pytest.raises(json.JSONDecodeError) as raised:
        json.loads(FETCHED)

    assert printed(raised.value, capsys)[-1] == "json.decoder.JSONDecodeError"


def test_a_chain_that_loops_back_on_itself_still_ends(
    capsys: pytest.CaptureFixture[str],
) -> None:
    first, second = ValueError(FETCHED), KeyError(FETCHED)
    first.__context__ = second
    second.__context__ = first

    assert printed(first, capsys) == ["KeyError", "", CONTEXT, "", "ValueError"]
