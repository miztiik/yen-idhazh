"""Are refusal and valid-reading rates independent of order and partitioning?"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from idhazh.contracts.story_similarity_pair import SameStoryVerdict
from idhazh.similarity.statistics import PairStatistics, reading_statistics


@dataclass(frozen=True)
class Reading:
    """The three cells the statistics read, which every judged pair carries."""

    verdict: SameStoryVerdict | None
    verdict_swapped: SameStoryVerdict | None
    grammar_applied: bool | None


def pair(forward: str | None, reverse: str | None) -> Reading:
    return Reading(
        None if forward is None else SameStoryVerdict(forward),
        None if reverse is None else SameStoryVerdict(reverse),
        grammar_applied=forward is not None and reverse is not None,
    )


@pytest.mark.parametrize(
    ("forward", "reverse", "expected"),
    [
        (None, "YES", PairStatistics(1, 0, 0, 0)),
        ("YES", None, PairStatistics(1, 0, 0, 0)),
        ("YES", "NO", PairStatistics(1, 1, 0, 0)),
        ("UNCLEAR", "UNCLEAR", PairStatistics(1, 1, 1, 1)),
        (None, None, PairStatistics(1, 0, 0, 0)),
    ],
)
def test_both_orders_define_one_valid_pair_or_one_refusal(
    forward: str | None, reverse: str | None, expected: PairStatistics
) -> None:
    assert reading_statistics([pair(forward, reverse)]) == expected


def test_zero_denominators_are_unavailable_not_perfect_agreement() -> None:
    empty = reading_statistics([])
    refused = reading_statistics([pair(None, None)])
    disagreed = reading_statistics([pair("YES", "NO")])

    assert empty.disagreement_rate is empty.unclear_rate is None
    assert refused.refused == 1
    assert refused.disagreement_rate is refused.unclear_rate is None
    assert disagreed.disagreement_rate == 1.0
    assert disagreed.unclear_rate is None


def test_swapping_failure_order_and_recombining_shards_keeps_counts_and_rates() -> None:
    rows = [
        pair(None, "YES"), pair("NO", "YES"),
        pair("UNCLEAR", "UNCLEAR"), pair("YES", "YES"), pair(None, None),
    ]
    swapped = [
        pair(
            None if row.verdict_swapped is None else row.verdict_swapped.value,
            None if row.verdict is None else row.verdict.value,
        )
        for row in rows
    ]
    stats = reading_statistics(rows)
    assert stats == reading_statistics(swapped) == PairStatistics(5, 3, 2, 1)
    assert (stats.refused, stats.disagreement_rate, stats.unclear_rate) == (2, 1 / 3, 1 / 2)
    partitions: Sequence[Sequence[Reading]] = (rows[:1], rows[1:4], rows[4:])
    combined = PairStatistics(
        *(sum(getattr(reading_statistics(part), field) for part in partitions)
          for field in ("attempted", "valid", "agreed", "unclear"))
    )
    assert combined == stats
    assert combined.disagreement_rate == stats.disagreement_rate
    assert combined.unclear_rate == stats.unclear_rate


def test_legacy_readings_with_no_grammar_flag_remain_readable_under_their_own_method() -> None:
    legacy = Reading(SameStoryVerdict.UNCLEAR, SameStoryVerdict.UNCLEAR, grammar_applied=None)
    assert reading_statistics([legacy]) == PairStatistics(1, 1, 1, 1)
