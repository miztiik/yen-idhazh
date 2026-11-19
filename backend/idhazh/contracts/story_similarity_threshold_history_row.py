"""What each threshold was, what the night's evidence proposed for it, and what the run applied.

One row a run, written on the nights a threshold moved AND on the nights it held: a
threshold that follows the evidence has to leave a record on the nights it stayed put, or a
reader cannot tell a held night from a night nothing ran. The row is for two thresholds at
once - the lower bound below which pairs are fully dissimilar and the upper bound above which
they are fully similar - so every per-threshold column appears twice, once under `lower_` and
once under `upper_`.

Every number the move came from is a column of its own: the thresholds before and after, the
evidence the curve read, the curve itself and the pull on it, the estimate and its gap from
the threshold, how many nights the gap has stood, and what limited or held the move. The
night's own totals sit beside them: how many pairs each lightly sampled end of the range held
and how many were usable, how many pairs the reporting runners were dealt and how each ended,
the rates over those counts, the clocks, and the answers to the known-answer pairs. Those
known-answer pairs are judged on top of the draw and are in no count or clock of the funnel.

Nothing here decides what publishes. The thresholds record where the judge's own answers say
the same-story share crosses two levels, and the next night's draw follows them.

Three words this row uses. A **gap** is the fitted curve's estimate minus the threshold the
night started from. The **ignore range** is how small a gap may be before the night does not
act on it. **Widening** moves a threshold out, the lower one down and the upper one up, so
the ambiguous range between them grows; **narrowing** moves it in.

The ledger door files it under
`state/raw/content-similarity-judge/threshold-history/<YYYY>/<MM>/<DD>/`, and the gardener
packs it under `state/compact/content-similarity-judge/threshold-history/`. The folder is
spelled in `idhazh.ledger`, which is where a path belongs and which this module may not import
(CLAUDE.md section 4).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from idhazh.contracts.base import (
    SLUG_PATTERN,
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
)
from idhazh.contracts.story_similarity_pair import (
    JudgeModelId,
    SameStoryVerdict,
    ScorerModelId,
)
from idhazh.contracts.story_similarity_pair_verdict import (
    RECOMPUTED_TOLERANCE,
    ConfigVersionsText,
    canonical_compact_object,
)


class ThresholdMoveLimit(StrEnum):
    """What cut a threshold's move short, in one word. `NONE` means nothing did.

    The step limits are the largest move a night may make: outward is fast and inward is
    slow, and a gap beyond the far-gap line takes a larger step either way. The three
    bounds are where the threshold came to rest against a limit of the range itself.
    """

    NONE = "none"
    WIDENING_STEP = "widening_step"
    NARROWING_STEP = "narrowing_step"
    FAR_GAP_STEP = "far_gap_step"
    LOWEST_ALLOWED = "lowest_allowed"
    HIGHEST_ALLOWED = "highest_allowed"
    SMALLEST_GAP = "smallest_gap"


class ThresholdHoldReason(StrEnum):
    """Why a threshold did not move tonight, in one word. `NONE` means it moved.

    Written in the order the reasons are tried: too little evidence first, then a fit that
    failed, then a gap too small to act on, then a gap that has not yet stood long enough.
    """

    NONE = "none"
    NOT_ENOUGH_EVIDENCE = "not_enough_evidence"
    FIT_FAILED = "fit_failed"
    WITHIN_IGNORE_RANGE = "within_ignore_range"
    WAITING_FOR_SECOND_NIGHT = "waiting_for_second_night"


#: The reasons that come from a fitted curve's gap: the move was made, or withheld because
#: the gap was small or had not stood long enough. Each carries the curve, the estimate and
#: the gap. A hold for thin evidence is not here, because the fit may not have run, and a
#: failed fit is the one hold that has no estimate to carry.
_REASONS_THAT_READ_A_GAP: Final = frozenset(
    {
        ThresholdHoldReason.NONE,
        ThresholdHoldReason.WITHIN_IGNORE_RANGE,
        ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT,
    }
)

#: What each per-threshold column means, once, because the row carries every one of them for
#: each bound. `{side}` is `lower` or `upper`.
_MEANING: Final[Mapping[str, str]] = MappingProxyType(
    {
        "threshold_before": (
            "The {side} bound threshold the night started from: the threshold_after of the "
            "newest row dated before the night, or the configured start when none is recent "
            "enough, so a re-run of the night starts from the same place."
        ),
        "share_level": (
            "The same-story share that defines the {side} bound: the threshold is the score "
            "where the fitted curve reaches it."
        ),
        "nights_used": (
            "How many nights of evidence the {side} estimate read. Fewer than the window "
            "when a change of judge, scorer or settings restarted it."
        ),
        "usable_pairs_used": (
            "How many usable pairs near the {side} threshold the estimate read, over those "
            "nights."
        ),
        "window_first_date": (
            "The first UTC day of the evidence the {side} estimate read. Empty exactly when "
            "no night and no pair was read."
        ),
        "curve_intercept": (
            "The fitted curve's intercept, a, in P(same story) = 1 / (1 + exp(-(a + b * "
            "score))) for the {side} bound. Empty, with the steepness, the estimate and the "
            "gap, when no curve was fitted or it could not give an estimate."
        ),
        "curve_steepness": (
            "The fitted curve's steepness, b, in the same formula. Always above zero when "
            "present: a curve that does not rise is not stored."
        ),
        "pull_centre": (
            "The steepness the {side} fit was pulled towards: the median of recent nights' "
            "steepness, or the starting steepness until enough nights exist."
        ),
        "pull_spread": (
            "How loose that pull was: the standard deviation of the pull on the {side} "
            "fit's steepness. A smaller spread pulls harder."
        ),
        "estimate": (
            "The score where the {side} curve reaches its share level. Empty when no curve "
            "was stored."
        ),
        "gap": (
            "The {side} estimate minus the threshold before. Empty when there is no "
            "estimate."
        ),
        "nights_beyond_ignore_range": (
            "How many nights in a row, tonight included, the {side} gap has been beyond the "
            "ignore range with the same sign. Zero when there is no gap or it is within the "
            "range."
        ),
        "move": (
            "The {side} threshold after minus the threshold before, signed. Zero when the "
            "threshold was held, and zero when a limit cut the move to nothing."
        ),
        "move_limited_by": "What cut the {side} move short, or none.",
        "held_because": "Why the {side} threshold did not move tonight, or none when it did.",
        "threshold_after": (
            "The {side} bound threshold the next night starts from. Equal to the threshold "
            "before when the threshold was held."
        ),
    }
)


def _threshold_column(side: str, name: str, **constraints: Any) -> Any:
    """One per-threshold column's declaration, its meaning read from the table above."""
    return Field(description=_MEANING[name].format(side=side), **constraints)


def _is_a_whole_number(cell: object) -> bool:
    """A JSON count: an integer, which is not a boolean and is not below zero."""
    return isinstance(cell, int) and not isinstance(cell, bool) and cell >= 0


def _is_a_margin(cell: object) -> bool:
    """A JSON number between 0 and 1, which is not a boolean."""
    return isinstance(cell, int | float) and not isinstance(cell, bool) and 0 <= cell <= 1


def _checked_canary_answers(text: str) -> str:
    """The known-answer pairs' answers, keyed by canary id, six cells each.

    An id that is absent was never judged, and a cell that is null is a reading that was
    refused or missing, so neither is dropped or turned into a guess. Only the runner that
    judged the pair is always known. The cells are positional, so a seventh would need a new
    version of this row that reads six cells or seven.
    """
    held = canonical_compact_object(text, column="canary_answers")
    if not held:
        raise ValueError("canary_answers names at least one canary pair, or is left empty")
    for canary_id, answer in held.items():
        if not re.fullmatch(SLUG_PATTERN, canary_id):
            raise ValueError(f"canary_answers names {canary_id!r}, which is not a slug")
        if not isinstance(answer, list) or len(answer) != 6:
            raise ValueError(
                f"canary_answers gives {canary_id} {answer!r}, and an answer is six cells: "
                "the answer in file order, the answer swapped, the two first-token margins, "
                "the file-order call's prompt tokens and the runner index"
            )
        words, margins, tokens, runner = answer[:2], answer[2:4], answer[4], answer[5]
        if any(word is not None and word not in SameStoryVerdict for word in words):
            raise ValueError(f"canary_answers gives {canary_id} an answer that is not a verdict")
        if not all(margin is None or _is_a_margin(margin) for margin in margins):
            raise ValueError(f"canary_answers gives {canary_id} a margin outside 0 to 1")
        if not (tokens is None or _is_a_whole_number(tokens)):
            raise ValueError(f"canary_answers gives {canary_id} a prompt count that is not whole")
        if not _is_a_whole_number(runner):
            raise ValueError(f"canary_answers gives {canary_id} no whole-number runner index")
    return text


#: The known-answer pairs' answers as one compact JSON object, empty before any were judged.
CanaryAnswersText = Annotated[str, AfterValidator(_checked_canary_answers)]


@dataclass(frozen=True, slots=True)
class _Reading:
    """One bound's columns, gathered so one check reads both bounds the same way."""

    before: float
    after: float
    move: float
    limited_by: ThresholdMoveLimit
    held_because: ThresholdHoldReason
    nights_used: int
    usable_pairs_used: int
    window_first_date: str | None
    intercept: float | None
    steepness: float | None
    estimate: float | None
    gap: float | None
    nights_beyond_ignore_range: int


def _the_bound_reads_coherently(side: str, reading: _Reading) -> None:
    """The move, the gap, the curve, the count of nights and the words say one thing.

    The words are what a reader scans and the numbers are what the next night reads, and a
    row where a `held_because` sits beside a moved threshold lies to one of them. Every
    clause here is a shape the night's computation cannot produce.
    """
    reason = reading.held_because
    if abs(reading.move - (reading.after - reading.before)) > RECOMPUTED_TOLERANCE:
        raise ValueError(
            f"the {side} move is {reading.move}, and the threshold went from "
            f"{reading.before} to {reading.after}"
        )
    if reason is not ThresholdHoldReason.NONE:
        if reading.move != 0.0 or reading.after != reading.before:
            raise ValueError(
                f"the {side} threshold was held ({reason.value}), so it stays at "
                f"{reading.before} and does not move, and this row takes it to {reading.after}"
            )
        if reading.limited_by is not ThresholdMoveLimit.NONE:
            raise ValueError(
                f"the {side} threshold was held, so no move was made for "
                f"{reading.limited_by.value} to cut short"
            )
    elif reading.move == 0.0 and reading.limited_by is ThresholdMoveLimit.NONE:
        raise ValueError(
            f"the {side} threshold moved, so the row carries a move, or the limit that cut "
            "the move to nothing"
        )
    curve = (reading.intercept, reading.steepness, reading.estimate, reading.gap)
    if any(cell is None for cell in curve) and any(cell is not None for cell in curve):
        raise ValueError(
            f"the {side} curve's intercept, steepness, estimate and gap are all on the row "
            "or all absent"
        )
    fitted = reading.gap is not None
    if (
        reading.estimate is not None
        and reading.gap is not None
        and abs(reading.gap - (reading.estimate - reading.before)) > RECOMPUTED_TOLERANCE
    ):
        raise ValueError(
            f"the {side} gap is {reading.gap}, and the estimate {reading.estimate} less the "
            f"threshold before {reading.before} is {reading.estimate - reading.before}"
        )
    if reason in _REASONS_THAT_READ_A_GAP and not fitted:
        raise ValueError(
            f"the {side} threshold's hold or move ({reason.value}) comes from a gap, and "
            "this row has no fitted curve to give one"
        )
    if reason is ThresholdHoldReason.FIT_FAILED and fitted:
        raise ValueError(f"the {side} fit failed, so the row carries no curve from it")
    if (reading.window_first_date is None) != (
        reading.nights_used == 0 and reading.usable_pairs_used == 0
    ):
        raise ValueError(
            f"the {side} evidence window starts on a date exactly when a night or a pair "
            "was read"
        )
    if not fitted and reading.nights_beyond_ignore_range != 0:
        raise ValueError(f"the {side} threshold has no gap, so no night stands beyond the range")
    if reason is ThresholdHoldReason.WITHIN_IGNORE_RANGE and reading.nights_beyond_ignore_range:
        raise ValueError(f"the {side} gap is within the ignore range, so no night stands beyond it")
    if (
        reason in {ThresholdHoldReason.NONE, ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT}
        and reading.nights_beyond_ignore_range < 1
    ):
        raise ValueError(
            f"the {side} threshold moved or waited on a gap beyond the ignore range, so at "
            "least tonight stands beyond it"
        )


def _the_end_totals_follow_its_counts(
    end: str, available: int, usable: int, estimated: float | None
) -> None:
    """A lightly sampled end holds its usable pairs, and its estimate follows from them.

    The estimated total is the sum of one over the chance of each usable pair that answered
    one way, and one slice stands for the whole end, so it cannot exceed the pairs the end
    held. With no usable pair there is nothing to weight, and an empty estimate says so where
    a zero would read as a night that measured everything and found none.
    """
    if usable > available:
        raise ValueError(f"{usable} pairs {end} were usable, and only {available} were available")
    if (estimated is None) != (usable == 0):
        raise ValueError(
            f"the estimated total {end} is empty exactly when no pair there was usable"
        )
    if estimated is not None and estimated > available + RECOMPUTED_TOLERANCE:
        raise ValueError(
            f"the estimated total {end} is {estimated}, and only {available} pairs were "
            "available there"
        )


class StorySimilarityThresholdHistoryRow(Contract):
    """One run's reading of both thresholds: the evidence, the curves, the moves and the night."""

    model_config = ConfigDict(allow_inf_nan=False)

    __schema_stem__: ClassVar[str] = "story-similarity-threshold-history-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-18",
            change="Initial shape: both thresholds, the numbers behind each move, and the night.",
            why="A threshold that follows the evidence has to show every number it followed.",
        ),
    )

    date: DateStamp = Field(description="The digest date, a UTC day, this night judged.")
    run_id: RunId = Field(
        description=(
            "The council run that filed this row. Two runs of one night keep their own rows."
        )
    )
    scorer_model: ScorerModelId = Field(
        description=(
            "Which encoder produced the scores the night's pairs were drawn by. A recorded "
            "slug, independent of the models currently configured."
        )
    )
    cosine_weight: float = Field(
        ge=0.0,
        le=1.0,
        description="What the cosine was worth in the scores the night's pairs were drawn by.",
    )
    judge_model: JudgeModelId | None = Field(
        default=None,
        description=(
            "Which model judged, as its recorded slug. Empty on a night nothing was judged."
        ),
    )
    judge_policy_version: DateStamp | None = Field(
        default=None,
        description=(
            "UTC date identifying how the judge's emitted evidence was read; empty on a "
            "night nothing was judged."
        ),
    )
    config_versions: ConfigVersionsText = Field(
        description=(
            "Every config file the night read and the version of each, as one compact JSON "
            "object keyed by path relative to config/."
        )
    )

    lower_threshold_before: float = _threshold_column(
        "lower", "threshold_before", ge=-1.0, le=1.0
    )
    lower_share_level: float = _threshold_column("lower", "share_level", gt=0.0, lt=1.0)
    lower_nights_used: int = _threshold_column("lower", "nights_used", ge=0)
    lower_usable_pairs_used: int = _threshold_column("lower", "usable_pairs_used", ge=0)
    lower_window_first_date: DateStamp | None = _threshold_column(
        "lower", "window_first_date", default=None
    )
    lower_curve_intercept: float | None = _threshold_column(
        "lower", "curve_intercept", default=None
    )
    lower_curve_steepness: float | None = _threshold_column(
        "lower", "curve_steepness", default=None, gt=0.0
    )
    lower_pull_centre: float = _threshold_column("lower", "pull_centre")
    lower_pull_spread: float = _threshold_column("lower", "pull_spread", gt=0.0)
    lower_estimate: float | None = _threshold_column("lower", "estimate", default=None)
    lower_gap: float | None = _threshold_column("lower", "gap", default=None)
    lower_nights_beyond_ignore_range: int = _threshold_column(
        "lower", "nights_beyond_ignore_range", ge=0
    )
    lower_move: float = _threshold_column("lower", "move")
    lower_move_limited_by: ThresholdMoveLimit = _threshold_column("lower", "move_limited_by")
    lower_held_because: ThresholdHoldReason = _threshold_column("lower", "held_because")
    lower_threshold_after: float = _threshold_column(
        "lower", "threshold_after", ge=-1.0, le=1.0
    )

    upper_threshold_before: float = _threshold_column(
        "upper", "threshold_before", ge=-1.0, le=1.0
    )
    upper_share_level: float = _threshold_column("upper", "share_level", gt=0.0, lt=1.0)
    upper_nights_used: int = _threshold_column("upper", "nights_used", ge=0)
    upper_usable_pairs_used: int = _threshold_column("upper", "usable_pairs_used", ge=0)
    upper_window_first_date: DateStamp | None = _threshold_column(
        "upper", "window_first_date", default=None
    )
    upper_curve_intercept: float | None = _threshold_column(
        "upper", "curve_intercept", default=None
    )
    upper_curve_steepness: float | None = _threshold_column(
        "upper", "curve_steepness", default=None, gt=0.0
    )
    upper_pull_centre: float = _threshold_column("upper", "pull_centre")
    upper_pull_spread: float = _threshold_column("upper", "pull_spread", gt=0.0)
    upper_estimate: float | None = _threshold_column("upper", "estimate", default=None)
    upper_gap: float | None = _threshold_column("upper", "gap", default=None)
    upper_nights_beyond_ignore_range: int = _threshold_column(
        "upper", "nights_beyond_ignore_range", ge=0
    )
    upper_move: float = _threshold_column("upper", "move")
    upper_move_limited_by: ThresholdMoveLimit = _threshold_column("upper", "move_limited_by")
    upper_held_because: ThresholdHoldReason = _threshold_column("upper", "held_because")
    upper_threshold_after: float = _threshold_column(
        "upper", "threshold_after", ge=-1.0, le=1.0
    )

    above_upper_pairs_available: int = Field(
        ge=0,
        description=(
            "How many pairs of the night the draw found in the fully similar bucket, the "
            "pool its lightly sampled end drew from."
        ),
    )
    above_upper_pairs_usable: int = Field(
        ge=0,
        description="How many of those had two agreeing readings.",
    )
    above_upper_same_story_estimated: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "How many of the pairs in the fully similar bucket the judge would have called "
            "the same story, estimated by weighting each usable pair by one over its "
            "sampling chance. Empty when no pair there was usable. With a handful of pairs "
            "a night this is an alarm and never moves a threshold."
        ),
    )
    below_lower_pairs_available: int = Field(
        ge=0,
        description=(
            "How many pairs of the night the draw found in the fully dissimilar bucket, the "
            "pool its lightly sampled end drew from."
        ),
    )
    below_lower_pairs_usable: int = Field(
        ge=0,
        description="How many of those had two agreeing readings.",
    )
    below_lower_different_story_estimated: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "How many of the pairs in the fully dissimilar bucket the judge would have "
            "called different stories, estimated the same way. Empty when no pair there was "
            "usable. An alarm, like its twin above."
        ),
    )
    runners_expected: int = Field(
        ge=0, description="How many runners the night was dealt over."
    )
    runners_reported: int = Field(
        ge=0,
        description="How many of those shipped a reading, so a lost runner shows as a gap.",
    )
    pairs_dealt: int = Field(
        ge=0,
        description=(
            "How many pairs the runners that reported were dealt, added up. A runner that "
            "never reported is not in it, so the four endings below still add up to this on "
            "a night that lost one."
        ),
    )
    pairs_valid: int = Field(
        ge=0, description="How many completed pairs had two valid readings."
    )
    pairs_agreed: int = Field(
        ge=0,
        description=(
            "How many valid pairs answered the same way in both orders. A subset of the "
            "valid pairs, never of the pairs dealt."
        ),
    )
    pairs_unreadable: int = Field(
        ge=0,
        description=(
            "How many pairs the window no longer reaches, because the day either item was "
            "published on has aged out."
        ),
    )
    pairs_refused: int = Field(
        ge=0,
        description="How many completed pairs had at least one refused reading.",
    )
    pairs_abandoned: int = Field(
        ge=0,
        description=(
            "How many pairs the runners owned and never reached, because one stopped on its "
            "own deadline."
        ),
    )
    disagreement_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "What share of the valid pairs answered differently in the two orders. Empty "
            "when no pair had two valid readings, because a rate over no rows is not zero."
        ),
    )
    unclear_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "What share of the agreed pairs answered UNCLEAR. Empty when no pair agreed, "
            "for the same reason."
        ),
    )
    decode_seconds_total: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "How long the runners' calls on the drawn pairs took, added up, in seconds. "
            "Empty where no call was made."
        ),
    )
    decode_seconds_slowest_runner: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "How long the slowest runner's calls on the drawn pairs took, in seconds. A "
            "night with an ordinary total and one slow runner is the one that runs out of "
            "clock next, and the total alone hides it."
        ),
    )
    canary_answers: CanaryAnswersText | None = Field(
        default=None,
        description=(
            "What the judge answered on the known-answer pairs, as one compact JSON object "
            "keyed by canary id. Each value lists the answer in file order, the answer "
            "swapped, the two first-token margins, the file-order call's prompt tokens and "
            "the runner index, with null for a reading that was refused or missing. An id "
            "that is absent was never judged. Empty when no known-answer pair was judged."
        ),
    )

    @model_validator(mode="after")
    def _each_bound_reads_coherently(self) -> Self:
        """Both bounds are held to the same rules, each named in its refusal."""
        for side in ("lower", "upper"):
            _the_bound_reads_coherently(
                side,
                _Reading(
                    before=getattr(self, f"{side}_threshold_before"),
                    after=getattr(self, f"{side}_threshold_after"),
                    move=getattr(self, f"{side}_move"),
                    limited_by=getattr(self, f"{side}_move_limited_by"),
                    held_because=getattr(self, f"{side}_held_because"),
                    nights_used=getattr(self, f"{side}_nights_used"),
                    usable_pairs_used=getattr(self, f"{side}_usable_pairs_used"),
                    window_first_date=getattr(self, f"{side}_window_first_date"),
                    intercept=getattr(self, f"{side}_curve_intercept"),
                    steepness=getattr(self, f"{side}_curve_steepness"),
                    estimate=getattr(self, f"{side}_estimate"),
                    gap=getattr(self, f"{side}_gap"),
                    nights_beyond_ignore_range=getattr(
                        self, f"{side}_nights_beyond_ignore_range"
                    ),
                ),
            )
        return self

    @model_validator(mode="after")
    def _the_lower_bound_stays_below_the_upper_one(self) -> Self:
        """A lower column above its upper twin is two sets of columns filed the wrong way round."""
        for what, lower, upper in (
            ("threshold before", self.lower_threshold_before, self.upper_threshold_before),
            ("threshold after", self.lower_threshold_after, self.upper_threshold_after),
            ("share level", self.lower_share_level, self.upper_share_level),
        ):
            if lower >= upper:
                raise ValueError(
                    f"the lower bound's {what} {lower} is not below the upper bound's {upper}"
                )
        return self

    @model_validator(mode="after")
    def _the_two_ends_of_the_range_keep_their_pairs_in_order(self) -> Self:
        """Each lightly sampled end holds its usable pairs, and its estimate follows."""
        _the_end_totals_follow_its_counts(
            "above the upper threshold",
            self.above_upper_pairs_available,
            self.above_upper_pairs_usable,
            self.above_upper_same_story_estimated,
        )
        _the_end_totals_follow_its_counts(
            "below the lower threshold",
            self.below_lower_pairs_available,
            self.below_lower_pairs_usable,
            self.below_lower_different_story_estimated,
        )
        return self

    @model_validator(mode="after")
    def _the_funnel_closes_and_its_rates_follow_its_counts(self) -> Self:
        """Every pair dealt had exactly one ending, and the rates are those counts' ratios.

        The four endings are one funnel written in four columns, and a row where they do not
        add up to what the reporting runners were dealt is a row whose arithmetic nobody can
        reproduce - every rate read off it would be a share of a denominator that means
        nothing. A rate over no rows is empty rather than zero.
        """
        accounted = (
            self.pairs_valid + self.pairs_refused + self.pairs_unreadable + self.pairs_abandoned
        )
        if accounted != self.pairs_dealt:
            raise ValueError(
                f"pairs_dealt is {self.pairs_dealt} and the runners account for {accounted} "
                "(valid, refused, unreadable, abandoned). Every pair dealt has exactly one "
                "of those four endings."
            )
        if self.pairs_agreed > self.pairs_valid:
            raise ValueError(
                f"pairs_agreed is {self.pairs_agreed} over {self.pairs_valid} valid. A pair "
                "agrees only if both of its readings arrived."
            )
        if self.runners_reported > self.runners_expected:
            raise ValueError(
                f"{self.runners_reported} runners reported of {self.runners_expected} expected"
            )
        disagreed = (
            (self.pairs_valid - self.pairs_agreed) / self.pairs_valid if self.pairs_valid else None
        )
        if (self.disagreement_rate is None) != (disagreed is None) or (
            disagreed is not None
            and abs((self.disagreement_rate or 0.0) - disagreed) > RECOMPUTED_TOLERANCE
        ):
            raise ValueError(
                "disagreement_rate is the share of valid pairs that answered differently, "
                "and is empty exactly when no pair had two valid readings"
            )
        if (self.unclear_rate is None) != (self.pairs_agreed == 0):
            raise ValueError("unclear_rate is empty exactly when no pair agreed")
        return self

    @model_validator(mode="after")
    def _a_known_answer_names_a_runner_the_night_expected(self) -> Self:
        """A known-answer pair is dealt to one of the runners the night had, never past them."""
        if self.canary_answers is None:
            return self
        for canary_id, answer in json.loads(self.canary_answers).items():
            if answer[5] >= self.runners_expected:
                raise ValueError(
                    f"canary_answers puts {canary_id} on runner {answer[5]}, and the night "
                    f"expected {self.runners_expected} runners"
                )
        return self
