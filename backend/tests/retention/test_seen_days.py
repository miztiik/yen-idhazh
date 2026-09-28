"""Is what the seen window keeps exactly the span of days the planner reads?"""

from __future__ import annotations

from datetime import date, timedelta

from idhazh import day_partition
from idhazh.contracts.knobs.collect import CollectConfig


def test_what_is_kept_is_exactly_what_the_planner_reads() -> None:
    """The margin, in days, over every anchor date a year can offer.

    At month grain the two were only comparable in days: the prune kept whole
    month files and the reader asked for a span of days, so what survived ran 90
    to 120 days against a 90-day window. At day grain they are the same unit and
    the margin is zero on every date - which is a stronger property than the one
    it replaces, and the reason the grain moved.

    Arithmetic over 366 built anchor dates, so it opens no file and reads nothing
    the archive holds.
    """
    window = CollectConfig().seen_window_days
    for offset in range(366):
        anchor = date(2026, 1, 1) + timedelta(days=offset)
        oldest_kept = min(day_partition.days_in_window(anchor.isoformat(), window))
        retained_days = (anchor - date.fromisoformat(oldest_kept)).days
        assert retained_days == window, (
            f"on {anchor} the prune keeps back to {oldest_kept}, which is "
            f"{retained_days} days - the planner reads {window}"
        )
