"""Which execution settings belong only to the content-similarity judge?"""

from typing import Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import DateStamp, Model

#: How far a quotient may sit from a whole number and still be one. A width such as 0.04 over
#: 0.01 is 4.000000000000001 in floating point, and the grid is counted in whole slices.
_WHOLE_NUMBER_NOISE: Final = 1e-9


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


class ThresholdStarts(Model):
    """Where the two thresholds sit until a night has moved them."""

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


class ContentSimilarityJudgeConfig(Model):
    """The draw, the thresholds it starts from, verdict flush cadence, temperature and version."""

    draw: DrawConfig
    thresholds: ThresholdStarts
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

        The draw only widens the range when it rounds a threshold outward, so a start that
        fits here fits after the rounding. The two thin runs sit at the two thresholds, so
        they need the range between the thresholds to hold both, and each lightly sampled
        end needs at least one thin slice of room before -1 or 1.
        """
        width = self.draw.slice_width
        lower, upper = self.thresholds.lower_start, self.thresholds.upper_start
        if lower < -1.0 + width - _WHOLE_NUMBER_NOISE:
            raise ValueError(
                f"lower_start {lower} leaves the fully dissimilar end under one slice wide"
            )
        if upper > 1.0 - width + _WHOLE_NUMBER_NOISE:
            raise ValueError(
                f"upper_start {upper} leaves the fully similar end under one slice wide"
            )
        needed = 2 * self.draw.thin_slices_each_end * width
        if upper - lower < needed - _WHOLE_NUMBER_NOISE:
            raise ValueError(
                f"the starts {lower} and {upper} are {upper - lower:.4f} apart, and "
                f"{self.draw.thin_slices_each_end} thin slices at each end need {needed:.4f}"
            )
        return self


class ContentSimilarityEvaluationConfig(Model):
    """The explicit offline input ceiling and event-group interval settings."""

    max_cases: int = Field(default=200, strict=True, gt=0)
    confidence_level: float = Field(default=0.95, gt=0, lt=1, allow_inf_nan=False)
    resamples: int = Field(default=2000, strict=True, gt=0)
    resample_seed: int = Field(default=0, strict=True)
