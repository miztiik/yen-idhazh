"""Is a UTC day old enough for the gardener to act on at a given instant?

**A day's end is a fact and a wake is not.** A day ended at 00:00 UTC on the
day after it, whenever the job that asks happened to wake, so whether a day is
old enough is measured from that instant and never from the wake. Moving a
schedule therefore cannot change which days qualify - it only changes when the
question is next asked (CLAUDE.md section 2).

Nothing here reads a clock. The instant is handed in, which is what lets a test
ask the question at any minute of any day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta


def ended_at(day: date) -> datetime:
    """The instant a UTC day closed: 00:00 UTC on the day after it."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)


def is_eligible(day: date, *, now: datetime, after_hours: int) -> bool:
    """Whether at least `after_hours` whole hours have passed since `day` ended.

    `now` must carry its timezone: a naive instant cannot be compared with the
    end of a UTC day, and Python refuses the subtraction rather than guess.
    """
    return now - ended_at(day) >= timedelta(hours=after_hours)
