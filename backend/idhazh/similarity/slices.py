"""Where do tonight's slices of the score range sit, and which slice holds a given score?

A slice is a narrow range of scores with its own sampling chance. The range from -1 to 1 is
cut into five buckets by the two thresholds the night follows. A straddling band of thin
slices sits within `thin_band_half_width` on both sides of each threshold, clamped at the
outer ends so `fully_dissimilar` and `fully_similar` each keep at least one `slice_width`
slice running out to -1.0 or 1.0, and coarse slices fill what lies between the two thin bands.

Every edge is a whole number of thin slices, because the thresholds are real numbers and
`floor(0.58 / 0.01)` is 57 in floating point. The grid is counted in whole slices, the lower
threshold rounds down onto it and the upper one rounds up, so each threshold sits on an exact
slice edge whenever its straddling bucket funds at least two slices. Multi-slice buckets widen
their step when their planned pair budget cannot fund finer slices at `min_pairs_per_slice`,
so every non-empty slice in a funded bucket receives at least one pair for any
`pair_budget >= 1`.

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


def _cut_ticks(
    bucket: PairBucket, start_tick: int, end_tick: int, *, step: int
) -> list[tuple[PairBucket, int, int]]:
    """Partition `[start_tick, end_tick)` into contiguous slices of width at most `step`."""
    cuts: list[tuple[PairBucket, int, int]] = []
    tick = start_tick
    while tick < end_tick:
        top = min(tick + step, end_tick)
        cuts.append((bucket, tick, top))
        tick = top
    return cuts


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
    return _cut_ticks(bucket, start_tick, end_tick, step=effective_step)


def _straddling_step(
    below_ticks: int, above_ticks: int, *, half_ticks: int, max_slices: int
) -> int:
    """Smallest positive step (preferring divisors of `half_ticks`) fitting `max_slices`."""
    for step in range(1, half_ticks + 1):
        if half_ticks % step != 0:
            continue
        slices = (below_ticks + step - 1) // step + (above_ticks + step - 1) // step
        if slices <= max_slices:
            return step
    return half_ticks


def _partition_straddling_bucket(
    bucket: PairBucket,
    start_tick: int,
    threshold_tick: int,
    end_tick: int,
    *,
    half_ticks: int,
    budget: int,
    min_pairs_per_slice: int,
) -> list[tuple[PairBucket, int, int]]:
    """Cut `[start_tick, end_tick)` around `threshold_tick`, keeping the threshold on an edge."""
    if start_tick == end_tick:
        return []
    if budget == 0:
        return [(bucket, start_tick, end_tick)]
    max_slices = max(1, budget // min_pairs_per_slice)
    if max_slices == 1:
        return [(bucket, start_tick, end_tick)]
    step = _straddling_step(
        threshold_tick - start_tick,
        end_tick - threshold_tick,
        half_ticks=half_ticks,
        max_slices=max_slices,
    )
    return _cut_ticks(bucket, start_tick, threshold_tick, step=step) + _cut_ticks(
        bucket, threshold_tick, end_tick, step=step
    )


def slice_grid(lower: float, upper: float, *, draw: DrawConfig) -> SliceGrid:
    """The slices for these thresholds.

    The lower threshold is rounded down and the upper one up to the grid, so the range
    between the thresholds is never narrower than the thresholds say. Each threshold's thin
    band straddles `thin_band_half_width` on both sides, with outer edges clamped so each
    lightly sampled end keeps at least one `slice_width` slice. A range too narrow to hold
    both non-overlapping thin bands, or a threshold with no room left for the lightly sampled
    end beyond it, is refused: the thresholds come from a committed file, and a draw cut from
    thresholds it cannot honour would file pairs under a slice nobody could explain.
    """
    per_unit = round(1.0 / draw.slice_width)
    coarse = round(draw.coarse_slice_width / draw.slice_width)
    half_ticks = round(draw.thin_band_half_width / draw.slice_width)
    lower_tick, upper_tick = threshold_ticks(lower, upper, slice_width=draw.slice_width)
    if lower_tick <= -per_unit:
        raise ValueError(f"the lower threshold {lower} leaves no room below it for a slice")
    if upper_tick >= per_unit:
        raise ValueError(f"the upper threshold {upper} leaves no room above it for a slice")
    lower_band_start = max(-per_unit + 1, lower_tick - half_ticks)
    lower_band_end = lower_tick + half_ticks
    upper_band_start = upper_tick - half_ticks
    upper_band_end = min(per_unit - 1, upper_tick + half_ticks)
    if lower_band_end > upper_band_start:
        raise ValueError(
            f"the thresholds {lower} and {upper} are too close to hold straddling thin bands of "
            f"half-width {draw.thin_band_half_width} around each threshold"
        )

    budgets = draw.bucket_budgets()
    cuts: list[tuple[PairBucket, int, int]] = [
        (PairBucket.FULLY_DISSIMILAR, -per_unit, lower_band_start)
    ]
    cuts += _partition_straddling_bucket(
        PairBucket.LOWER_THIN,
        lower_band_start,
        lower_tick,
        lower_band_end,
        half_ticks=half_ticks,
        budget=budgets[PairBucket.LOWER_THIN],
        min_pairs_per_slice=draw.min_pairs_per_slice,
    )
    cuts += _partition_bucket(
        PairBucket.MIDDLE_COARSE,
        lower_band_end,
        upper_band_start,
        base_step=coarse,
        budget=budgets[PairBucket.MIDDLE_COARSE],
        min_pairs_per_slice=draw.min_pairs_per_slice,
    )
    cuts += _partition_straddling_bucket(
        PairBucket.UPPER_THIN,
        upper_band_start,
        upper_tick,
        upper_band_end,
        half_ticks=half_ticks,
        budget=budgets[PairBucket.UPPER_THIN],
        min_pairs_per_slice=draw.min_pairs_per_slice,
    )
    cuts.append((PairBucket.FULLY_SIMILAR, upper_band_end, per_unit))
    return SliceGrid(
        tuple(Slice(bucket, low / per_unit, high / per_unit) for bucket, low, high in cuts)
    )
