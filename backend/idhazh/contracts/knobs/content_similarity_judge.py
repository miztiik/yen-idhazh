"""Which execution settings belong only to the content-similarity judge?"""

import math
from typing import Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import DateStamp, Model

#: How far a quotient may sit from a whole number and still be one. A width such as 0.04 over
#: 0.01 is 4.000000000000001 in floating point, and the grid is counted in whole slices.
_WHOLE_NUMBER_NOISE: Final = 1e-9

#: How far a threshold may sit from a grid line, counted in slices, and still be on it. 0.58
#: over a slice of 0.01 is 57.99999999999999 slices, and a rounding down that trusted that last
#: digit would put 0.58 one slice low.
GRID_NOISE: Final = 1e-9

#: How far two scores may differ by floating-point arithmetic alone: 0.93 less 0.81 is
#: 0.12000000000000011, and a gap of exactly 0.12 is not under 0.12.
_SCORE_NOISE: Final = 1e-9


def threshold_ticks(lower: float, upper: float, *, slice_width: float) -> tuple[int, int]:
    """The grid lines the two thresholds round to, counted in slices from zero.

    The lower threshold rounds down and the upper one up, so the range between them is never
    narrower than they say. The draw cuts its slices from these two numbers and the loader
    refuses starts that leave them no room, so the two read one answer.
    """
    per_unit = round(1.0 / slice_width)
    return math.floor(lower * per_unit + GRID_NOISE), math.ceil(upper * per_unit - GRID_NOISE)


class DrawBucketWeights(Model):
    """How the pairs left after the two lightly sampled ends are shared among the three buckets
    between the thresholds."""

    lower_thin: int = Field(
        ge=1,
        description=(
            "Weight of the thin slices that start at the lower bound threshold. Weights are "
            "relative: only their proportions matter. A bucket with no pairs hands its share on "
            "in descending weight order."
        ),
    )
    upper_thin: int = Field(
        ge=1, description="Weight of the thin slices that end at the upper bound threshold."
    )
    middle_coarse: int = Field(
        ge=1, description="Weight of the coarse slices that fill the range between the two runs."
    )


class LightBucketDraw(Model):
    """How many pairs one lightly sampled end of the score range gives a night."""

    weight: int = Field(
        ge=1,
        description=(
            "The end's weight against the three weights in `bucket_weights` and the other end's: "
            "its target is the budget times its weight over the sum of all five, rounded to a "
            "whole pair."
        ),
    )
    minimum: int = Field(
        ge=0,
        description=(
            "The fewest pairs taken when the end holds that many. The target is raised to it."
        ),
    )
    maximum: int = Field(
        ge=1,
        description=(
            "The most pairs taken. The target is lowered to it, and the pairs it frees go to the "
            "buckets between the thresholds."
        ),
    )

    @model_validator(mode="after")
    def _the_minimum_does_not_pass_the_maximum(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError(
                f"the minimum of {self.minimum} pairs is above the maximum of {self.maximum}"
            )
        return self


class DrawConfig(Model):
    """How the nightly draw cuts the score range into slices and spends its budget."""

    pair_budget: int = Field(
        ge=1,
        description=(
            "Live pairs a night to judge, shared over the council's shards. 150 over four shards "
            "is 38 pairs a shard, which costs 1 hour 10 minutes at the measured worst of 110.98 "
            "seconds a pair. The judge refuses a draw that cannot fit the council's window."
        ),
    )
    slice_width: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "Width of the thin slices, and the grid every slice edge sits on. One over it is a "
            "whole number, so -1 and 1 lie on the grid. The draw rounds the lower bound "
            "threshold down and the upper one up to this grid."
        ),
    )
    thin_slices_each_end: int = Field(
        ge=1,
        description=(
            "Thin slices that start at the lower bound threshold, and as many that end at the "
            "upper one."
        ),
    )
    coarse_slice_width: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "Width of the coarse slices between the two thin runs, a whole number of thin "
            "slices. The last coarse slice is narrower when the range does not divide."
        ),
    )
    bucket_weights: DrawBucketWeights
    fully_similar: LightBucketDraw = Field(
        description="The sample above the upper bound threshold, checked lightly as a live canary."
    )
    fully_dissimilar: LightBucketDraw = Field(
        description="The sample below the lower bound threshold, checked lightly as a live canary."
    )
    thresholds_lookback_days: int = Field(
        ge=1,
        description=(
            "The newest threshold-history row dated before the night and inside this many days "
            "sets the thresholds the draw follows. With none inside it, the configured starts do."
        ),
    )

    @model_validator(mode="after")
    def _the_slices_lie_on_one_grid(self) -> Self:
        """Edges are counted in whole thin slices so -1, 1 and every threshold meet the grid."""
        per_unit = 1.0 / self.slice_width
        if abs(per_unit - round(per_unit)) > _WHOLE_NUMBER_NOISE:
            raise ValueError(
                f"slice_width {self.slice_width} does not divide 1 into whole slices"
            )
        per_coarse = self.coarse_slice_width / self.slice_width
        if per_coarse < 1.0 - _WHOLE_NUMBER_NOISE or abs(per_coarse - round(per_coarse)) > (
            _WHOLE_NUMBER_NOISE
        ):
            raise ValueError(
                f"coarse_slice_width {self.coarse_slice_width} is not a whole number of "
                f"slice_width {self.slice_width} slices"
            )
        return self


class ThresholdsConfig(Model):
    """Where the two thresholds start, what defines each, and how a night is allowed to move them.

    A night reads the pairs of the last `window_nights` nights that scored near a threshold,
    fits a curve through the judge's answers, and finds the score where the same-story share
    reaches the threshold's level. The gap between that score and the threshold is acted on
    only when it is big enough, has stood long enough and rests on enough pairs, and then
    only by a limited step: out fast and in slowly, because a threshold sitting too far
    inside the doubtful range leaves wrong answers in a bucket the draw barely checks.
    """

    lower_start: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "The lower bound threshold the draw follows when no threshold-history row is recent "
            "enough. Below it pairs are fully dissimilar."
        ),
    )
    upper_start: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "The upper bound threshold the draw follows when no threshold-history row is recent "
            "enough. Above it pairs are fully similar."
        ),
    )
    lower_share_level: float = Field(
        gt=0.0,
        lt=1.0,
        description=(
            "The same-story share that defines the lower bound threshold: the score where the "
            "fitted curve reaches it. Low, because below the lower threshold pairs are fully "
            "dissimilar and almost none should be called the same story."
        ),
    )
    upper_share_level: float = Field(
        gt=0.0,
        lt=1.0,
        description=(
            "The same-story share that defines the upper bound threshold: the score where the "
            "fitted curve reaches it. High, because above the upper threshold pairs are fully "
            "similar and almost all should be called the same story. Above the lower share level."
        ),
    )
    window_nights: int = Field(
        ge=1,
        description=(
            "How many UTC days, ending on the night, of pair-verdicts the estimate reads. "
            "Several nights are pooled because one night's pairs near a threshold are too few "
            "to place it."
        ),
    )
    near_threshold_width: float = Field(
        gt=0.0,
        description=(
            "How far either side of a threshold a pair may score and still be evidence for "
            "it. Pairs farther away say almost nothing about where the share crosses a level."
        ),
    )
    minimum_usable_pairs: int = Field(
        ge=1,
        description=(
            "The fewest usable pairs near a threshold, over the window, that a night may act "
            "on. Fewer holds the threshold, and the estimate is still stored."
        ),
    )
    ignore_range: float = Field(
        gt=0.0,
        description=(
            "A gap between the estimate and the threshold this small or smaller is not acted "
            "on: it is inside what a night's evidence can tell apart from no change."
        ),
    )
    nights_running_required: int = Field(
        ge=1,
        description=(
            "How many nights in a row the gap has to be beyond the ignore range, in the same "
            "direction, before a threshold moves. One is no confirmation."
        ),
    )
    widening_step: float = Field(
        gt=0.0,
        description=(
            "The most a threshold moves in a night when moving out: the lower one down, the "
            "upper one up. Out is fast, so the doubtful range grows as soon as the evidence "
            "says it should."
        ),
    )
    narrowing_step: float = Field(
        gt=0.0,
        description=(
            "The most a threshold moves in a night when moving in: the lower one up, the upper "
            "one down. In is slow, because a threshold too far inside the doubtful range "
            "leaves wrong answers in a bucket the draw barely checks."
        ),
    )
    far_gap: float = Field(
        gt=0.0,
        description=(
            "A gap larger than this is far: the threshold is a long way from where the "
            "evidence puts it, and takes the far gap step in either direction."
        ),
    )
    far_gap_step: float = Field(
        gt=0.0,
        description=(
            "The most a threshold moves in a night, in or out, when the gap is far, so a bad "
            "start is found in a few nights and not in many."
        ),
    )
    lowest_lower_threshold: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "The lowest score the lower bound threshold may reach. A move that would pass it "
            "stops here."
        ),
    )
    highest_upper_threshold: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "The highest score the upper bound threshold may reach. A move that would pass it "
            "stops here."
        ),
    )
    smallest_gap: float = Field(
        gt=0.0,
        description=(
            "The least distance between the two thresholds. A move that would bring them "
            "closer stops here, because the draw cannot cut its thin slices from a range "
            "narrower than both thin runs."
        ),
    )
    pull_start_steepness: float = Field(
        gt=0.0,
        description=(
            "The steepness every curve fit is pulled towards until enough nights of fitted "
            "steepness exist to take their median instead."
        ),
    )
    pull_spread: float = Field(
        gt=0.0,
        description=(
            "How loosely the fit is held to the pull centre: the standard deviation of the "
            "pull on the steepness. A smaller spread pulls harder."
        ),
    )
    pull_window_nights: int = Field(
        ge=1,
        description=(
            "How many UTC days before the night of fitted steepness the pull centre is the "
            "median of."
        ),
    )
    pull_minimum_nights: int = Field(
        ge=1,
        description=(
            "How many nights of fitted steepness the median needs. Fewer, and the pull centre "
            "is the starting steepness."
        ),
    )

    @model_validator(mode="after")
    def _the_two_share_levels_and_the_pull_window_are_in_order(self) -> Self:
        """The lower level is below the upper, and the median can have as many nights as it needs.

        A threshold row refuses a lower share level that is not below the upper one, so a
        config that allowed it would pass here and fail every night when the row is filed.
        """
        if self.lower_share_level >= self.upper_share_level:
            raise ValueError(
                f"lower_share_level {self.lower_share_level} is not below upper_share_level "
                f"{self.upper_share_level}"
            )
        if self.pull_minimum_nights > self.pull_window_nights:
            raise ValueError(
                f"pull_minimum_nights {self.pull_minimum_nights} is above pull_window_nights "
                f"{self.pull_window_nights}, so the median could never have enough nights"
            )
        return self

    @model_validator(mode="after")
    def _a_far_gap_is_a_gap_that_is_acted_on_and_takes_no_smaller_step_than_a_near_one(
        self,
    ) -> Self:
        """A far gap is beyond the ignore range and moves a threshold as far as a near one.

        A far gap takes its own step in either direction. If that step were under a near step,
        a larger gap would move a threshold less than a smaller one, and if the far gap were not
        beyond the ignore range, no gap would ever be near and the two near steps would be
        settings nothing reads.
        """
        if self.far_gap <= self.ignore_range:
            raise ValueError(
                f"far_gap {self.far_gap} is not above ignore_range {self.ignore_range}, so no "
                "gap acted on would be near"
            )
        near = max(self.widening_step, self.narrowing_step)
        if self.far_gap_step < near:
            raise ValueError(
                f"far_gap_step {self.far_gap_step} is under the near step of {near}, so a far "
                "gap would move a threshold less than a near one"
            )
        return self


class ContentSimilarityJudgeConfig(Model):
    """The draw, the thresholds and how they move, flush cadence, temperature and version."""

    draw: DrawConfig
    thresholds: ThresholdsConfig
    flush_every_pairs: int = Field(
        ge=1,
        description=(
            "Pairs completed before rewriting the verdict file. One preserves every "
            "completed pair if a shard dies; the bounded rewrite is cheap beside a call."
        ),
    )
    judge_temperature: float = Field(
        ge=0.0,
        le=2.0,
        description=(
            "Decoder temperature for both orders. Zero measures order disagreement "
            "without adding sampling noise; the summarizer's temperature stays separate."
        ),
    )
    version: DateStamp = Field(
        description=(
            "UTC date (YYYY-MM-DD) of the last edit to this file that changed a value, "
            "bumped in the same commit as that edit. A night records the date of each "
            "config file it read, so its results say which tuning produced them. It is a "
            "revision date and never a schema version, so it needs no migration. The "
            "loader refuses a date that does not exist or has not arrived yet."
        ),
    )

    @model_validator(mode="after")
    def _the_starts_leave_room_for_both_thin_runs_and_both_lightly_sampled_ends(self) -> Self:
        """A draw cut from these starts has every slice it names, with none overlapping.

        The starts are rounded onto the grid the way the draw rounds them, so a start that
        fits here fits when the draw cuts its slices. The two thin runs sit at the two
        thresholds, so they need the range between the rounded thresholds to hold both, and
        each lightly sampled end needs at least one thin slice of room before -1 or 1.
        """
        width = self.draw.slice_width
        thin = self.draw.thin_slices_each_end
        lower, upper = self.thresholds.lower_start, self.thresholds.upper_start
        lower_tick, upper_tick = threshold_ticks(lower, upper, slice_width=width)
        per_unit = round(1.0 / width)
        if lower_tick <= -per_unit:
            raise ValueError(
                f"lower_start {lower} leaves the fully dissimilar end under one slice wide"
            )
        if upper_tick >= per_unit:
            raise ValueError(
                f"upper_start {upper} leaves the fully similar end under one slice wide"
            )
        if upper_tick - lower_tick < 2 * thin:
            raise ValueError(
                f"the starts {lower} and {upper} are {upper - lower:.4f} apart, and "
                f"{thin} thin slices at each end need {2 * thin * width:.4f}"
            )
        return self

    @model_validator(mode="after")
    def _the_limits_and_the_smallest_gap_leave_the_thresholds_room_the_draw_can_cut(self) -> Self:
        """A threshold that moves to a limit still leaves the draw every slice it names.

        The thresholds move only between the lowest and highest allowed scores and never closer
        than the smallest gap, so a draw cut from any place they can reach needs what the starts
        were checked for: a thin slice of fully dissimilar and of fully similar range at the
        ends, and both thin runs between. The starts must also stand inside the limits and at
        least the smallest gap apart, or the first night would be cut short by a limit it began
        outside. This runs after the check of the starts, so a start that fails both is refused
        for its own reason.
        """
        rules = self.thresholds
        width, thin = self.draw.slice_width, self.draw.thin_slices_each_end
        per_unit = round(1.0 / width)
        lowest_tick, highest_tick = threshold_ticks(
            rules.lowest_lower_threshold, rules.highest_upper_threshold, slice_width=width
        )
        if lowest_tick <= -per_unit:
            raise ValueError(
                f"lowest_lower_threshold {rules.lowest_lower_threshold} leaves the fully "
                "dissimilar end under one slice wide"
            )
        if highest_tick >= per_unit:
            raise ValueError(
                f"highest_upper_threshold {rules.highest_upper_threshold} leaves the fully "
                "similar end under one slice wide"
            )
        if rules.smallest_gap * per_unit + GRID_NOISE < 2 * thin:
            raise ValueError(
                f"smallest_gap {rules.smallest_gap} is under the {2 * thin * width:.4f} that "
                f"{thin} thin slices at each end need"
            )
        if rules.lower_start < rules.lowest_lower_threshold:
            raise ValueError(
                f"lower_start {rules.lower_start} is below lowest_lower_threshold "
                f"{rules.lowest_lower_threshold}"
            )
        if rules.upper_start > rules.highest_upper_threshold:
            raise ValueError(
                f"upper_start {rules.upper_start} is above highest_upper_threshold "
                f"{rules.highest_upper_threshold}"
            )
        if rules.upper_start - rules.lower_start + _SCORE_NOISE < rules.smallest_gap:
            raise ValueError(
                f"the starts {rules.lower_start} and {rules.upper_start} are closer than "
                f"smallest_gap {rules.smallest_gap}"
            )
        return self


class ContentSimilarityEvaluationConfig(Model):
    """The explicit offline input ceiling and event-group interval settings."""

    max_cases: int = Field(default=200, strict=True, gt=0)
    confidence_level: float = Field(default=0.95, gt=0, lt=1, allow_inf_nan=False)
    resamples: int = Field(default=2000, strict=True, gt=0)
    resample_seed: int = Field(default=0, strict=True)
