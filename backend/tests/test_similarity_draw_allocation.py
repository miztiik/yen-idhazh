"""How many pairs does each slice give, for a budget and what each slice held?

Unit tier: integer arithmetic over named pools. Every expected number below is worked by
hand from the committed settings (150 pairs; weights 40, 30 and 20 between the thresholds;
the lightly sampled ends at 6 and 4), so a changed rule shows as a changed number a person
can follow.
"""

from __future__ import annotations

import pytest
from support.paths import CONFIG_DIR

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.story_similarity_pair_verdict import PairBucket
from idhazh.similarity.draw_allocation import allocate, share_out
from idhazh.similarity.slices import slice_grid

DRAW = judge_settings.load(CONFIG_DIR).draw

#: The slices at the committed starts: the end below, six thin and three coarse slices
#: from the lower threshold, six thin slices to the upper one, and the end above.
SLICES = slice_grid(0.70, 0.93, draw=DRAW).slices

PLENTY = 10_000


def pools_of(*, dissimilar: int = PLENTY, lower: int = PLENTY, middle: int = PLENTY,
             upper: int = PLENTY, similar: int = PLENTY) -> list[int]:
    """Every slice of a bucket holding the same number of pairs."""
    held = {
        PairBucket.FULLY_DISSIMILAR: dissimilar,
        PairBucket.LOWER_THIN: lower,
        PairBucket.MIDDLE_COARSE: middle,
        PairBucket.UPPER_THIN: upper,
        PairBucket.FULLY_SIMILAR: similar,
    }
    return [held[one.bucket] for one in SLICES]


def takes_by_bucket(takes: tuple[int, ...]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for one, count in zip(SLICES, takes, strict=True):
        totals[one.bucket.value] = totals.get(one.bucket.value, 0) + count
    return totals


def test_a_night_with_pairs_everywhere_spends_the_budget_by_the_weights() -> None:
    """150 pairs: the ends take 4 and 6 (their maxima), the other 140 split 62, 47 and 31.

    The ends' targets are 4 percent and 6 percent of the budget, which is 6 and 9 pairs,
    and their maxima of 4 and 6 are lower. What is left, 140, goes by weights 40, 30 and
    20, which is 62.2, 46.7 and 31.1, so the pair the fractions leave over goes to the
    largest fraction, the upper thin slices. Inside a bucket the share is equal: 62 over
    six slices is 11, 11, 10, 10, 10, 10.
    """
    takes = allocate(SLICES, pools_of(), draw=DRAW)

    assert takes_by_bucket(takes) == {
        "fully_dissimilar": 4,
        "lower_thin": 62,
        "middle_coarse": 31,
        "upper_thin": 47,
        "fully_similar": 6,
    }
    assert takes == (4, 11, 11, 10, 10, 10, 10, 11, 10, 10, 8, 8, 8, 8, 8, 7, 6)
    assert sum(takes) == DRAW.pair_budget


def test_a_slice_that_holds_less_than_its_share_takes_all_and_the_others_split_the_rest() -> None:
    """Lower thin: a budget of 62 over slices holding 3, then plenty, is 3, 12, 12, 12, 12, 11."""
    assert share_out(62, [3, 100, 100, 100, 100, 100]) == [3, 12, 12, 12, 12, 11]


def test_a_bucket_that_holds_less_than_its_share_hands_the_rest_on_by_weight() -> None:
    """The coarse slices hold six pairs, so 25 of their 31 go to the heaviest bucket with room."""
    pools = pools_of(middle=2)  # three coarse slices of two pairs

    takes = allocate(SLICES, pools, draw=DRAW)

    assert takes_by_bucket(takes) == {
        "fully_dissimilar": 4,
        "lower_thin": 62 + 25,
        "middle_coarse": 6,
        "upper_thin": 47,
        "fully_similar": 6,
    }
    assert sum(takes) == DRAW.pair_budget


def test_the_night_judges_fewer_than_the_budget_only_when_every_slice_between_is_spent() -> None:
    """Between the thresholds every slice holds five pairs, which is 75 of the 140."""
    takes = allocate(SLICES, pools_of(lower=5, middle=5, upper=5), draw=DRAW)

    between = [count for one, count in zip(SLICES, takes, strict=True)
               if one.bucket not in (PairBucket.FULLY_DISSIMILAR, PairBucket.FULLY_SIMILAR)]
    assert between == [5] * 15, "every slice between the thresholds was taken whole"
    assert sum(takes) == 4 + 6 + 75 < DRAW.pair_budget


def test_a_lightly_sampled_end_is_raised_to_its_minimum_and_never_past_what_it_holds() -> None:
    """With 150 pairs the similar end would take 6, and holding three it takes three."""
    assert takes_by_bucket(allocate(SLICES, pools_of(similar=3), draw=DRAW))["fully_similar"] == 3
    assert takes_by_bucket(allocate(SLICES, pools_of(similar=1), draw=DRAW))["fully_similar"] == 1
    assert takes_by_bucket(allocate(SLICES, pools_of(dissimilar=0), draw=DRAW))[
        "fully_dissimilar"
    ] == 0

    small = DRAW.model_copy(update={"pair_budget": 30})
    assert takes_by_bucket(allocate(SLICES, pools_of(), draw=small))["fully_similar"] == 2, (
        "30 pairs give the similar end 6 percent, under one pair, and its minimum raises it to 2"
    )


@pytest.mark.parametrize(
    "pools",
    [
        pools_of(),
        pools_of(lower=1, middle=1, upper=1),
        pools_of(lower=7, middle=3, upper=40, similar=5, dissimilar=2),
        [PLENTY, 0, 0, 0, 0, 0, 0, 2, 0, 9, 0, 0, 0, 0, 0, 4, 1],
    ],
    ids=["plenty", "one each", "uneven", "mostly empty"],
)
def test_every_slice_that_holds_a_pair_gives_one_and_none_gives_more_than_it_holds(
    pools: list[int],
) -> None:
    takes = allocate(SLICES, pools, draw=DRAW)

    assert all(1 <= count <= pool for count, pool in zip(takes, pools, strict=True) if pool)
    assert all(count == 0 for count, pool in zip(takes, pools, strict=True) if not pool)
    assert sum(takes) <= DRAW.pair_budget


def test_a_changed_weight_changes_the_allocation() -> None:
    """The weights are config, and equal weights give each bucket between the thresholds a third.

    140 over three equal weights is 46 each and two left over, and a tie in the fractions
    goes to the buckets in score order: the lower thin slices, then the coarse ones.
    """
    equal = DRAW.model_copy(update={"bucket_weights": DRAW.bucket_weights.model_copy(
        update={"lower_thin": 1, "upper_thin": 1, "middle_coarse": 1}
    )})

    totals = takes_by_bucket(allocate(SLICES, pools_of(), draw=equal))

    assert (totals["lower_thin"], totals["middle_coarse"], totals["upper_thin"]) == (47, 47, 46)


def test_a_budget_that_cannot_give_every_held_slice_a_pair_is_refused_by_name() -> None:
    """A silent zero would file the slice under no chance, so the night is refused first."""
    small = DRAW.model_copy(update={"pair_budget": 14})

    with pytest.raises(ValueError, match="raise pair_budget"):
        allocate(SLICES, pools_of(), draw=small)


def test_a_budget_below_the_minimums_of_the_two_ends_is_refused() -> None:
    tiny = DRAW.model_copy(update={"pair_budget": 2})

    with pytest.raises(ValueError, match="pair_budget 2"):
        allocate(SLICES, pools_of(), draw=tiny)


def test_the_allocation_is_a_function_of_its_inputs() -> None:
    """The same pools and the same settings give the same takes, which is what a re-run needs."""
    pools = [4000, 3, 9, 1, 22, 40, 0, 12, 6, 2, 31, 7, 5, 8, 19, 40, 11]

    assert allocate(SLICES, pools, draw=DRAW) == allocate(SLICES, pools, draw=DRAW)


def test_a_pool_for_every_slice_is_required() -> None:
    with pytest.raises(ValueError, match="one pool"):
        allocate(SLICES[:2], [1, 2, 3], draw=DRAW)
