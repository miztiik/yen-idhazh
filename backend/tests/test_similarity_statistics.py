"""Are refusal and valid-reading rates independent of order and partitioning?"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pytest
from support.judged_pairs import a_reading

from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.story_similarity_pair_verdict import SameStoryVerdict
from idhazh.similarity.statistics import (
    PairStatistics,
    combined_statistics,
    reading_statistics,
    shipped_statistics,
)


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


def a_shipped(
    *, read: int, agreed: int, unclear_rate: float | None, refused: int = 0
) -> ContentSimilarityJudgeMetrics:
    """One runner's shipped reading with these counts, the rest of its funnel left as it was."""
    return a_reading(
        shard=0, dealt=read + refused, date="2026-11-18", run_id="2026-11-18-9"
    ).model_copy(
        update={
            "pairs_read": read,
            "pairs_agreed": agreed,
            "pairs_refused": refused,
            "unclear_rate": unclear_rate,
        }
    )


def test_a_shipped_reading_gives_back_the_counts_its_rates_were_made_from() -> None:
    """Nine valid pairs and two refused, six agreed and a third of those UNCLEAR: 2 of 6."""
    stats = shipped_statistics(a_shipped(read=9, agreed=6, unclear_rate=1 / 3, refused=2))

    assert stats == PairStatistics(attempted=11, valid=9, agreed=6, unclear=2)
    assert shipped_statistics(a_shipped(read=4, agreed=0, unclear_rate=None)).unclear == 0


def test_runners_are_counted_as_one_lot_so_a_big_runner_outweighs_a_small_one() -> None:
    """Ten pairs of which 2 were UNCLEAR and two pairs of which 1 was: 3 of 12, not 35 percent.

    Averaging the two runners' own rates, 0.2 and 0.5, would give 0.35 and weigh the runner
    that read two pairs as much as the runner that read ten.
    """
    big = shipped_statistics(a_shipped(read=10, agreed=10, unclear_rate=0.2))
    small = shipped_statistics(a_shipped(read=2, agreed=2, unclear_rate=0.5))

    combined = combined_statistics([big, small])

    assert combined == PairStatistics(attempted=12, valid=12, agreed=12, unclear=3)
    assert combined.unclear_rate == pytest.approx(0.25)
