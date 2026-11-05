"""Are refusal and valid-reading rates independent of order and partitioning?"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from test_similarity_counting import a_row

from idhazh.contracts.story_similarity_pair import SameStoryVerdict, StorySimilarityPair
from idhazh.similarity.statistics import PairStatistics, reading_statistics


def pair(forward: str | None, reverse: str | None, index: int = 0) -> StorySimilarityPair:
    raw = a_row(score=0.55, pair=index).model_dump(mode="json") | {
        "verdict": forward, "verdict_swapped": reverse,
        "grammar_applied": forward is not None and reverse is not None,
        "usable": forward is not None and forward == reverse,
    }
    return StorySimilarityPair.model_validate(raw)


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
        pair(None, "YES", 0), pair("NO", "YES", 1),
        pair("UNCLEAR", "UNCLEAR", 2), pair("YES", "YES", 3), pair(None, None, 4),
    ]
    swapped = [
        pair(
            None if row.verdict_swapped is None else row.verdict_swapped.value,
            None if row.verdict is None else row.verdict.value,
            index,
        )
        for index, row in enumerate(rows)
    ]
    stats = reading_statistics(rows)
    assert stats == reading_statistics(swapped) == PairStatistics(5, 3, 2, 1)
    assert (stats.refused, stats.disagreement_rate, stats.unclear_rate) == (2, 1 / 3, 1 / 2)
    partitions: Sequence[Sequence[StorySimilarityPair]] = (rows[:1], rows[1:4], rows[4:])
    combined = PairStatistics(
        *(sum(getattr(reading_statistics(part), field) for part in partitions)
          for field in ("attempted", "valid", "agreed", "unclear"))
    )
    assert combined == stats
    assert combined.disagreement_rate == stats.disagreement_rate
    assert combined.unclear_rate == stats.unclear_rate


def test_legacy_readings_with_no_grammar_flag_remain_readable_under_their_own_method() -> None:
    row = a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR).model_copy(update={
        "judge_policy_version": None, "grammar_applied": None,
    })
    assert reading_statistics([row]) == PairStatistics(1, 1, 1, 1)
