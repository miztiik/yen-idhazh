"""Is a day old enough exactly when its own end says so, whenever the job wakes?

A UTC day ended at 00:00 UTC on the day after it, and a day is eligible once
`after_hours` whole hours have passed since then. That instant is a fact about
the day, so moving the schedule cannot move it. What the schedule does move is
when the question is asked, and these tests pin both halves: the answer at
every wake the workflow might use, and the instant the answer changes.

No clock is read. Every instant is written out, in UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from idhazh.gardener.schedule import ended_at, is_eligible

pytestmark = pytest.mark.contract

#: Six days, the last of them the day the wakes fall on.
DAYS = tuple(date(2026, 9, 20) + timedelta(days=offset) for offset in range(6))
#: The wakes a gardener schedule might use, on the last of those days.
WAKES = ("00:00", "00:40", "12:00", "23:00", "23:59")


def at(day: date, clock: str) -> datetime:
    hours, minutes = (int(part) for part in clock.split(":"))
    return datetime(day.year, day.month, day.day, hours, minutes, tzinfo=UTC)


def eligible(now: datetime, after_hours: int) -> set[date]:
    return {day for day in DAYS if is_eligible(day, now=now, after_hours=after_hours)}


def test_a_day_ends_at_midnight_utc_on_the_day_after_it() -> None:
    assert ended_at(date(2026, 9, 24)) == datetime(2026, 9, 25, tzinfo=UTC)
    assert ended_at(date(2026, 12, 31)) == datetime(2027, 1, 1, tzinfo=UTC)


def test_at_a_whole_day_the_answer_is_the_same_at_every_wake_of_a_day() -> None:
    """At 24 hours the set is identical at all five wakes, and changes only at the next midnight.

    Even at 23:59 on the 25th the 24th has been over for 23 hours 59 minutes,
    not 24, so it is not yet eligible. It becomes eligible at 00:00 on the 26th.
    """
    today = DAYS[-1]
    answers = {clock: eligible(at(today, clock), 24) for clock in WAKES}

    assert all(answer == set(DAYS[:-2]) for answer in answers.values()), answers
    assert eligible(at(today + timedelta(days=1), "00:00"), 24) == set(DAYS[:-1])


def test_a_knob_that_is_not_a_whole_day_changes_the_answer_inside_a_day() -> None:
    """At 30 hours the 24th turns eligible at 06:00 on the 26th, between two wakes of that day.

    So a wake at 00:40 acts on it a day later than a wake at 12:00 would: the
    rule does not move, but when it is next read does.
    """
    the_24th = DAYS[4]
    next_day = DAYS[-1] + timedelta(days=1)
    turned = {clock: the_24th in eligible(at(next_day, clock), 30) for clock in WAKES}

    assert turned == {"00:00": False, "00:40": False, "12:00": True, "23:00": True, "23:59": True}


@pytest.mark.parametrize("after_hours", [1, 24, 30, 360])
def test_the_boundary_moves_with_the_knob_and_nothing_else(after_hours: int) -> None:
    """Not eligible a microsecond before `ended_at + after_hours`, and eligible at it."""
    day = date(2026, 9, 24)
    boundary = ended_at(day) + timedelta(hours=after_hours)

    assert not is_eligible(day, now=boundary - timedelta(microseconds=1), after_hours=after_hours)
    assert is_eligible(day, now=boundary, after_hours=after_hours)


def test_an_instant_with_no_timezone_is_refused() -> None:
    """A naive instant cannot be compared with the end of a UTC day, and Python says so."""
    with pytest.raises(TypeError):
        is_eligible(date(2026, 9, 24), now=datetime(2026, 9, 26), after_hours=24)
