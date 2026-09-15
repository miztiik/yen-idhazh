"""How many month shards does one read of an N-day window open?"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from functools import lru_cache


@lru_cache(maxsize=16)
def months_a_window_can_touch(within_days: int) -> int:
    """The most `<YYYY-MM>` shards one read of that window can open.

    A window of N days reads N+1 inclusive days - the way
    `ledger.shards_in_window` walks them - and the answer is how many calendar
    months those days fall in. It is not `N / 30`. The extreme is a window that
    ends on the first of a month and starts on the last day of another, which is
    why the committed 366-day console window reaches **14** shards and a
    thirteen-month retention is one shard short of what a reader can still ask
    for.

    Sweeping the month-firsts of one 400-year Gregorian cycle is exact rather
    than a sample. Moving the end date later inside its month spends days that
    would otherwise reach back, so the widest span always ends on a first, and
    the calendar repeats every 400 years.
    """
    if within_days < 0:
        raise ValueError("a window cannot be negative")
    span = timedelta(days=within_days)
    widest = 1
    for year in range(2000, 2400):
        for month in range(1, 13):
            end = date_type(year, month, 1)
            start = end - span
            reach = (end.year * 12 + end.month) - (start.year * 12 + start.month) + 1
            widest = max(widest, reach)
    return widest
