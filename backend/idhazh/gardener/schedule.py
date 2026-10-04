"""Is a UTC day, month or year old enough for the gardener to act on at a given instant?

**A period's end is a fact and a wake is not.** A day ended at 00:00 UTC on the
day after it, a month at 00:00 UTC on the first of the month after it and a year
at 00:00 UTC on 1 January after it, whenever the job that asks happened to wake,
so whether a period is old enough is measured from that instant and never from
the wake. Moving a schedule therefore cannot change which periods qualify - it
only changes when the question is next asked (CLAUDE.md section 2).

**The wait is whole days, so every wake of one UTC day gets the same answer.**
A period ends at 00:00 UTC and a whole number of days after it is 00:00 UTC
too, so the answer changes only at midnight. A wait counted in hours would
change it at some hour inside the day, and the wake time would then decide
which periods qualify.

Nothing here reads a clock. The instant is handed in, which is what lets a test
ask the question at any minute of any day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta


def ended_at(day: date) -> datetime:
    """The instant a UTC day closed: 00:00 UTC on the day after it."""
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)


def is_eligible(day: date, *, now: datetime, after_days: int) -> bool:
    """Whether at least `after_days` whole days have passed since `day` ended.

    `now` must carry its timezone: a naive instant cannot be compared with the
    end of a UTC day, and Python refuses the subtraction rather than guess.
    """
    return now - ended_at(day) >= timedelta(days=after_days)


def newest_eligible(*, now: datetime, after_days: int) -> date:
    """The newest day `is_eligible` says yes to at `now`.

    A day is eligible once 00:00 UTC on the day `after_days + 1` after it has
    come, so the newest is that many days before `now`'s own UTC day.
    """
    return now.astimezone(UTC).date() - timedelta(days=after_days + 1)


def month_ended_at(month: str) -> datetime:
    """The instant a UTC month closed: 00:00 UTC on the first of the month after it.

    `month` is `YYYY-MM`, the stamp a monthly period carries.
    """
    year, number = int(month[:4]), int(month[5:7])
    return datetime(year + number // 12, number % 12 + 1, 1, tzinfo=UTC)


def is_month_eligible(month: str, *, now: datetime, after_days: int) -> bool:
    """Whether at least `after_days` whole days have passed since `month` ended."""
    return now - month_ended_at(month) >= timedelta(days=after_days)


def newest_eligible_month(*, now: datetime, after_days: int) -> str:
    """The newest `YYYY-MM` month `is_month_eligible` says yes to at `now`.

    A month ends at 00:00 UTC on the first of the next, so it is eligible once
    that first is at least `after_days` days before `now`: the month before the
    one holding the day `after_days` back.
    """
    back = now.astimezone(UTC).date() - timedelta(days=after_days)
    total = back.year * 12 + back.month - 2
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def year_ended_at(year: str) -> datetime:
    """The instant a UTC year closed: 00:00 UTC on 1 January of the year after it.

    `year` is `YYYY`, the stamp a yearly period carries.
    """
    return datetime(int(year) + 1, 1, 1, tzinfo=UTC)


def is_year_eligible(year: str, *, now: datetime, after_days: int) -> bool:
    """Whether at least `after_days` whole days have passed since `year` ended."""
    return now - year_ended_at(year) >= timedelta(days=after_days)
