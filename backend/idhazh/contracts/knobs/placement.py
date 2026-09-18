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

#: The gap between TODAY's floor and the highest-scoring pair a person marked as
#: TWO stories - Ontario's pushback against the lake renaming, at 0.9317, against
#: a floor of 0.94. Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 /
#: Python 3.14.2 over 3,978 items across eleven committed days. It is a reading
#: of one moment rather than a property of the system: the live margin is
#: applied - 0.9317, and it shrinks every time the line falls. A single downward
#: step larger than this reading can cross the margin in one day, which is why it
#: bounds max_down_step rather than sitting in a comment.
HOLDOUT_MARGIN: Final = 0.0083

#: Wall clock for one judge call at 764 read tokens, in seconds. Derived from the
#: repository's own reading of 9.85 tokens a second - median over 4,117 timed
#: rows, slowest 8.25, fastest 44.71, taken 2026-09-09 on a stock ubuntu-latest
#: (docs/reference/measurements.md). It is here because pair_budget is bounded
#: against the leg timeout and that arithmetic needs a seconds-a-call figure with
#: a source. Row 17 replaces it with a reading taken on the judge prompt itself.
SECONDS_A_CALL: Final = 77.6


class SimilarityThresholdConfig(Model):
    """How the merge line fits itself, and the gates it has to clear before it may.

    Nested inside `SameStoryConfig` rather than flat under `assemble`, for the
    reason that model's own docstring gives: a knob whose legal value depends on
    another knob's value belongs where a validator can see both. `max_down_step`
    is bounded by a margin measured against `floor_min`, and `band_low` has to
    sit below the line `floor_min` currently holds.

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
            "measured pairs start: the highest pair a person marked as two stories sits at "
            "0.9317, so the band opens well below every decision the line has to get right."
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
            "fitted line. 0.001 is eight times finer than the 0.0083 margin the line has to "
            "stay above, so the slot edge is never what puts the line on the wrong side of a "
            "hand-marked pair. Finer costs slots and coarser costs precision on the one "
            "number this feature exists to set."
        ),
    )
    discard_share: float = Field(
        default=0.01,
        gt=0.0,
        lt=0.5,
        description=(
            "What share of judged NO pairs the fit sets aside at the top before placing the "
            "line. 0.01 is what stops one bad verdict setting the number: a single NO at "
            "0.97 would otherwise pin the line at 0.971 for ever, because the line is the "
            "stopped slot's upper edge. floor(total * 0.01) sets one pair aside at 100 "
            "negatives and two at 200, which is what minimum_negatives waits for."
        ),
    )
    smoothing_weight: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description=(
            "How much of a DOWNWARD move lands today. 0.15 means a relaxation arrives over "
            "five to seven days while a tightening arrives whole, because raising the line "
            "reduces wrong merges and lowering it increases them. Symmetric damping would "
            "make the safe move a week late."
        ),
    )
    max_down_step: float = Field(
        default=0.005,
        gt=0.0,
        lt=HOLDOUT_MARGIN,
        description=(
            "The furthest the line may fall in one day. 0.005 leaves TODAY's 0.0083 gap "
            "uncrossable in one day. The gap is not a constant: it is applied minus 0.9317, "
            "so it shrinks as the line falls, and once the line reaches 0.9367 one legal "
            "step lands on the marked pair. That is why the holdout report is read on every "
            "day rather than once. The owner proposed 0.010, which is larger than today's "
            "gap, so it would have crossed on its first step."
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
            "How many pairs a day may be judged. 200 pairs judged twice is 400 calls, which "
            "is 100 calls on each of four legs, which at 77.6 seconds a call is 2 hours 9 "
            "minutes of model time a leg. That figure is derived from 9.85 tokens a second "
            "measured on a stock runner, not from a judge call; row 17 measures a real one. "
            "Raising it is a job-timeout question before it is a quality one, and a "
            "validator refuses a value that does not fit the leg."
        ),
    )
    shards: int = Field(
        default=4,
        ge=1,
        le=8,
        description=(
            "How many judging legs split the day. 4 legs, one llama-server each, because one "
            "server on the configured weights already peaks at 12.57 to 13.16 GiB and "
            "reaches 14.31 GiB with the shard's python - 96.0 percent of the 16 GB runner, "
            "measured 2026-09-08 over four shards of run 2026-08-29-3. A second server on "
            "one runner does not fit at all. The ceiling of 8 is what a GitHub matrix leg "
            "costs rather than a measured limit."
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
            "200, because discard_share is 0.01 and one percent of anything smaller sets "
            "aside less than two pairs, which is the same as setting aside none."
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
    def _a_move_may_not_cross_the_margin_in_one_day(self) -> Self:
        """One step may not carry the line past the closest pair a person marked apart.

        Spelled as a validator as well as a field bound so that the refusal
        names the margin and the measurement instead of printing a bare `lt`
        failure (Guardrail #10).
        """
        if self.max_down_step >= HOLDOUT_MARGIN:
            raise ValueError(
                f"max_down_step is {self.max_down_step}, and the gap between today's floor "
                f"and the highest pair a person marked as two stories is {HOLDOUT_MARGIN} "
                "(0.94 against 0.9317, measured 2026-09-01). A step that size crosses the "
                "margin in one day"
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
            "weights sum to 1.0. Set by hand labels rather than by taste. Every group "
            "the pass forms over the eleven committed days was read and marked "
            "same-story or not, measured 2026-09-01 on Intel Core i7-1265U / Windows "
            "11 / Python 3.14.2 over 3,978 items: at 0.93 one group of thirty is two "
            "different stories - Ontario's pushback against the lake renaming, merged "
            "into Google doing the renaming, at 0.9317 - and at 0.94 all twenty-two "
            "groups are one story each. The rule is the first round hundredth above "
            "the highest-scoring pair a person marked as two stories, which leaves a "
            "margin of 0.0083. That margin is thin, and the way to widen it is more "
            "labels rather than a higher number. Raising this costs missed duplicates, "
            "which a reader sees as the same story twice; lowering it costs a false "
            "merge, which is a story that never ran, so the two errors are not equal "
            "and this number leans high. It was measured against the cosine alone, "
            "which is what the shipped weights still score."
        ),
    )
    adaptive_dedup_threshold: SimilarityThresholdConfig = Field(
        default_factory=SimilarityThresholdConfig
    )

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
        """
        band_low = self.adaptive_dedup_threshold.band_low
        if band_low >= self.floor_min:
            raise ValueError(
                f"adaptive_dedup_threshold.band_low is {band_low} and floor_min is "
                f"{self.floor_min}, so every pair in the band already merges and the "
                "fitted line could only ever rise"
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
            "floor of 0.94, and the highest-scoring pair a person marked as TWO stories "
            "sits at 0.9317 - above that median, so no threshold separates the two "
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
