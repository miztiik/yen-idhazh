"""How many pairs does each slice give, for a budget and what each slice held?

Unit tier: integer arithmetic over named pools. Every expected number below is worked by
hand from the committed settings (150 pairs split proportionally across all five buckets
at weights 5, 20, 10, 60 and 5), so a changed rule shows as a changed number a person can
follow.
"""

from __future__ import annotations

import pytest
from support.paths import CONFIG_DIR

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.knobs.content_similarity_judge import DrawBucketWeights
from idhazh.contracts.story_similarity_pair_verdict import PairBucket
from idhazh.similarity.draw_allocation import allocate, per_slice_cap, share_out
from idhazh.similarity.slices import Slice, slice_grid

DRAW = judge_settings.load(CONFIG_DIR).draw

#: The 23 slices at the committed starts: the end below 0.64, six straddling 0.02 slices
#: around 0.70, three coarse slices across the middle, twelve straddling 0.01 slices around
#: 0.93, and the end above 0.99.
SLICES = slice_grid(0.70, 0.93, draw=DRAW).slices

PLENTY = 10_000


def pools_of(
    *,
    slices: tuple[Slice, ...] = SLICES,
    dissimilar: int = PLENTY,
    lower: int = PLENTY,
    middle: int = PLENTY,
    upper: int = PLENTY,
    similar: int = PLENTY,
) -> list[int]:
    """Every slice of a bucket holding the same number of pairs."""
    held = {
        PairBucket.FULLY_DISSIMILAR: dissimilar,
        PairBucket.LOWER_THIN: lower,
        PairBucket.MIDDLE_COARSE: middle,
        PairBucket.UPPER_THIN: upper,
        PairBucket.FULLY_SIMILAR: similar,
    }
    return [held[one.bucket] for one in slices]


def takes_by_bucket(
    takes: tuple[int, ...], *, slices: tuple[Slice, ...] = SLICES
) -> dict[str, int]:
    totals: dict[str, int] = {}
    for one, count in zip(slices, takes, strict=True):
        totals[one.bucket.value] = totals.get(one.bucket.value, 0) + count
    return totals


def test_a_night_with_pairs_everywhere_spends_the_budget_by_the_weights() -> None:
    """150 pairs split by unified weights 5, 20, 10, 60 and 5 give 8, 30, 15, 90 and 7."""
    takes = allocate(SLICES, pools_of(), draw=DRAW)

    assert takes_by_bucket(takes) == {
        "fully_dissimilar": 8,
        "lower_thin": 30,
        "middle_coarse": 15,
        "upper_thin": 90,
        "fully_similar": 7,
    }
    assert takes == (
        8,
        5, 5, 5, 5, 5, 5,
        5, 5, 5,
        8, 8, 8, 8, 8, 8, 7, 7, 7, 7, 7, 7,
        7,
    )
    assert sum(takes) == DRAW.pair_budget


def test_a_slice_that_holds_less_than_its_share_takes_all_and_the_others_split_the_rest() -> None:
    """Lower thin: a budget of 62 over slices holding 3, then plenty, is 3, 12, 12, 12, 12, 11."""
    assert share_out(62, [3, 100, 100, 100, 100, 100]) == [3, 12, 12, 12, 12, 11]


def test_sparse_buckets_and_short_ends_do_not_pad_other_buckets() -> None:
    """Unspent pairs stay unspent so sparse nights draw fewer than pair_budget pairs."""
    sparse = allocate(SLICES, pools_of(middle=2, upper=1, similar=2), draw=DRAW)

    assert takes_by_bucket(sparse) == {
        "fully_dissimilar": 8,
        "lower_thin": 30,
        "middle_coarse": 6,
        "upper_thin": 12,
        "fully_similar": 2,
    }
    assert sum(sparse) == 58 < DRAW.pair_budget

    empty_ends = allocate(SLICES, pools_of(dissimilar=0, similar=0), draw=DRAW)

    assert takes_by_bucket(empty_ends) == {
        "fully_dissimilar": 0,
        "lower_thin": 30,
        "middle_coarse": 15,
        "upper_thin": 90,
        "fully_similar": 0,
    }
    assert sum(empty_ends) == 135 < DRAW.pair_budget


def test_slice_overflow_factor_scales_per_slice_cap_without_exceeding_bucket_ceiling() -> None:
    """Sibling slices absorb at most per_slice_cap and never push a bucket past its ceiling."""
    strict = DRAW.model_copy(update={"slice_overflow_factor": 1.0})
    pools = pools_of()
    pools[1] = 2  # first lower_thin slice is sparse
    strict_takes = allocate(SLICES, pools, draw=strict)
    assert strict_takes[1:7] == (2, 5, 5, 5, 5, 5)
    assert sum(strict_takes[1:7]) == 27 < 30

    # Committed slice_overflow_factor=1.5 allows siblings to absorb up to ceil((B/k) * 1.5).
    assert per_slice_cap(90, 12, overflow_factor=1.5) == 12
    assert per_slice_cap(30, 6, overflow_factor=1.5) == 8

    one_upper = pools_of(upper=0)
    one_upper[10] = 100
    assert allocate(SLICES, one_upper, draw=DRAW)[10:22] == (12, *([0] * 11))

    eight_upper = pools_of(upper=0)
    for index in range(10, 18):
        eight_upper[index] = 100
    eight_takes = allocate(SLICES, eight_upper, draw=DRAW)[10:22]
    assert eight_takes == (12, 12, 11, 11, 11, 11, 11, 11, 0, 0, 0, 0)
    assert sum(eight_takes) == 90

    # Scaling pair_budget scales per_slice_cap linearly with bucket budget.
    doubled = DRAW.model_copy(update={"pair_budget": 300})
    assert per_slice_cap(
        doubled.bucket_budgets()[PairBucket.UPPER_THIN], 12, overflow_factor=1.5
    ) == 23
    base_200 = DRAW.model_copy(update={"pair_budget": 200})
    double_400 = DRAW.model_copy(update={"pair_budget": 400})
    assert per_slice_cap(
        double_400.bucket_budgets()[PairBucket.UPPER_THIN], 12, overflow_factor=1.5
    ) == 2 * per_slice_cap(
        base_200.bucket_budgets()[PairBucket.UPPER_THIN], 12, overflow_factor=1.5
    )


@pytest.mark.parametrize("pair_budget", [1, 7, 20, 60, 80, 150, 300])
def test_sweeping_pair_budget_auto_scales_slices_and_respects_all_caps(pair_budget: int) -> None:
    """Any pair_budget >= 1 produces a drawable grid that respects bucket and slice caps."""
    scaled = DRAW.model_copy(update={"pair_budget": pair_budget})
    grid = slice_grid(0.70, 0.93, draw=scaled)
    budgets = scaled.bucket_budgets()
    counts_by_bucket = {
        bucket: sum(1 for one in grid.slices if one.bucket is bucket) for bucket in PairBucket
    }

    for pools in (
        pools_of(slices=grid.slices),
        pools_of(slices=grid.slices, lower=2, middle=1, upper=3, similar=1, dissimilar=2),
        [index % 3 * 5 for index in range(len(grid.slices))],
    ):
        takes = allocate(grid.slices, pools, draw=scaled)
        bucket_totals = takes_by_bucket(takes, slices=grid.slices)

        assert sum(takes) <= pair_budget
        for bucket in PairBucket:
            assert bucket_totals.get(bucket.value, 0) <= budgets[bucket]
        for one, pool, take in zip(grid.slices, pools, takes, strict=True):
            budget = budgets[one.bucket]
            cap = per_slice_cap(
                budget, counts_by_bucket[one.bucket], overflow_factor=scaled.slice_overflow_factor
            )
            assert 0 <= take <= min(pool, cap)
            if budget == 0 or pool == 0:
                assert take == 0
            else:
                assert take >= 1

    full_takes = allocate(grid.slices, pools_of(slices=grid.slices), draw=scaled)
    assert sum(full_takes) == pair_budget


@pytest.mark.parametrize(
    "pools",
    [
        pools_of(),
        pools_of(lower=1, middle=1, upper=1),
        pools_of(lower=7, middle=3, upper=40, similar=5, dissimilar=2),
        [PLENTY, 0, 0, 0, 0, 0, 0, 2, 0, 9, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 1],
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
    """Equal weights across all five buckets split 152 as 31, 31, 30, 30 and 30 in score order."""
    equal = DRAW.model_copy(
        update={
            "pair_budget": 152,
            "bucket_weights": DrawBucketWeights(
                fully_dissimilar=1,
                lower_thin=1,
                middle_coarse=1,
                upper_thin=1,
                fully_similar=1,
            ),
        }
    )

    totals = takes_by_bucket(allocate(SLICES, pools_of(), draw=equal))

    assert [totals[bucket.value] for bucket in PairBucket] == [31, 31, 30, 30, 30]


def test_a_budget_that_cannot_give_every_held_slice_a_pair_is_refused_by_name() -> None:
    """An uncoarsened slice list is refused; slice_grid coarsens the same budget cleanly."""
    small = DRAW.model_copy(update={"pair_budget": 14})

    with pytest.raises(ValueError, match="raise pair_budget"):
        allocate(SLICES, pools_of(), draw=small)

    coarsened = slice_grid(0.70, 0.93, draw=small).slices
    assert sum(allocate(coarsened, pools_of(slices=coarsened), draw=small)) == 14


def test_the_allocation_is_a_function_of_its_inputs() -> None:
    """The same pools and the same settings give the same takes, which is what a re-run needs."""
    pools = [4000, 3, 9, 1, 22, 40, 0, 12, 6, 2, 31, 7, 5, 8, 19, 40, 11, 6, 4, 9, 2, 15, 11]

    assert allocate(SLICES, pools, draw=DRAW) == allocate(SLICES, pools, draw=DRAW)


def test_a_pool_for_every_slice_is_required() -> None:
    with pytest.raises(ValueError, match="one pool"):
        allocate(SLICES[:2], [1, 2, 3], draw=DRAW)
