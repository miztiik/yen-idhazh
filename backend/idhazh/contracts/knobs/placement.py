"""Where a story sits on the published day, and the frame a person sets over its head."""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob

# The band rule is one rule and the record owns the number. Imported rather than
# re-declared: two literals for one tolerance drift the first time somebody
# loosens one, and then a band this file accepts is a band the record refuses,
# hours later and on the first fold. The `as` spelling is deliberate - it is how
# a module says a re-export is intended rather than accidental.
from idhazh.contracts.story_similarity_distribution import (
    GRID_TOLERANCE as GRID_TOLERANCE,
)

#: The knobs `assemble` used to carry, and where each one went. Spelled as a
#: whole path because the floor moved down a level rather than changing its
#: name, and an operator sent to `assemble.floor_min` is sent to a key that does
#: not exist.
SUPERSEDED_ASSEMBLE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"duplicate_similarity_min": "assemble.same_story.floor_min"}
)

#: How close a set of weights has to get to 1.0 to count as summing to 1.0. Not
#: exact equality: 0.7 and 0.3 are two numbers a person would write and their
#: binary sum is 0.9999999999999999, so exact equality refuses a split nothing
#: is wrong with. A billionth is far below any weight worth setting.
_WEIGHTS_TOLERANCE: Final = 1e-9

#: The highest score the labelled set marks as TWO stories. Measured 2026-09-19
#: over the 200 pairs in `state/content-similarity-judge/holdout-pairs.csv`, labelled by
#: claude-opus-4.6 reading each pair's title and summary; 196 one story, 4 two
#: stories, and the four are all the same lake-renaming cluster. Counts are
#: deterministic and have no spread.
#:
#: **It is the pair's own score and never a gap.** The gap to the line is
#: `floor_min` minus this, computed where it is needed, because `floor_min` is a
#: config value and a frozen subtraction goes stale the moment either side moves.
#: Today that gap is -0.0007: the line sits BELOW the highest two-story mark, so
#: there is no headroom for a downward step to protect.
#:
#: **One declaration, and one instrument that retakes it** (Guardrail #10).
#: `idhazh score-merge-line-holdout` scores every marked pair on its way to the
#: four cells, so it already holds this reading and prints it beside this line
#: whenever the two disagree. It prints rather than stores: a second copy on a
#: committed row is the second source this constant is not allowed to have.
HOLDOUT_TWO_STORY_MAX: Final = 0.9407

#: How much of the marked set has to be scorable before the four cells are worth
#: reading, as a share of the marked rows. Retention deletes published days the
#: holdout still names, so a run can find no vectors for most of the pairs and
#: still produce four cells that add up - and four small cells look like a good
#: line rather than a vanished comparison.
#:
#: **A constant rather than a knob, on purpose.** It says what makes the reading
#: mean anything, and a number that can be tuned down is a number somebody tunes
#: down on the morning the reading goes red. It sits beside the two-story maximum
#: because both are properties of the marked file rather than of the pipeline.
HOLDOUT_RESOLVED_SHARE_MIN: Final = 0.5

#: Wall clock for one judge call at 764 read tokens, in seconds. Derived from the
#: repository's own reading of 9.85 tokens a second - median over 4,117 timed
#: rows, slowest 8.25, fastest 44.71, taken 2026-09-09 on a stock ubuntu-latest
#: (docs/reference/pipeline-cost.md). A derived figure rather than a judge
#: reading, which is why the judge no longer sizes its own budget from it. It
#: stays because the budgets that still read it have no reading of their own, and
#: moving it would re-size work nobody measured.
SECONDS_A_CALL: Final = 77.6

#: The knobs `adaptive_dedup_threshold` used to carry, and where each one went.
#: Two changed unit as well as name: the fall cap is counted in slots of
#: `bin_width` now rather than written as a score, and the one damping weight
#: became two because the line damps both directions. `shards` is the third and
#: it changed owner instead - a fan-out width is a runner number the workflow
#: sizes its own matrix by, so its replacement is spelled as a whole path.
SUPERSEDED_THRESHOLD_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "max_down_step": "max_down_bins",
        "shards": "council.shards",
        "smoothing_weight": "fall_weight",
    }
)


class SimilarityThresholdConfig(Model):
    """How the merge line fits itself, and the gates it has to clear before it may.

    Nested inside `SameStoryConfig` rather than flat under `assemble`, for the
    reason that model's own docstring gives: a knob whose legal value depends on
    another knob's value belongs where a validator can see both. The daily caps
    are counted in slots of `bin_width` and have to stay inside the band the
    record slices, and `band_low` has to sit below the line `floor_min` currently
    holds.

    The line falls fast and rises slow. Lowering it publishes less, which is the
    house rule, so both the damping weight and the daily cap are larger going
    down than going up - and a validator here refuses a config that reverses it.

    **Nothing reads this block yet.** It ships with `enabled` off, so a fresh
    clone publishes exactly what it published before the block existed.
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Whether assemble reads the fitted line instead of floor_min. Ships off, so a "
            "fresh clone publishes exactly what it published before this feature existed. "
            "Removal condition: delete this flag once row 9 has run 14 days and the fitted "
            "line has moved no published group a person disagreed with."
        ),
    )
    band_low: float = Field(
        default=0.88,
        gt=0.0,
        lt=1.0,
        description=(
            "The lowest score worth judging. Below it two items are nowhere near one "
            "story, so a verdict costs a model call and moves nothing. 0.88 is where the "
            "measured pairs start: the lowest of the 200 labelled pairs sits at 0.8807, so "
            "the band opens below every decision the line has to get right."
        ),
    )
    band_high: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description=(
            "The top of the band. 1.00, because a cosine goes no higher and a pair at 0.999 "
            "is still a pair the record should hold a slot for."
        ),
    )
    bin_width: float = Field(
        default=0.001,
        gt=0.0,
        le=0.01,
        description=(
            "How finely the record slices the band, and therefore the resolution of the "
            "fitted line. 0.001 is already finer than the labels can be read apart: the "
            "200 pairs marked on 2026-09-19 put a one-story pair at 0.9406, a two-story "
            "pair at 0.9407 and another one-story pair at 0.9409, so three slots hold both "
            "marks. Finer costs slots and buys no separation the labels can support."
        ),
    )
    discard_share: float = Field(
        default=0.03,
        gt=0.0,
        lt=0.5,
        description=(
            "What share of the record's agreed-NO verdicts the fit sets aside at the top "
            "before placing the line - a share of NO readings, never of judged pairs. It "
            "is what stops a handful of wrong NO verdicts setting the number: a single NO "
            "at 0.97 would otherwise pin the line at 0.971 for ever, because the line is "
            "the stopped slot's upper edge. The question it answers is how many wrong NO "
            "verdicts ONE news cluster can produce before it sets the line, and the "
            "answer is not one. In the 200 labelled pairs of 2026-09-19 all four "
            "two-story marks came from a single cluster that produced 29 pairs. At "
            "minimum_negatives of 200, floor(total * 0.03) sets six verdicts aside, which "
            "survives that night; 0.01 sets two aside, which does not."
        ),
    )
    dead_zone_bins: int = Field(
        default=1,
        ge=1,
        description=(
            "How close a proposal has to come to the applied line before the day counts as "
            "no move at all, counted in slots of bin_width. 1 slot, because a smaller move "
            "is one the fit cannot represent: the line is a slot's upper edge, so a step of "
            "half a slot lands on no edge the next walk can produce. Without it the damping "
            "leaves a geometric tail whose steps shrink below one slot for ever and the "
            "applied line never formally arrives at its proposal."
        ),
    )
    fall_weight: float = Field(
        default=0.50,
        gt=0.0,
        le=1.0,
        description=(
            "How much of a DOWNWARD move lands today. Down is the fast direction: lowering "
            "the line publishes less, and the house rule is to err on the side of "
            "publishing less. 0.50 is half the remaining gap a day rather than the whole "
            "gap, because one judge misreading one news cluster produces a block of "
            "adjacent wrong verdicts on one night, and an undamped fall would take that "
            "whole block at once. An ESTIMATE; what replaces it is the first fortnight of "
            "written rows."
        ),
    )
    rise_weight: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description=(
            "How much of an UPWARD move lands today. Up is the slow direction: raising the "
            "line merges more stories together and publishes fewer of them separately, so "
            "it arrives over a month. 0.15 with the up cap takes the line from 0.88 back "
            "to 0.94 in about thirty-three days, against about ten days for the same "
            "distance downwards. An ESTIMATE, replaced by the first fortnight of rows."
        ),
    )
    max_down_bins: int = Field(
        default=10,
        ge=1,
        description=(
            "The furthest the line may fall in one day, counted in slots of bin_width. 10 "
            "slots is 0.010 at the committed width. Counted in slots rather than written "
            "as a decimal because 10 slots down is checkable against the record the line "
            "was fitted from, and 'one percent of the scale' is not. Bounded by the band: "
            "a step wider than the band leaves the record that proposed it."
        ),
    )
    max_up_bins: int = Field(
        default=3,
        ge=1,
        description=(
            "The furthest the line may rise in one day, counted in slots of bin_width. 3 "
            "slots is 0.003 at the committed width - under a third of the fall cap, which "
            "is the whole asymmetry in one number. Both directions are capped rather than "
            "one, because damping alone is not a brake a reader can bound and the "
            "step-change guard ships off."
        ),
    )
    step_change_multiple: float = Field(
        default=5.0,
        gt=1.0,
        le=50.0,
        description=(
            "How far out of line one day's evidence has to be before the guard holds. "
            "Measured against the median daily shift of the last fourteen rows, never a "
            "standard deviation: the daily shift shrinks as 1/days and is not normally "
            "distributed, so a sigma is the wrong ruler. 5 is an ESTIMATE. What replaces it "
            "is the spread of the first fourteen written rows."
        ),
    )
    step_change_guard_enforced: bool = Field(
        default=False,
        description=(
            "Whether the guard actually holds the line or only records that it would have. "
            "Ships off, because enforcing a hold on a multiple nobody has measured lets an "
            "unchecked number freeze the line. Removal condition: delete this flag once "
            "step_change_multiple carries a value measured from fourteen written rows."
        ),
    )
    pair_budget: int = Field(
        default=200,
        ge=1,
        description=(
            "How many pairs a day may be judged. 200 pairs over the council's committed "
            "four shards is 50 pairs a shard, which at the worst pair measured - 110.98 s "
            "on 2026-09-18 - is 1 hour 32 minutes of model time a shard, and 1 hour 19 "
            "minutes at the measured average of 94.53 s "
            "(docs/reference/benchmarks/what-a-judge-pair-costs.md). Raising it is a "
            "job-timeout question before it is a quality one, and this judge refuses a "
            "value that does not fit the window the council leaves a unit to work in - "
            "checked when the council resolves this judge, not when config is read, "
            "because the per-pair cost is this judge's own measurement."
        ),
    )
    flush_every_pairs: int = Field(
        default=1,
        ge=1,
        description=(
            "How many pairs a judging shard finishes before it writes its verdict file "
            "again. Every pair, because the file holds one shard's slice of pair_budget - "
            "50 rows at the committed numbers - and rewriting 50 rows is not measurable "
            "beside a pair that costs 110.98 s. It buys the case the cadence exists for: a "
            "shard that stops on its clock, or dies, still leaves every pair it had "
            "already judged. Counted in pairs because a pair is the unit this judge stops "
            "between. Raise it only if a run ever shows the rewrite costing anything."
        ),
    )
    judge_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description=(
            "How far the judge's sampler may stray from the likeliest word. 0.0, because "
            "every pair is read twice with the two summaries swapped and the two readings "
            "are then compared: at 0.0 a disagreement is position bias, which is the thing "
            "disagreement_max gates on. Above 0.0 the same pair can answer differently with "
            "nothing swapped at all, so the comparison measures sampling noise instead and "
            "the gate stops meaning what its own name says. It sits here rather than on "
            "models.summarize.inference because that entry pins its temperature for writing "
            "summaries, which is a different job on the same weights."
        ),
    )
    minimum_negatives: int = Field(
        default=200,
        ge=1,
        description=(
            "Agreed NO verdicts the record needs before the fit may set the line at all. "
            "200, because discard_share is 0.03 and three percent of 200 sets six verdicts "
            "aside - enough to absorb the four wrong NO verdicts one news cluster produced "
            "in the 200 labelled pairs of 2026-09-19. Three percent of 100 sets three "
            "aside, which does not."
        ),
    )
    minimum_above_line: int = Field(
        default=30,
        ge=1,
        description=(
            "Judged pairs at or above the current line the record needs before the fit runs. "
            "30 is an ESTIMATE of enough to notice a wrong merge rate; what replaces it is "
            "the first month of holdout readings. These pairs are the entire precision "
            "measurement and are never sampled away."
        ),
    )
    minimum_days: int = Field(
        default=10,
        ge=1,
        description=(
            "Distinct dates the record needs before the fit runs. 10, so the line is never "
            "set by a fortnight of one kind of news."
        ),
    )
    disagreement_max: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description=(
            "How often the two orders may disagree before the run holds with judge_unstable. "
            "0.15 means one pair in seven flipping with the order, at which point the "
            "verdicts are reading the prompt layout rather than the articles. An ESTIMATE; "
            "what replaces it is the first fourteen written rows."
        ),
    )
    unclear_max: float = Field(
        default=0.35,
        gt=0.0,
        le=1.0,
        description=(
            "What share of readings may be UNCLEAR before the run holds with "
            "judge_uncertain. 0.35 is where the middle bucket starves the two the line is "
            "fitted on. UNCLEAR means the text does not say enough, never that the pair is "
            "halfway between. An ESTIMATE, replaced the same way."
        ),
    )
    settled_window_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description=(
            "How far back step 4 looks to ask whether a whole week of fresh judgements "
            "changed the answer. 7 days, because that is a week of news rather than a "
            "statistical window: the damping already carries a day-to-day correlation of "
            "0.85, so a shorter window asks the smoothing whether the smoothing worked."
        ),
    )
    settled_delta: float = Field(
        default=0.001,
        gt=0.0,
        le=0.01,
        description=(
            "How small the week-on-week move has to be to count as settled. 0.001, which is "
            "one bin width, so settling is measured at the line's own resolution and never "
            "at a precision the fit cannot produce."
        ),
    )
    applied_lookback_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description=(
            "How many days back assemble will look for a fitted line before it falls back to "
            "the config floor. 7, because the fit writes a row every day, so a gap longer "
            "than a week means the judge has been down a week and the committed config value "
            "is the honest answer."
        ),
    )
    step_change_window_rows: int = Field(
        default=14,
        ge=2,
        le=90,
        description=(
            "How many written rows the guard's median is taken over. 14 rows, counted as "
            "rows rather than as days: a window in days returns fewer rows than it names "
            "after any missed run, and a median over four rows would let the guard fire on "
            "noise. The fit reads a window of days wide enough to find them and takes the "
            "newest 14 it has."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_a_removed_knob(cls, data: Any) -> Any:
        return refuse_a_removed_knob(
            "assemble.same_story.adaptive_dedup_threshold", data, SUPERSEDED_THRESHOLD_NAMES
        )

    @property
    def dead_zone(self) -> float:
        """How near a proposal counts as no move, in score units. Slots times slot width."""
        return self.dead_zone_bins * self.bin_width

    @property
    def max_down_step(self) -> float:
        """The fall cap in score units. Derived, so the slot count is the only number set."""
        return self.max_down_bins * self.bin_width

    @property
    def max_up_step(self) -> float:
        """The rise cap in score units. Derived for the same reason the fall cap is."""
        return self.max_up_bins * self.bin_width

    @model_validator(mode="after")
    def _the_band_divides_into_whole_slots(self) -> Self:
        """A band that ends mid-slot leaves a part-slot whose counts mean something else.

        Checked here as well as on the record, because the record's own
        validator would refuse the first fold hours after the config edit, in
        CI, with nothing on the row saying which of three knobs to move. The
        message names both numbers and the remainder for the same reason.
        """
        span = self.band_high - self.band_low
        slots = span / self.bin_width
        remainder = abs(slots - round(slots))
        if remainder > GRID_TOLERANCE:
            raise ValueError(
                f"a band of {self.band_low} to {self.band_high} is {span} wide, which does "
                f"not divide into whole slots of {self.bin_width}: it leaves "
                f"{remainder * self.bin_width} over. Move band_high, band_low or bin_width"
            )
        return self

    @model_validator(mode="after")
    def _the_band_opens_below_where_it_closes(self) -> Self:
        """A band that opens at or above its own top holds no slots at all."""
        if self.band_low >= self.band_high:
            raise ValueError(
                f"the band opens at {self.band_low} and closes at {self.band_high}, so it "
                "holds no scores"
            )
        return self

    @model_validator(mode="after")
    def _a_step_may_not_outrun_the_band(self) -> Self:
        """A day's move may not carry the line outside the record that proposed it.

        The record holds slots only between `band_low` and `band_high`, so a step
        wider than that span can put the line where no slot exists and the next
        fit has nothing to read. The dead zone is checked against the same span:
        a zone as wide as the band would make every proposal no move at all.
        Spelled as a validator rather than a field bound because the span is two
        other fields and a literal would drift from them.

        This replaced the margin check on 2026-09-19. That one refused a step at
        or above the gap between the line and the nearest pair marked as two
        stories; the 200 labels marked that day put the nearest such pair at
        0.9407, above the 0.94 line, so the gap it guarded is gone and a step
        sized against it guards nothing (Guardrail #10).
        """
        span = self.band_high - self.band_low
        slots = round(span / self.bin_width)
        for name, bins in (
            ("max_down_bins", self.max_down_bins),
            ("max_up_bins", self.max_up_bins),
            ("dead_zone_bins", self.dead_zone_bins),
        ):
            if bins >= slots:
                raise ValueError(
                    f"{name} is {bins} slots and the band runs {self.band_low} to "
                    f"{self.band_high}, which is {slots} slots of {self.bin_width}. A move "
                    "that size can put the line outside the record it was fitted from"
                )
        return self

    @model_validator(mode="after")
    def _a_fall_lands_faster_than_a_rise(self) -> Self:
        """The line falls fast and rises slow, and this refuses a config that reverses it.

        The house rule is to publish less rather than more: when two feeds give
        near-identical coverage that is the feed's fault, so the move that folds
        fewer stories together arrives quickly and the move that folds more
        arrives over weeks. Lowering the line publishes less, so down is the fast
        direction in both mechanisms - the damping weight and the daily cap.

        Written as a refusal rather than as a comment because the shape reads
        backwards to anyone who has not been told the rule, and the obvious
        tidy-up is to point it the other way.
        """
        if self.fall_weight <= self.rise_weight:
            raise ValueError(
                f"fall_weight is {self.fall_weight} and rise_weight is {self.rise_weight}, "
                "so the line would rise at least as fast as it falls. Lowering the line "
                "publishes less, and that is the direction that is meant to be quick"
            )
        if self.max_down_bins <= self.max_up_bins:
            raise ValueError(
                f"max_down_bins is {self.max_down_bins} slots and max_up_bins is "
                f"{self.max_up_bins}, so a day could rise at least as far as it falls. "
                "Lowering the line publishes less, and that is the direction that is "
                "meant to be quick"
            )
        return self


class SameStoryConfig(Model):
    """How alike two of a day's items have to be before they are one story.

    One score, and the score is a weighted sum of terms that each run 0 to 1.
    Nested rather than three flat knobs under `assemble` because the weights
    carry an invariant ACROSS them - they sum to 1.0 - and a knob whose legal
    value depends on another knob's value belongs in the model where a validator
    can see both.

    **The sum-to-one rule is what keeps the floor meaning something.** The floor
    is a number on the same 0-to-1 scale as every term, so a person reading
    `config/idhazh.json` can compare the floor against a term without first
    working out what the weights add up to. Let them sum to 1.3 and the floor
    silently becomes easier to clear every time a weight moves, which is the
    failure this model exists to make impossible.

    It ships with all the weight on the cosine, which is exactly what the pass
    scored before this model existed. The weights are fitted against hand labels
    in a later change; until then this is a rewrite that changes no published
    group rather than a retune.
    """

    cosine_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "How much of the score is the cosine between the two vectors the day "
            "already carries. 1.0 ships, which is the whole score and is what the pass "
            "used before the composite existed - so the composite lands changing no "
            "published group, and the weights move against labels rather than against "
            "taste. It is the strongest single term measured so far: it separates 97.4 "
            "percent of the labelled pairs. NOT comparable to assist.similarity_floor, "
            "which scores a reader's query against an item rather than two items "
            "against each other, so the two distributions are different shapes."
        ),
    )
    key_point_weight: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "How much of the score is the share of words the two items' key points "
            "have in common - the words of both lists reduced the way a headline is "
            "reduced, then what they share over what they have between them. 0.0 "
            "ships, so the term is computed and logged and carries no weight yet: the "
            "composite is a rewrite first and a retune second. It is the only term "
            "beside the cosine whose different-story pairs stay below its same-story "
            "pairs with room to spare - a 99th percentile of 0.0962 against a "
            "same-story median of 0.2419, so the two populations barely touch - which "
            "is why it is the second term rather than one of several."
        ),
    )
    floor_min: float = Field(
        default=0.94,
        ge=0.0,
        le=1.0,
        description=(
            "What the weighted score has to reach before two items are one story, and "
            "EVERY pair inside a group has to reach it - not only each item against "
            "the one it joined. On the same 0-to-1 scale as every term, because the "
            "weights sum to 1.0. Set by labels rather than by taste: 0.94 is the first "
            "round hundredth above the highest pair marked as two stories in the eleven "
            "committed days read on 2026-09-01, which put that pair at 0.9317. The 200 "
            "pairs labelled on 2026-09-19 put it at 0.9407 instead - ABOVE this line - so "
            "the margin this number used to carry is gone and the line now admits one "
            "known two-story pair. No line fixes that: the same labels mark a pair at "
            "0.9406 as one story and another at 0.9409 as one story, so the two "
            "populations interleave inside three slots. Raising this costs missed "
            "duplicates, which a reader sees as the same story twice; lowering it costs a "
            "false merge, which is a story that never ran, so the two errors are not equal "
            "and this number leans high. It was measured against the cosine alone, which "
            "is what the shipped weights still score."
        ),
    )
    adaptive_dedup_threshold: SimilarityThresholdConfig | None = Field(
        default=None,
        description=(
            "The content-similarity judge's own knobs, absent when that judge is not "
            "configured. Optional rather than built by a default factory, because a "
            "factory cannot express 'no judge is configured' - absent and "
            "present-at-defaults read the same afterwards, so nothing could tell the "
            "council's own night apart from a night this judge runs. The council's "
            "runner numbers are in `council` and stand whether or not this block does."
        ),
    )

    def judging_knobs(self) -> SimilarityThresholdConfig:
        """This judge's block, or a refusal naming what is missing.

        Every stage of the content-similarity judge reads the block through
        here, so a stage that runs with no block configured says so in one
        sentence instead of raising on an attribute of `None`.
        """
        if self.adaptive_dedup_threshold is None:
            raise ValueError(
                "assemble.same_story.adaptive_dedup_threshold is absent, so the "
                "content-similarity judge is not configured. Add the block to "
                "config/idhazh.json, or do not run this judge"
            )
        return self.adaptive_dedup_threshold

    @model_validator(mode="after")
    def _the_weights_sum_to_one(self) -> Self:
        """A score that is not on 0 to 1 cannot be compared against a floor on 0 to 1.

        Checked here rather than left to whoever edits the file, because the
        failure is silent: weights that sum to 1.3 push every pair up, the floor
        stops meaning what the labels measured, and the day publishes a merge
        nobody chose. Nothing downstream re-checks it.
        """
        weights = {
            "cosine_weight": self.cosine_weight,
            "key_point_weight": self.key_point_weight,
        }
        total = math.fsum(weights.values())
        if not math.isclose(total, 1.0, abs_tol=_WEIGHTS_TOLERANCE):
            spelled = ", ".join(f"{name}={value}" for name, value in weights.items())
            raise ValueError(
                f"the same_story weights must sum to 1.0, and these sum to {total} "
                f"({spelled}). Every term runs 0 to 1, so the weights are what keep "
                "the score on the same scale as floor_min"
            )
        return self

    @model_validator(mode="after")
    def _the_band_opens_below_the_line_it_replaces(self) -> Self:
        """A band that opens above today's floor can only ever confirm what already merges.

        Every pair it judges is a pair the pass merges anyway, so the record
        fills with agreements and the line can never come down - while every
        number in the file still looks legal. Checked on this model because
        `floor_min` is this model's field and a nested model cannot see it.

        The band also has to reach the hardest pair we hold a label for, which
        is a second ceiling and not the same one: a floor raised above
        `HOLDOUT_TWO_STORY_MAX` would let the band open above the pair a wrong
        line publishes first, so the record would fill with easy agreements and
        never judge the case that could prove the line wrong.

        A config with no judge in it has no band, so there is nothing to check.
        """
        if self.adaptive_dedup_threshold is None:
            return self
        band_low = self.adaptive_dedup_threshold.band_low
        if band_low >= self.floor_min:
            raise ValueError(
                f"adaptive_dedup_threshold.band_low is {band_low} and floor_min is "
                f"{self.floor_min}, so every pair in the band already merges and the "
                "fitted line could only ever rise"
            )
        if band_low >= HOLDOUT_TWO_STORY_MAX:
            raise ValueError(
                f"adaptive_dedup_threshold.band_low is {band_low} and the highest pair the "
                f"labelled set marks as two stories is {HOLDOUT_TWO_STORY_MAX}, so the "
                "band cannot draw the pair the line most has to get right"
            )
        return self


class AssembleConfig(Model):
    """What the published day does with the items a run finished.

    Its own group rather than a knob under `assist`, because `AppearanceConfig`
    imports `AssistConfig` whole: a threshold the pipeline applies once at build
    time would then also land in `config/appearance.json`, where it has no
    reader and no meaning.
    """

    same_story: SameStoryConfig = Field(default_factory=SameStoryConfig)

    same_story_window_hours: float = Field(
        default=36.0,
        ge=0.0,
        description=(
            "How far apart two stories may have appeared and still be one story. A "
            "story that breaks at 23:00 and is picked up at 07:00 is one story, and a "
            "day boundary is an accident of the calendar rather than a fact about the "
            "news - so the window is hours between the two stories' own times, not "
            "which day each was published on. 36 hours covers an evening break picked "
            "up the next morning and refuses a genuine follow-up two days later. It "
            "is an ESTIMATE: what would overturn it is the age gap of the cross-day "
            "pairs a person marks as one story. The window is also what bounds the "
            "read - the pass loads only the earlier days it can still reach, so the "
            "cost is set by this number and never by how much archive exists "
            "(Guardrail #12). 0 keeps the pass inside one published day, which is "
            "what it did before this knob existed, and is the revert."
        ),
    )

    group_identical_titles: bool = Field(
        default=True,
        description=(
            "Whether two of a day's items are one story when their published headlines "
            "say the same thing - compatibility-normalised, casefolded, and with "
            "everything that is not a letter or a digit turned into a space. The words "
            "must match exactly; the numbers only have to agree to the coarser of the "
            "two precisions they were written with, so `$12.9 billion` and `$12.93 "
            "billion` are one acquisition while `25 percent` and `50 percent` are two "
            "different figures. This is a second way into a group beside "
            "same_story.floor_min, never a replacement: every pair inside a group "
            "still has to clear one of the two, and an item with no vector is still "
            "never grouped. It exists because the cosine is taken over `title. "
            "summary`, and the summary is our own prose about ONE article and is most "
            "of that string, so two honest tellings of one story are pulled apart by "
            "the part that is guaranteed to differ. Measured "
            "2026-09-14 on a developer machine / Python 3.14.2 over the "
            "twenty-five committed days and 9,353 items: fifty-three cross-source "
            "pairs share a headline, their cosine has a median of 0.9177 against a "
            "floor of 0.94, and the highest-scoring pair marked as TWO stories "
            "sits at 0.9407 (2026-09-19 labels) - above both that median and the floor, "
            "so no threshold separates the two "
            "populations and lowering same_story.floor_min cannot fix this. Turning "
            "this off restores the vector-only rule, which is the revert path an "
            "operator has if a shared headline ever turns out to be two stories. Ruled "
            "by Andre and the Editor, 2026-09-14, and the rounding tolerance by the "
            "owner the same day; the reasoning is in "
            "docs/architecture/publishing/layout.md."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_a_removed_knob(cls, data: Any) -> Any:
        return refuse_a_removed_knob("assemble", data, SUPERSEDED_ASSEMBLE_NAMES)


class PlacementConfig(Model):
    """The frame a person sets over the head of the published day, and what age does to it.

    Nobody reads this digest before it publishes and it publishes five times a
    day, so a standing editorial decision can only reach a reader as arithmetic
    that runs without one. These six numbers are that decision. The rule they
    express and the measurements behind them are in docs/concepts/placement.md.

    Every cap here displaces and none of them shortens: a story a cap holds out
    of the head keeps its place in the day, lower down. A reader cannot see what
    was left out, so leaving something out is the one thing a frame may not buy.

    The three `freshness_` numbers are not caps and take nothing away either.
    They are one curve, read when the page is drawn rather than when the story
    was planned, and they decide where a story that has been running all day
    sits against one that broke an hour ago. `placement.freshness_multiplier`
    owns the arithmetic.
    """

    head_items: int = Field(
        default=20,
        ge=0,
        description=(
            "How many of the day's first stories the frame governs. A COUNT and never "
            "a share: what a reader sees before deciding whether to scroll does not "
            "grow with the day, and a share of a 731-story day is a head nobody "
            "reaches (Jony, 2026-09-11). The stream pages at twelve, so 20 is the "
            "cold load plus one page action. Past this slot the order is the score's "
            "alone. 0 switches the frame off and publishes the score's order whole."
        ),
    )
    max_desk_in_head: int = Field(
        default=5,
        ge=1,
        description=(
            "How many of the first head_items stories one desk may hold. 5 of 20 with "
            "five desks is the largest cap that still guarantees three different desks "
            "in the first twelve stories - the cold load - and four in the first "
            "twenty; 6 guarantees only two in the first twelve. Set on what the reader "
            "is guaranteed rather than on how often it fires, because measurement "
            "killed the alternative: over the 13 committed days carrying rank_score, "
            "read 2026-09-13 on Intel Core i7-1265U / Windows 11 / Python 3.14.2, the "
            "biggest desk in the top 20 ran at a median of 12 and reached all 20 on "
            "2026-09-07, so EVERY cap from 4 to 10 fires on 85 percent of days or more "
            "and 'rarely binds' was not available to buy. Ruled 5 by Jony and by "
            "Editor independently. Raising it costs desks on the first screen; "
            "lowering it to 4 pins the head at four of each desk every day, which is a "
            "quota rather than a cap and cannot report a day one desk genuinely owned."
        ),
    )
    head_no_repeat: int = Field(
        default=10,
        ge=0,
        description=(
            "How far down the head one feed may not repeat. No feed holds more than "
            "one of the first this-many stories. Measured over the same 13 days, the "
            "biggest feed in the first ten ran from 3 to 8, so this is load-bearing "
            "rather than decorative. 0 switches the feed rule off and leaves the desk "
            "cap alone."
        ),
    )

    freshness_offset_hours: float = Field(
        default=6.0,
        ge=0.0,
        description=(
            "How many hours a story keeps its whole score before age counts against it "
            "at all. A flat shoulder rather than a curve that starts falling at minute "
            "one: a story nothing has had time to answer yet should not be marked down "
            "for being new. 6 hours is an ESTIMATE and not a measurement - the day "
            "publishes five times, so 6 hours is about one publishing cycle, which is "
            "the shortest shoulder that lets a story reach the next run at full value. "
            "What would overturn it is the published age of the stories that actually "
            "led each committed day. 0 removes the shoulder, and age starts counting "
            "from the minute a story appeared."
        ),
    )
    freshness_scale_hours: float = Field(
        default=24.0,
        gt=0.0,
        description=(
            "How far past the shoulder a story has to be before it is worth "
            "freshness_decay_at_scale of what it was. Read the two as one sentence: at "
            "this many hours past the shoulder, a story keeps that much of its score. "
            "The width of the curve is derived from those two numbers rather than "
            "typed, so a person sets a sentence they can read instead of a variance "
            "nobody can picture. 24 hours is collect.max_age_hours, the age past which "
            "a story may not be added to the day at all, so the shipped pair says a "
            "story that has been running for a whole admission window past its "
            "shoulder is worth half."
        ),
    )
    freshness_decay_at_scale: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "What a story is worth freshness_scale_hours past the shoulder, as a share "
            "of what it was worth inside it. 0.5 is half, the same word "
            "collect.recency_half_life_hours already uses at plan time, so an operator "
            "reads one vocabulary rather than two. Exactly 1.0 switches the whole "
            "curve off: every story scores 1.0 at every age and the leading block is "
            "ordered the way it was before the curve existed. That is the revert, and "
            "it is one edit to one line."
        ),
    )

    @model_validator(mode="after")
    def _window_fits_the_head(self) -> Self:
        """A no-repeat window wider than the head governs slots the frame does not.

        It would read as a live rule and do nothing past head_items, which is the
        kind of dead knob a later reader treats as load-bearing.
        """
        if self.head_no_repeat > self.head_items:
            raise ValueError(
                "head_no_repeat is a window inside the head, so it cannot be wider "
                "than head_items"
            )
        return self


class LensWeightsConfig(Model):
    """What a run asks about its own lens weights, and how much of the answer it keeps.

    A lens weight is a number somebody picked, and nothing committed said what a
    different number would have done. Every run now scores a bounded pool of its
    candidates twice - once at the committed weights and once at a candidate
    weight - and writes both to `state/counterfactual-scores/`. Nothing here
    moves a weight, an item, or a published payload. These knobs decide what the
    run asks and how many rows it leaves behind.

    The ledger is appended to forever, so every knob here is a bound on ONE
    run's work rather than on the archive's size (CLAUDE.md Guardrail #12).
    `window_days` is the other end of the same rule: it is how far back a reader
    of the ledger may look, and it is what the retention pass keeps.
    """

    counterfactual_multiplier: float = Field(
        default=1.25,
        gt=0.0,
        description=(
            "What the counterfactual multiplies each committed lens weight by. Above "
            "1.0 on purpose: a heavier weight is the question a committed archive "
            "cannot answer afterwards, because it is the one that would have lifted a "
            "story the run refused, and a refused story leaves no other trace. 1.25 is "
            "an ESTIMATE and has not been measured - it is large enough to move a "
            "story across the cut on a crowded desk and small enough to stay inside "
            "the step a later tuning loop would allow. Exactly 1.0 asks nothing: both "
            "scores come out equal and every row is a byte with no question in it."
        ),
    )
    counterfactual_refused_per_desk: int = Field(
        default=20,
        ge=0,
        description=(
            "How many of each desk's refused candidates the run records, highest score "
            "first. Everything the run TOOK is recorded whatever this says. 20 keeps "
            "the band around the cut, where a bonus decides; a candidate further down "
            "would not cross under any weight this probe asks about, so its row carries "
            "no question. At about 80 items taken and five desks this is roughly 180 "
            "rows a run. 0 records the taken items alone."
        ),
    )
    window_days: int = Field(
        default=30,
        ge=1,
        description=(
            "How far back a reader of the counterfactual ledger may look, and so how "
            "much of it the retention pass keeps. Both ends of one rule, in one knob, "
            "because a window a reader opens and a window the prune keeps have to be "
            "the same window or the reader reads a hole. 30 days is an ESTIMATE: long "
            "enough that a lens firing a few times a day still has a few hundred rows "
            "in it, short enough that a weight changed last month is not still being "
            "argued from."
        ),
    )
