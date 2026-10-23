"""Which availability facts hold for every order allowed by saved observation times?"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.recorded_instant import instant_bounds


def observation_groups(rows: Iterable[FeedHealthRow]) -> list[list[FeedHealthRow]]:
    """Overlapping precision intervals carry no inferred chronological order."""
    ordered = sorted(rows, key=lambda row: (*instant_bounds(row.checked_at), row.run_id))
    groups: list[list[FeedHealthRow]] = []
    upper: int | None = None
    for row in ordered:
        lower, end = instant_bounds(row.checked_at)
        if upper is None or lower >= upper:
            groups.append([])
            upper = end
        else:
            upper = max(upper, end)
        groups[-1].append(row)
    return groups


@dataclass(frozen=True, slots=True)
class AvailabilityEvidence:
    """Exact counts or unavailable values; resting is proved, disproved or unknown."""

    strikes: int | None
    rested_runs: int | None
    resting: bool | None
    failing: bool | None


def availability_evidence(
    rows: Iterable[FeedHealthRow], *, after_failures: int | None = None
) -> AvailabilityEvidence:
    """Bounds use only definite interval precedence, without permutation enumeration."""
    if after_failures is not None and after_failures < 1:
        raise ValueError("after_failures must be positive")
    held = list(rows)
    strikes_low, strikes_high = _count_after(
        [row for row in held if row.failing],
        [row for row in held if not row.failing and not row.preserves],
    )
    skips_low, skips_high = _count_after(
        [row for row in held if row.outcome is FetchOutcome.SKIPPED],
        [row for row in held if row.outcome is not FetchOutcome.SKIPPED],
    )
    resting: bool | None = None
    if after_failures is not None:
        if strikes_low >= after_failures and skips_high < after_failures:
            resting = True
        elif strikes_high < after_failures or skips_low >= after_failures:
            resting = False
    return AvailabilityEvidence(
        strikes=strikes_low if strikes_low == strikes_high else None,
        rested_runs=skips_low if skips_low == skips_high else None,
        resting=resting,
        failing=True if strikes_low > 0 else False if strikes_high == 0 else None,
    )


def _count_after(values: list[FeedHealthRow], resets: list[FeedHealthRow]) -> tuple[int, int]:
    if not resets:
        return len(values), len(values)
    last_start = max(instant_bounds(row.checked_at)[0] for row in resets)
    last_end = max(instant_bounds(row.checked_at)[1] for row in resets)
    return (
        sum(instant_bounds(row.checked_at)[0] >= last_end for row in values),
        sum(instant_bounds(row.checked_at)[1] > last_start for row in values),
    )


def latest_observations(rows: Iterable[FeedHealthRow]) -> list[FeedHealthRow]:
    """Only observations not definitely followed by another can be the latest."""
    held = list(rows)
    if not held:
        return []
    last_start = max(instant_bounds(row.checked_at)[0] for row in held)
    return [row for row in held if instant_bounds(row.checked_at)[1] > last_start]
