"""What does one night do to one threshold, given where the curve says it should sit?

The curve gives an estimate, the score where the same-story share reaches the threshold's
level, and the gap is the estimate less where the threshold stood. A night acts on a gap only
when it is beyond the ignore range, has stood for the required number of nights in a row in
one direction, and rests on enough pairs. Otherwise the threshold is held, and the night says
why in one word.

**The move is the gap, cut to a step.** Out is fast and in is slow: the lower threshold falls
by up to the widening step and rises by up to the narrowing step, and the upper threshold
the other way round, because a threshold sitting too far inside the doubtful range leaves
wrong answers in a bucket the draw barely checks. A gap beyond the far gap takes the far gap
step in either direction, so a bad start is found in a few nights.

**Three limits of the range itself come after the step, and a limit only ever shortens a move.**
The lower threshold stops at its lowest allowed score, the upper at its highest, and neither
comes closer to the other than the smallest gap. A threshold that already stands outside a
limit, because a setting changed under it, is not pushed back by the limit: it simply does not
move that way, and the move is cut to nothing. The smallest gap is what keeps tomorrow's draw
drawable, so it is applied in sequence: the lower threshold is limited by where the upper one
stands now, and the upper one by where the lower one now ends up, which gives the lower
threshold first claim on the room between them. `move_limited_by` names the last limit that
changed the move, and a limit that changed nothing is not named.

**A held threshold is never cut.** It keeps the score it started from, to the last digit,
and its estimate is still stored.

Pure arithmetic over numbers the caller names: no file, no config file, no clock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from idhazh.contracts.knobs.content_similarity_judge import ThresholdsConfig
from idhazh.contracts.story_similarity_threshold_history_row import (
    ThresholdHoldReason,
    ThresholdMoveLimit,
)
from idhazh.similarity.threshold_evidence import Side


@dataclass(frozen=True, slots=True)
class PreviousNight:
    """What the previous night's row said about this threshold's gap."""

    gap: float | None
    nights_beyond_ignore_range: int


@dataclass(frozen=True, slots=True)
class ThresholdMove:
    """What a night concluded for one threshold: the gap, how long it has stood, and the move."""

    estimate: float | None
    gap: float | None
    nights_beyond_ignore_range: int
    move: float
    move_limited_by: ThresholdMoveLimit
    held_because: ThresholdHoldReason
    threshold_after: float


def nights_beyond_ignore_range(
    gap: float | None, previous: PreviousNight | None, *, ignore_range: float
) -> int:
    """How many nights in a row, tonight included, the gap has been beyond the ignore range.

    Zero when there is no gap or it is within the range. Otherwise one more than the previous
    night's count when that night's gap was beyond the range in the same direction, and one
    when it was not. A move does not reset the count: after a move the gap is measured from
    the new threshold, and a gap still beyond the range in the same direction is still a
    night in a row.
    """
    if gap is None or abs(gap) <= ignore_range:
        return 0
    if (
        previous is not None
        and previous.gap is not None
        and previous.nights_beyond_ignore_range >= 1
        and (previous.gap > 0) == (gap > 0)
    ):
        return previous.nights_beyond_ignore_range + 1
    return 1


def _why_held(
    *,
    usable_pairs_used: int,
    gap: float | None,
    nights: int,
    settings: ThresholdsConfig,
) -> ThresholdHoldReason:
    """The first reason, in the order they are tried, that the threshold stays where it is."""
    if usable_pairs_used < settings.minimum_usable_pairs:
        return ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    if gap is None:
        return ThresholdHoldReason.FIT_FAILED
    if abs(gap) <= settings.ignore_range:
        return ThresholdHoldReason.WITHIN_IGNORE_RANGE
    if nights < settings.nights_running_required:
        return ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT
    return ThresholdHoldReason.NONE


def _the_score_after_the_move(
    side: Side,
    *,
    before: float,
    gap: float,
    nearest_other: float,
    settings: ThresholdsConfig,
) -> tuple[float, ThresholdMoveLimit]:
    """Where the threshold lands, and the last limit that changed the move.

    `nearest_other` is where the other threshold stands for the smallest-gap limit: the
    upper threshold's start for the lower one, and the lower threshold's end for the upper
    one.
    """
    outward = gap < 0 if side == "lower" else gap > 0
    if abs(gap) > settings.far_gap:
        step, step_limit = settings.far_gap_step, ThresholdMoveLimit.FAR_GAP_STEP
    elif outward:
        step, step_limit = settings.widening_step, ThresholdMoveLimit.WIDENING_STEP
    else:
        step, step_limit = settings.narrowing_step, ThresholdMoveLimit.NARROWING_STEP

    landed, limited_by = before + gap, ThresholdMoveLimit.NONE
    if abs(gap) > step:
        landed, limited_by = before + math.copysign(step, gap), step_limit

    # A limit is a floor on a move down and a ceiling on a move up, and it never sits on the far
    # side of where the threshold already stands, so it can shorten a move and cannot lengthen
    # or turn one round.
    if gap < 0:
        floor, floor_limit = (
            (settings.lowest_lower_threshold, ThresholdMoveLimit.LOWEST_ALLOWED)
            if side == "lower"
            else (nearest_other + settings.smallest_gap, ThresholdMoveLimit.SMALLEST_GAP)
        )
        if landed < min(before, floor):
            return min(before, floor), floor_limit
    else:
        ceiling, ceiling_limit = (
            (nearest_other - settings.smallest_gap, ThresholdMoveLimit.SMALLEST_GAP)
            if side == "lower"
            else (settings.highest_upper_threshold, ThresholdMoveLimit.HIGHEST_ALLOWED)
        )
        if landed > max(before, ceiling):
            return max(before, ceiling), ceiling_limit
    return landed, limited_by


def decide_move(
    side: Side,
    *,
    before: float,
    estimate: float | None,
    usable_pairs_used: int,
    previous: PreviousNight | None,
    nearest_other: float,
    settings: ThresholdsConfig,
) -> ThresholdMove:
    """What tonight does to one threshold.

    `estimate` is none when no curve was fitted or none settled. `usable_pairs_used` is the
    evidence the estimate rests on, which decides whether a night may act on it at all.
    `previous` is the previous night's reading of this threshold, none on the first night.
    """
    gap = None if estimate is None else estimate - before
    nights = nights_beyond_ignore_range(gap, previous, ignore_range=settings.ignore_range)
    held_because = _why_held(
        usable_pairs_used=usable_pairs_used, gap=gap, nights=nights, settings=settings
    )
    if held_because is not ThresholdHoldReason.NONE or gap is None:
        return ThresholdMove(
            estimate=estimate,
            gap=gap,
            nights_beyond_ignore_range=nights,
            move=0.0,
            move_limited_by=ThresholdMoveLimit.NONE,
            held_because=held_because,
            threshold_after=before,
        )
    after, limited_by = _the_score_after_the_move(
        side, before=before, gap=gap, nearest_other=nearest_other, settings=settings
    )
    return ThresholdMove(
        estimate=estimate,
        gap=gap,
        nights_beyond_ignore_range=nights,
        move=after - before,
        move_limited_by=limited_by,
        held_because=ThresholdHoldReason.NONE,
        threshold_after=after,
    )
