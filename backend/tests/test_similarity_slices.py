"""Where do the slices sit for a pair of thresholds, and which slice holds a score?

Unit tier: pure arithmetic over the committed draw settings, nothing opened.
"""

from __future__ import annotations

import itertools

import pytest
from support.paths import CONFIG_DIR

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.story_similarity_pair_verdict import PairBucket
from idhazh.similarity.slices import slice_grid

DRAW = judge_settings.load(CONFIG_DIR).draw


def edges(lower: float, upper: float) -> list[tuple[str, float, float]]:
    return [
        (one.bucket.value, one.low, one.high) for one in slice_grid(lower, upper, draw=DRAW).slices
    ]


def test_the_committed_starts_cut_minus_one_to_one_into_the_five_buckets() -> None:
    """A hand-worked table: 0.70 and 0.93 give 17 slices, the last coarse one the narrower."""
    cut = edges(0.70, 0.93)

    assert cut[0] == ("fully_dissimilar", -1.0, 0.70)
    assert {slice_[0] for slice_ in cut[1:7]} == {"lower_thin"}
    assert [slice_[1:] for slice_ in cut[1:7]] == [
        (0.70, 0.71), (0.71, 0.72), (0.72, 0.73), (0.73, 0.74), (0.74, 0.75), (0.75, 0.76)
    ]
    assert cut[7:10] == [
        ("middle_coarse", 0.76, 0.80), ("middle_coarse", 0.80, 0.84), ("middle_coarse", 0.84, 0.87)
    ]
    assert [slice_[1:] for slice_ in cut[10:16]] == [
        (0.87, 0.88), (0.88, 0.89), (0.89, 0.90), (0.90, 0.91), (0.91, 0.92), (0.92, 0.93)
    ]
    assert {slice_[0] for slice_ in cut[10:16]} == {"upper_thin"}
    assert cut[16] == ("fully_similar", 0.93, 1.0)
    assert len(cut) == 17
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(cut)), (
        "every slice starts where the one below it stops"
    )


def test_a_threshold_off_the_grid_rounds_the_lower_down_and_the_upper_up() -> None:
    """The ambiguous range is never narrower than the thresholds say."""
    cut = edges(0.705, 0.931)

    assert cut[0][2] == 0.70, "the lower threshold rounds down"
    assert cut[-1][1] == 0.94, "the upper threshold rounds up"


@pytest.mark.parametrize(
    ("threshold", "grid_line"),
    [(0.58, 0.58), (0.70 - 0.02, 0.68), (0.57, 0.57), (0.29, 0.29)],
)
def test_a_threshold_a_rounding_error_below_a_grid_line_sits_on_it(
    threshold: float, grid_line: float
) -> None:
    """`floor(0.58 / 0.01)` is 57 in floating point, and 0.70 - 0.02 is 0.6799999999999999.

    A threshold the arithmetic put a digit below a grid line is on the line, because a
    lower threshold that fell to the slice below would widen the ambiguous range by one
    whole slice that the threshold never named.
    """
    assert edges(threshold, 0.99)[0][2] == grid_line


def test_the_remainder_of_the_middle_is_the_last_coarse_slice() -> None:
    """A middle that divides by the coarse width leaves no narrow slice."""
    cut = edges(0.70, 0.94)

    assert [slice_[1:] for slice_ in cut if slice_[0] == "middle_coarse"] == [
        (0.76, 0.80), (0.80, 0.84), (0.84, 0.88)
    ]


def test_a_score_on_an_edge_belongs_to_the_slice_above_and_the_top_slice_holds_one() -> None:
    grid = slice_grid(0.70, 0.93, draw=DRAW)

    def bucket(score: float) -> tuple[PairBucket, float]:
        held = grid.slices[grid.index_of(score)]
        return held.bucket, held.low

    assert bucket(-1.0) == (PairBucket.FULLY_DISSIMILAR, -1.0)
    assert bucket(0.6999999) == (PairBucket.FULLY_DISSIMILAR, -1.0)
    assert bucket(0.70) == (PairBucket.LOWER_THIN, 0.70)
    assert bucket(0.76) == (PairBucket.MIDDLE_COARSE, 0.76)
    assert bucket(0.8699999) == (PairBucket.MIDDLE_COARSE, 0.84)
    assert bucket(0.87) == (PairBucket.UPPER_THIN, 0.87)
    assert bucket(0.9299999) == (PairBucket.UPPER_THIN, 0.92)
    assert bucket(0.93) == (PairBucket.FULLY_SIMILAR, 0.93)
    assert bucket(1.0) == (PairBucket.FULLY_SIMILAR, 0.93), "a shared headline scores exactly 1.0"


@pytest.mark.parametrize(
    ("lower", "upper", "refused"),
    [
        (0.70, 0.80, "too close"),
        (0.93, 0.70, "too close"),
        (-1.0, 0.93, "no room below"),
        (0.70, 1.0, "no room above"),
    ],
)
def test_thresholds_the_slices_cannot_be_cut_from_are_refused(
    lower: float, upper: float, refused: str
) -> None:
    """A draw cut from thresholds it cannot honour would file pairs under no explainable slice."""
    with pytest.raises(ValueError, match=refused):
        slice_grid(lower, upper, draw=DRAW)


def test_small_pair_budget_auto_coarsens_multi_slice_buckets_without_gaps() -> None:
    """At pair_budget=7, bucket ceilings 0/3/1/2/1 coarsen slices so every funded slice fits."""
    small = DRAW.model_copy(update={"pair_budget": 7})
    cut = [(one.bucket.value, one.low, one.high) for one in slice_grid(0.70, 0.93, draw=small).slices]

    assert cut == [
        ("fully_dissimilar", -1.0, 0.70),
        ("lower_thin", 0.70, 0.72),
        ("lower_thin", 0.72, 0.74),
        ("lower_thin", 0.74, 0.76),
        ("middle_coarse", 0.76, 0.87),
        ("upper_thin", 0.87, 0.90),
        ("upper_thin", 0.90, 0.93),
        ("fully_similar", 0.93, 1.0),
    ]
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(cut))


def test_unfunded_buckets_and_empty_middle_span_keep_the_grid_contiguous() -> None:
    """Budget=0 buckets emit one full-span slice; zero-width middle emits no slices."""
    tiny = DRAW.model_copy(update={"pair_budget": 1})
    cut = [(one.bucket.value, one.low, one.high) for one in slice_grid(0.70, 0.93, draw=tiny).slices]

    assert cut == [
        ("fully_dissimilar", -1.0, 0.70),
        ("lower_thin", 0.70, 0.76),
        ("middle_coarse", 0.76, 0.87),
        ("upper_thin", 0.87, 0.93),
        ("fully_similar", 0.93, 1.0),
    ]

    no_middle = edges(0.70, 0.82)
    assert not any(bucket == "middle_coarse" for bucket, _, _ in no_middle)
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(no_middle))


def test_min_pairs_per_slice_coarsens_funded_buckets() -> None:
    """Raising min_pairs_per_slice widens steps so funded buckets emit fewer slices."""
    coarser = DRAW.model_copy(update={"min_pairs_per_slice": 15})
    cut = [
        (one.bucket.value, one.low, one.high)
        for one in slice_grid(0.70, 0.93, draw=coarser).slices
    ]

    assert [slice_[1:] for slice_ in cut if slice_[0] == "lower_thin"] == [
        (0.70, 0.72), (0.72, 0.74), (0.74, 0.76)
    ]
    assert [slice_[1:] for slice_ in cut if slice_[0] == "middle_coarse"] == [
        (0.76, 0.82), (0.82, 0.87)
    ]
    assert [slice_[1:] for slice_ in cut if slice_[0] == "upper_thin"] == [
        (0.87, 0.89), (0.89, 0.91), (0.91, 0.93)
    ]
