"""Where do tonight's slices of the score range sit, and which slice holds a given score?

A slice is a narrow range of scores with its own sampling chance. The range from -1 to 1 is
cut into five buckets by the two thresholds the night follows. Below the lower threshold is
one lightly sampled slice running to -1.0, and above the upper threshold is one running to
1.0. Between the thresholds, a run of thin slices starts at the lower threshold, another run
ends at the upper one, and coarse slices fill what lies between the two runs.

Every edge is a whole number of thin slices, because the thresholds are real numbers and
`floor(0.58 / 0.01)` is 57 in floating point. The grid is counted in whole slices, the lower
threshold rounds down onto it and the upper one rounds up, so a lightly sampled end never
reaches past the threshold it lies beyond. Multi-slice buckets widen their step when their
planned pair budget cannot fund finer slices at `min_pairs_per_slice`, so every non-empty
slice in a funded bucket receives at least one pair for any `pair_budget >= 1`.

Nothing here reads a file, a config file or a clock.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from idhazh.contracts.knobs.content_similarity_judge import DrawConfig, threshold_ticks
from idhazh.contracts.story_similarity_pair_verdict import PairBucket


@dataclass(frozen=True, slots=True)
class Slice:
    """One range of scores, from `low` up to but not including `high`.

    The top slice includes 1.0, because a shared headline scores exactly 1.0.
    """

    bucket: PairBucket
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class SliceGrid:
    """The slices of -1 to 1 for one pair of thresholds, lowest score first."""

    slices: tuple[Slice, ...]
    _lows: tuple[float, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_lows", tuple(one.low for one in self.slices))

    def index_of(self, score: float) -> int:
        """Which slice holds this score. A score on an edge belongs to the slice above it.

        A caller clamps a score to -1 to 1 first, so the first and last slices take whatever
        is beyond them rather than refusing it.
        """
        return max(bisect.bisect_right(self._lows, score) - 1, 0)


def _partition_bucket(
    bucket: PairBucket,
    start_tick: int,
    end_tick: int,
    *,
    base_step: int,
    budget: int,
    min_pairs_per_slice: int,
) -> list[tuple[PairBucket, int, int]]:
    """Cut `[start_tick, end_tick)` into ticks that `budget` can fund without starving a slice."""
    span_ticks = end_tick - start_tick
    if span_ticks == 0:
        return []
    if budget == 0:
        return [(bucket, start_tick, end_tick)]
    max_slices = max(1, budget // min_pairs_per_slice)
    effective_step = max(base_step, (span_ticks + max_slices - 1) // max_slices)
    cuts: list[tuple[PairBucket, int, int]] = []
    tick = start_tick
    while tick < end_tick:
        top = min(tick + effective_step, end_tick)
        cuts.append((bucket, tick, top))
        tick = top
    return cuts


def slice_grid(lower: float, upper: float, *, draw: DrawConfig) -> SliceGrid:
    """The slices for these thresholds.

    The lower threshold is rounded down and the upper one up to the grid, so the range
    between the thresholds is never narrower than the thresholds say. A range too narrow
    to hold both thin runs, or a threshold with no room left for the lightly sampled end
    beyond it, is refused: the thresholds come from a committed file, and a draw cut from
    thresholds it cannot honour would file pairs under a slice nobody could explain.
    """
    per_unit = round(1.0 / draw.slice_width)
    coarse = round(draw.coarse_slice_width / draw.slice_width)
    thin = draw.thin_slices_each_end
    lower_tick, upper_tick = threshold_ticks(lower, upper, slice_width=draw.slice_width)
    if lower_tick <= -per_unit:
        raise ValueError(f"the lower threshold {lower} leaves no room below it for a slice")
    if upper_tick >= per_unit:
        raise ValueError(f"the upper threshold {upper} leaves no room above it for a slice")
    middle_start, middle_end = lower_tick + thin, upper_tick - thin
    if middle_start > middle_end:
        raise ValueError(
            f"the thresholds {lower} and {upper} are too close to hold {thin} thin slices of "
            f"{draw.slice_width} at each end"
        )

    budgets = draw.bucket_budgets()
    cuts: list[tuple[PairBucket, int, int]] = [(PairBucket.FULLY_DISSIMILAR, -per_unit, lower_tick)]
    cuts += _partition_bucket(
        PairBucket.LOWER_THIN,
        lower_tick,
        middle_start,
        base_step=1,
        budget=budgets[PairBucket.LOWER_THIN],
        min_pairs_per_slice=draw.min_pairs_per_slice,
    )
    cuts += _partition_bucket(
        PairBucket.MIDDLE_COARSE,
        middle_start,
        middle_end,
        base_step=coarse,
        budget=budgets[PairBucket.MIDDLE_COARSE],
        min_pairs_per_slice=draw.min_pairs_per_slice,
    )
    cuts += _partition_bucket(
        PairBucket.UPPER_THIN,
        middle_end,
        upper_tick,
        base_step=1,
        budget=budgets[PairBucket.UPPER_THIN],
        min_pairs_per_slice=draw.min_pairs_per_slice,
    )
    cuts.append((PairBucket.FULLY_SIMILAR, upper_tick, per_unit))
    return SliceGrid(
        tuple(Slice(bucket, low / per_unit, high / per_unit) for bucket, low, high in cuts)
    )
