"""Is a period old enough exactly when its own end says so, whenever the job wakes?

A UTC day ended at 00:00 UTC on the day after it, and a month at 00:00 UTC on
the first of the month after it. A period is eligible once `after_days` whole
days have passed since then. That instant is a fact about the period, so moving
the schedule cannot move it, and because the wait is whole days the answer is
the same at every wake of one UTC day. These tests pin both halves: the answer
at every wake the workflow might use, and the instant the answer changes.

No clock is read. Every instant is written out, in UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from idhazh.gardener.schedule import (
    ended_at,
    is_eligible,
    is_month_eligible,
    month_ended_at,
    newest_eligible,
)

pytestmark = pytest.mark.contract

#: Six days, the last of them the day the wakes fall on.
DAYS = tuple(date(2026, 9, 20) + timedelta(days=offset) for offset in range(6))
#: The wakes a gardener schedule might use, on the last of those days.
WAKES = ("00:00", "00:40", "12:00", "23:00", "23:59")


def at(day: date, clock: str) -> datetime:
    hours, minutes = (int(part) for part in clock.split(":"))
    return datetime(day.year, day.month, day.day, hours, minutes, tzinfo=UTC)


def eligible(now: datetime, after_days: int) -> set[date]:
    return {day for day in DAYS if is_eligible(day, now=now, after_days=after_days)}


def test_a_day_ends_at_midnight_utc_on_the_day_after_it() -> None:
    assert ended_at(date(2026, 9, 24)) == datetime(2026, 9, 25, tzinfo=UTC)
    assert ended_at(date(2026, 12, 31)) == datetime(2027, 1, 1, tzinfo=UTC)


def test_at_one_whole_day_the_answer_is_the_same_at_every_wake_of_a_day() -> None:
    """At one day the set is identical at all five wakes, and changes only at the next midnight.

    Even at 23:59 on the 25th the 24th has been over for 23 hours 59 minutes,
    not a whole day, so it is not yet eligible. It becomes eligible at 00:00 on
    the 26th.
    """
    today = DAYS[-1]
    answers = {clock: eligible(at(today, clock), 1) for clock in WAKES}

    assert all(answer == set(DAYS[:-2]) for answer in answers.values()), answers
    assert eligible(at(today + timedelta(days=1), "00:00"), 1) == set(DAYS[:-1])


@pytest.mark.parametrize("after_days", [1, 2, 3])
def test_no_wake_of_a_day_changes_the_answer_at_any_number_of_days(after_days: int) -> None:
    """A whole number of days after midnight is midnight, so no wake time moves the boundary."""
    today = DAYS[-1]
    answers = {clock: eligible(at(today, clock), after_days) for clock in WAKES}

    assert len({frozenset(answer) for answer in answers.values()}) == 1, answers
    assert answers["00:00"] == set(DAYS[: len(DAYS) - 1 - after_days])


@pytest.mark.parametrize("after_days", [1, 2, 15, 360])
def test_the_boundary_moves_with_the_knob_and_nothing_else(after_days: int) -> None:
    """Not eligible a microsecond before `ended_at + after_days`, and eligible at it."""
    day = date(2026, 9, 24)
    boundary = ended_at(day) + timedelta(days=after_days)

    assert not is_eligible(day, now=boundary - timedelta(microseconds=1), after_days=after_days)
    assert is_eligible(day, now=boundary, after_days=after_days)


def test_an_instant_with_no_timezone_is_refused() -> None:
    """A naive instant cannot be compared with the end of a UTC day, and Python says so."""
    with pytest.raises(TypeError):
        is_eligible(date(2026, 9, 24), now=datetime(2026, 9, 26), after_days=1)


@pytest.mark.parametrize("after_days", [1, 2, 15])
def test_the_newest_eligible_day_is_the_newest_day_the_rule_says_yes_to(after_days: int) -> None:
    """At every wake of the 25th, one day of waiting makes the 23rd the newest day to take."""
    today = DAYS[-1]
    for clock in WAKES:
        now = at(today, clock)
        newest = newest_eligible(now=now, after_days=after_days)
        assert is_eligible(newest, now=now, after_days=after_days)
        assert not is_eligible(newest + timedelta(days=1), now=now, after_days=after_days)
    assert newest_eligible(now=at(today, "00:40"), after_days=1) == date(2026, 9, 23)


def test_a_month_ends_at_midnight_utc_on_the_first_of_the_month_after_it() -> None:
    assert month_ended_at("2026-08") == datetime(2026, 9, 1, tzinfo=UTC)
    assert month_ended_at("2026-12") == datetime(2027, 1, 1, tzinfo=UTC)


def test_a_month_turns_eligible_at_its_end_plus_the_days_and_not_a_microsecond_before() -> None:
    """45 days after August ends is 00:00 UTC on 16 October, whatever the wake."""
    boundary = datetime(2026, 10, 16, tzinfo=UTC)

    assert boundary - month_ended_at("2026-08") == timedelta(days=45)
    assert not is_month_eligible(
        "2026-08", now=boundary - timedelta(microseconds=1), after_days=45
    )
    assert all(
        is_month_eligible("2026-08", now=at(boundary.date(), clock), after_days=45)
        for clock in WAKES
    )
