"""Where do the slices sit for a pair of thresholds, and which slice holds a score?

Unit tier: pure arithmetic over the committed draw settings, nothing opened.
"""

from __future__ import annotations

import itertools

import pytest
from support.judged_pairs import a_judged_pair
from support.paths import CONFIG_DIR

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.knobs.content_similarity_judge import DrawConfig
from idhazh.contracts.story_similarity_pair_verdict import PairBucket
from idhazh.similarity.slices import slice_grid

DRAW = judge_settings.load(CONFIG_DIR).draw


def edges(
    lower: float, upper: float, *, draw: DrawConfig = DRAW
) -> list[tuple[str, float, float]]:
    return [
        (one.bucket.value, one.low, one.high) for one in slice_grid(lower, upper, draw=draw).slices
    ]


def test_the_committed_starts_cut_minus_one_to_one_into_the_five_buckets() -> None:
    """A hand-worked table: 0.70 and 0.93 give 23 straddling slices with exact threshold edges."""
    cut = edges(0.70, 0.93)

    assert cut[0] == ("fully_dissimilar", -1.0, 0.64)
    assert {slice_[0] for slice_ in cut[1:7]} == {"lower_thin"}
    assert [slice_[1:] for slice_ in cut[1:7]] == [
        (0.64, 0.66), (0.66, 0.68), (0.68, 0.70), (0.70, 0.72), (0.72, 0.74), (0.74, 0.76)
    ]
    assert cut[7:10] == [
        ("middle_coarse", 0.76, 0.80), ("middle_coarse", 0.80, 0.84), ("middle_coarse", 0.84, 0.87)
    ]
    assert {slice_[0] for slice_ in cut[10:22]} == {"upper_thin"}
    assert [slice_[1:] for slice_ in cut[10:22]] == [
        (0.87, 0.88), (0.88, 0.89), (0.89, 0.90), (0.90, 0.91), (0.91, 0.92), (0.92, 0.93),
        (0.93, 0.94), (0.94, 0.95), (0.95, 0.96), (0.96, 0.97), (0.97, 0.98), (0.98, 0.99),
    ]
    assert cut[22] == ("fully_similar", 0.99, 1.0)
    assert len(cut) == 23
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(cut)), (
        "every slice starts where the one below it stops"
    )


def test_a_threshold_off_the_grid_rounds_the_lower_down_and_the_upper_up() -> None:
    """Lower rounds down (0.70 -> band 0.64..0.76) and upper rounds up (0.94 -> band 0.88..0.99)."""
    cut = edges(0.705, 0.931)

    lower_edges = {edge for bucket, low, high in cut if bucket == "lower_thin" for edge in (low, high)}
    upper_edges = {edge for bucket, low, high in cut if bucket == "upper_thin" for edge in (low, high)}
    assert cut[0] == ("fully_dissimilar", -1.0, 0.64)
    assert 0.70 in lower_edges and max(lower_edges) == 0.76
    assert 0.94 in upper_edges and min(upper_edges) == 0.88 and max(upper_edges) == 0.99
    assert cut[-1] == ("fully_similar", 0.99, 1.0)


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
    cut = edges(threshold, 0.99)
    lower_edges = {edge for bucket, low, high in cut if bucket == "lower_thin" for edge in (low, high)}
    assert cut[0][2] == round(grid_line - DRAW.thin_band_half_width, 2)
    assert grid_line in lower_edges


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
    assert bucket(0.6399999) == (PairBucket.FULLY_DISSIMILAR, -1.0)
    assert bucket(0.64) == (PairBucket.LOWER_THIN, 0.64)
    assert bucket(0.6999999) == (PairBucket.LOWER_THIN, 0.68)
    assert bucket(0.70) == (PairBucket.LOWER_THIN, 0.70)
    assert bucket(0.76) == (PairBucket.MIDDLE_COARSE, 0.76)
    assert bucket(0.8699999) == (PairBucket.MIDDLE_COARSE, 0.84)
    assert bucket(0.87) == (PairBucket.UPPER_THIN, 0.87)
    assert bucket(0.9299999) == (PairBucket.UPPER_THIN, 0.92)
    assert bucket(0.93) == (PairBucket.UPPER_THIN, 0.93)
    assert bucket(0.9899999) == (PairBucket.UPPER_THIN, 0.98)
    assert bucket(0.99) == (PairBucket.FULLY_SIMILAR, 0.99)
    assert bucket(1.0) == (PairBucket.FULLY_SIMILAR, 0.99), "a shared headline scores exactly 1.0"


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


@pytest.mark.parametrize(
    ("pair_budget", "expected_lower_count", "expected_upper_count"),
    [
        (7, 1, 1),
        (20, 1, 4),
        (60, 4, 12),
        (80, 4, 12),
        (150, 6, 12),
        (300, 12, 12),
    ],
)
def test_straddling_slices_auto_coarsen_cleanly_across_pair_budgets_with_exact_edges(
    pair_budget: int, expected_lower_count: int, expected_upper_count: int
) -> None:
    """Budgets 7..300 auto-coarsen thin bands while keeping thresholds on exact slice edges."""
    scaled = DRAW.model_copy(update={"pair_budget": pair_budget})
    cut = edges(0.70, 0.93, draw=scaled)

    lower_slices = [slice_[1:] for slice_ in cut if slice_[0] == "lower_thin"]
    upper_slices = [slice_[1:] for slice_ in cut if slice_[0] == "upper_thin"]

    assert len(lower_slices) == expected_lower_count
    assert len(upper_slices) == expected_upper_count
    assert (lower_slices[0][0], lower_slices[-1][1]) == (0.64, 0.76)
    assert (upper_slices[0][0], upper_slices[-1][1]) == (0.87, 0.99)
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(cut))
    if expected_lower_count >= 2:
        assert 0.70 in {edge for low, high in lower_slices for edge in (low, high)}
    if expected_upper_count >= 2:
        assert 0.93 in {edge for low, high in upper_slices for edge in (low, high)}

    if pair_budget == 80:
        assert lower_slices == [(0.64, 0.67), (0.67, 0.70), (0.70, 0.73), (0.73, 0.76)]
    if pair_budget == 150:
        assert lower_slices == [
            (0.64, 0.66), (0.66, 0.68), (0.68, 0.70), (0.70, 0.72), (0.72, 0.74), (0.74, 0.76)
        ]
    if pair_budget == 300:
        assert lower_slices == [
            (round(0.64 + 0.01 * i, 2), round(0.65 + 0.01 * i, 2)) for i in range(12)
        ]


@pytest.mark.parametrize(
    ("upper", "expected_upper_count"),
    [(0.95, 10), (0.96, 9), (0.99, 6)],
)
def test_clamping_near_one_preserves_fully_similar_and_produces_valid_verdict_rows(
    upper: float, expected_upper_count: int
) -> None:
    """Clamping at upper=0.95, 0.96, 0.99 preserves FULLY_SIMILAR=[0.99, 1.00] and valid rows."""
    grid = slice_grid(0.70, upper, draw=DRAW)
    cut = [(one.bucket.value, one.low, one.high) for one in grid.slices]
    upper_slices = [slice_[1:] for slice_ in cut if slice_[0] == "upper_thin"]

    assert cut[-1] == ("fully_similar", 0.99, 1.0)
    assert len(upper_slices) == expected_upper_count
    assert upper_slices[0][0] == round(upper - DRAW.thin_band_half_width, 2)
    assert upper_slices[-1][1] == 0.99
    assert upper in {edge for low, high in upper_slices for edge in (low, high)}
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(cut))

    for index, one in enumerate(grid.slices):
        midpoint = round((one.low + one.high) / 2, 6)
        row = a_judged_pair(index, score=midpoint, lower=0.70, upper=upper)
        assert (row.bucket, row.slice_low, row.slice_high) == (one.bucket, one.low, one.high)


def test_unfunded_buckets_and_empty_middle_span_keep_the_grid_contiguous() -> None:
    """Budget=0 buckets emit one full-span slice; zero-width middle emits no slices."""
    tiny = DRAW.model_copy(update={"pair_budget": 1})
    cut = edges(0.70, 0.93, draw=tiny)

    assert cut == [
        ("fully_dissimilar", -1.0, 0.64),
        ("lower_thin", 0.64, 0.76),
        ("middle_coarse", 0.76, 0.87),
        ("upper_thin", 0.87, 0.99),
        ("fully_similar", 0.99, 1.0),
    ]

    no_middle = edges(0.70, 0.82)
    assert not any(bucket == "middle_coarse" for bucket, _, _ in no_middle)
    assert all(earlier[2] == later[1] for earlier, later in itertools.pairwise(no_middle))


def test_min_pairs_per_slice_coarsens_funded_buckets() -> None:
    """Raising min_pairs_per_slice widens steps while keeping both thresholds on exact edges."""
    coarser = DRAW.model_copy(update={"min_pairs_per_slice": 15})
    cut = edges(0.70, 0.93, draw=coarser)

    assert [slice_[1:] for slice_ in cut if slice_[0] == "lower_thin"] == [
        (0.64, 0.70), (0.70, 0.76)
    ]
    assert [slice_[1:] for slice_ in cut if slice_[0] == "middle_coarse"] == [(0.76, 0.87)]
    assert [slice_[1:] for slice_ in cut if slice_[0] == "upper_thin"] == [
        (0.87, 0.89), (0.89, 0.91), (0.91, 0.93), (0.93, 0.95), (0.95, 0.97), (0.97, 0.99)
    ]
