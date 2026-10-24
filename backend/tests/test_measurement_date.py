"""Resolve a budget measurement's date without borrowing the host's local day."""

import sys
from datetime import UTC, date, datetime
from types import FrameType
from typing import Any

import pytest

from utilities.measure_budgets import Tokenizer, main, parse_args, resolve_measurement_date


@pytest.mark.parametrize(
    ("instant", "taken_on", "expected"),
    [
        ("2027-01-01T00:30:00+02:00", None, date(2026, 12, 31)),
        ("2026-12-31T23:30:00-02:00", None, date(2027, 1, 1)),
        ("2027-01-01T00:30:00+02:00", "2026-06-15", date(2026, 6, 15)),
    ],
    ids=["east-of-utc-year-end", "west-of-utc-year-end", "operator-date"],
)
def test_measurement_date_uses_the_utc_day_unless_the_operator_supplies_one(
    instant: str, taken_on: str | None, expected: date
) -> None:
    argv = ["read", "--runner", "date-resolution-test"]
    if taken_on is not None:
        argv += ["--taken-on", taken_on]
    args = parse_args(argv)

    assert resolve_measurement_date(
        args.taken_on, now=datetime.fromisoformat(instant)
    ) == expected


def test_measurement_date_refuses_an_instant_without_a_utc_offset() -> None:
    with pytest.raises(ValueError, match="must include a UTC offset"):
        resolve_measurement_date(None, now=datetime(2027, 1, 1))


@pytest.mark.parametrize("taken_on", [None, "2026-06-15"], ids=["utc-default", "operator-date"])
def test_read_stamps_the_resolved_date_before_starting_the_tokenizer(
    taken_on: str | None,
) -> None:
    class BeforeTokenizerError(Exception):
        pass

    calls: list[dict[str, Any]] = []
    returned: list[object] = []
    stamps: list[dict[str, str]] = []

    def observe(frame: FrameType, event: str, argument: object) -> None:
        if frame.f_code is resolve_measurement_date.__code__:
            if event == "call":
                calls.append(dict(frame.f_locals))
                instant = frame.f_locals["now"]
                assert isinstance(instant, datetime) and instant.tzinfo is UTC
            elif event == "return":
                returned.append(argument)
        if event == "call" and frame.f_code is Tokenizer.__init__.__code__:
            caller = frame.f_back
            assert caller is not None
            stamps.append(dict(caller.f_locals["stamp"]))
            raise BeforeTokenizerError

    argv = ["read", "--subject", "a" * 64, "--runner", "date-resolution-test"]
    if taken_on is not None:
        argv += ["--taken-on", taken_on]
    previous = sys.getprofile()
    started = datetime.now(UTC)
    try:
        sys.setprofile(observe)
        with pytest.raises(BeforeTokenizerError):
            main(argv)
    finally:
        sys.setprofile(previous)
    ended = datetime.now(UTC)

    assert len(calls) == len(returned) == len(stamps) == 1
    instant = calls[0]["now"]
    assert isinstance(instant, datetime) and instant.tzinfo is UTC
    assert started <= instant <= ended
    expected = date.fromisoformat(taken_on) if taken_on else instant.date()
    assert calls[0]["taken_on"] == (date.fromisoformat(taken_on) if taken_on else None)
    assert returned == [expected]
    assert stamps == [{
        "subject": "a" * 64,
        "runner": "date-resolution-test",
        "taken_on": expected.isoformat(),
    }]
