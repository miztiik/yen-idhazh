"""Does a night move a threshold by the steps it is allowed, and hold it for the reason it has?

Pure arithmetic over numbers named in each test, with the committed settings as the base.
Every word of the two closed vocabularies is reached here, so a word the code can no longer
say is a test that fails.

What this cannot settle is whether the committed steps follow a real shift in time: the
nights in `test_review_thresholds.py` run the whole night, and the first real nights show
the rest.
"""

from __future__ import annotations

import pytest
from support.paths import CONFIG_DIR

from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.story_similarity_threshold_history_row import (
    ThresholdHoldReason,
    ThresholdMoveLimit,
)
from idhazh.similarity.threshold_move import (
    PreviousNight,
    ThresholdMove,
    decide_move,
    nights_beyond_ignore_range,
)

SETTINGS = judge_settings.load(CONFIG_DIR).thresholds

#: Enough usable pairs to act on, and the one fewer that is not.
ENOUGH = SETTINGS.minimum_usable_pairs
THIN = SETTINGS.minimum_usable_pairs - 1

#: Last night saw the same gap beyond the ignore range, so tonight's is the second in a row.
SECOND_NIGHT_OF_A_FALL = PreviousNight(gap=-0.03, nights_beyond_ignore_range=1)
SECOND_NIGHT_OF_A_RISE = PreviousNight(gap=0.03, nights_beyond_ignore_range=1)


def lower(
    *,
    before: float = 0.70,
    gap: float | None = -0.03,
    usable: int = ENOUGH,
    previous: PreviousNight | None = SECOND_NIGHT_OF_A_FALL,
    other: float = 0.93,
) -> ThresholdMove:
    """The lower threshold on a night whose estimate is `gap` away from `before`."""
    return decide_move(
        "lower",
        before=before,
        estimate=None if gap is None else before + gap,
        usable_pairs_used=usable,
        previous=previous,
        nearest_other=other,
        settings=SETTINGS,
    )


def upper(
    *,
    before: float = 0.93,
    gap: float | None = 0.03,
    usable: int = ENOUGH,
    previous: PreviousNight | None = SECOND_NIGHT_OF_A_RISE,
    other: float = 0.70,
) -> ThresholdMove:
    """The upper threshold on a night whose estimate is `gap` away from `before`."""
    return decide_move(
        "upper",
        before=before,
        estimate=None if gap is None else before + gap,
        usable_pairs_used=usable,
        previous=previous,
        nearest_other=other,
        settings=SETTINGS,
    )


# --- why a threshold stays where it is ---------------------------------------------------


@pytest.mark.parametrize(
    ("night", "reason"),
    [
        (lower(usable=THIN), ThresholdHoldReason.NOT_ENOUGH_EVIDENCE),
        (lower(gap=None), ThresholdHoldReason.FIT_FAILED),
        (lower(gap=-0.005), ThresholdHoldReason.WITHIN_IGNORE_RANGE),
        (lower(previous=None), ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT),
        (lower(), ThresholdHoldReason.NONE),
    ],
    ids=["thin evidence", "failed fit", "within the ignore range", "first night", "moves"],
)
def test_every_reason_a_threshold_is_held_is_reached_and_a_held_threshold_stays_put(
    night: ThresholdMove, reason: ThresholdHoldReason
) -> None:
    assert night.held_because is reason
    if reason is not ThresholdHoldReason.NONE:
        assert (night.move, night.threshold_after, night.move_limited_by) == (
            0.0,
            0.70,
            ThresholdMoveLimit.NONE,
        )
    else:
        assert night.move != 0.0


def test_the_reasons_are_tried_in_order_so_thin_evidence_hides_a_failed_fit_and_a_small_gap() -> None:
    assert lower(usable=THIN, gap=None).held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    assert lower(usable=THIN, gap=-0.005).held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE
    assert lower(gap=-0.005, previous=None).held_because is ThresholdHoldReason.WITHIN_IGNORE_RANGE


def test_a_threshold_held_for_thin_evidence_still_stores_its_estimate_and_its_gap() -> None:
    held = lower(usable=THIN, gap=-0.03)

    assert held.estimate == pytest.approx(0.67)
    assert held.gap == pytest.approx(-0.03)
    assert held.nights_beyond_ignore_range == 2


def test_a_failed_fit_stores_no_estimate_and_no_gap() -> None:
    held = lower(gap=None)

    assert (held.estimate, held.gap, held.nights_beyond_ignore_range) == (None, None, 0)


def test_a_threshold_outside_its_limits_is_held_where_it_stands_to_the_last_digit() -> None:
    """A limit is applied to a move and never to a night that makes none."""
    held = lower(before=0.45, gap=-0.005)

    assert (held.held_because, held.threshold_after) == (ThresholdHoldReason.WITHIN_IGNORE_RANGE, 0.45)


# --- how many nights in a row -------------------------------------------------------------


@pytest.mark.parametrize(
    ("gap", "previous", "expected"),
    [
        (None, None, 0),
        (None, PreviousNight(-0.03, 3), 0),
        (0.01, PreviousNight(0.03, 3), 0),
        (-0.005, None, 0),
        (0.03, None, 1),
        (0.03, PreviousNight(None, 0), 1),
        (0.03, PreviousNight(0.003, 0), 1),
        (0.03, PreviousNight(0.03, 1), 2),
        (0.03, PreviousNight(0.04, 4), 5),
        (0.03, PreviousNight(-0.03, 3), 1),
        (-0.03, PreviousNight(0.03, 3), 1),
    ],
    ids=[
        "no gap", "no gap after a run", "within the range", "small and first", "first night",
        "after a night with no gap", "after a gap inside the range", "second night",
        "fifth night", "direction turned over", "direction turned back",
    ],
)
def test_nights_in_a_row_count_the_gap_beyond_the_range_in_one_direction(
    gap: float | None, previous: PreviousNight | None, expected: int
) -> None:
    assert nights_beyond_ignore_range(gap, previous, ignore_range=0.01) == expected


def test_a_move_does_not_reset_the_count() -> None:
    """The gap is measured from the new threshold, and a gap still beyond the range goes on counting."""
    night = lower(gap=-0.03, previous=PreviousNight(-0.04, 2))

    assert night.held_because is ThresholdHoldReason.NONE
    assert night.nights_beyond_ignore_range == 3


# --- the step a move is allowed ----------------------------------------------------------


@pytest.mark.parametrize(
    ("side", "gap", "step"),
    [
        ("lower", -0.03, 0.02),
        ("lower", 0.03, 0.01),
        ("upper", 0.03, 0.02),
        ("upper", -0.03, 0.01),
    ],
    ids=["lower out", "lower in", "upper out", "upper in"],
)
def test_out_is_fast_and_in_is_slow_for_both_thresholds(side: str, gap: float, step: float) -> None:
    """The lower threshold falls by up to the widening step and rises by up to the narrowing step."""
    previous = PreviousNight(gap=gap, nights_beyond_ignore_range=1)
    night = (
        lower(gap=gap, previous=previous) if side == "lower" else upper(gap=gap, previous=previous)
    )

    assert abs(night.move) == pytest.approx(step)
    assert (night.move > 0) == (gap > 0)
    assert night.move_limited_by is (
        ThresholdMoveLimit.WIDENING_STEP if step == 0.02 else ThresholdMoveLimit.NARROWING_STEP
    )


def test_a_gap_smaller_than_its_step_is_taken_whole_and_limited_by_nothing() -> None:
    night = lower(gap=-0.015)

    assert night.move == pytest.approx(-0.015)
    assert night.move_limited_by is ThresholdMoveLimit.NONE
    assert night.threshold_after == pytest.approx(0.685)


@pytest.mark.parametrize(
    ("side", "gap"),
    [("lower", -0.10), ("lower", 0.10), ("upper", 0.10), ("upper", -0.10)],
    ids=["lower out", "lower in", "upper out", "upper in"],
)
def test_a_far_gap_takes_the_far_gap_step_in_either_direction(side: str, gap: float) -> None:
    previous = PreviousNight(gap=gap, nights_beyond_ignore_range=1)
    night = lower(gap=gap, previous=previous) if side == "lower" else upper(gap=gap, previous=previous)

    assert night.move == pytest.approx(0.02 if gap > 0 else -0.02)
    assert night.move_limited_by is ThresholdMoveLimit.FAR_GAP_STEP


def test_the_far_gap_still_waits_for_its_second_night() -> None:
    """A far gap changes the size of the step and not the confirmation."""
    assert lower(gap=-0.10, previous=None).held_because is ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT


def test_a_gap_just_inside_the_far_gap_is_still_a_near_gap_and_just_beyond_it_is_far() -> None:
    assert lower(gap=-0.039).move_limited_by is ThresholdMoveLimit.WIDENING_STEP
    assert lower(gap=-0.041).move_limited_by is ThresholdMoveLimit.FAR_GAP_STEP


# --- the limits of the range --------------------------------------------------------------


def test_the_lower_threshold_stops_at_its_lowest_allowed_score() -> None:
    night = lower(before=0.51, gap=-0.05)

    assert night.threshold_after == pytest.approx(0.50)
    assert night.move == pytest.approx(-0.01)
    assert night.move_limited_by is ThresholdMoveLimit.LOWEST_ALLOWED


def test_the_upper_threshold_stops_at_its_highest_allowed_score() -> None:
    night = upper(before=0.98, gap=0.05, other=0.80)

    assert night.threshold_after == pytest.approx(0.99)
    assert night.move == pytest.approx(0.01)
    assert night.move_limited_by is ThresholdMoveLimit.HIGHEST_ALLOWED


def test_a_move_a_limit_cuts_to_nothing_is_a_move_with_its_limit_named() -> None:
    night = lower(before=0.50, gap=-0.03)

    assert (night.held_because, night.move, night.threshold_after) == (
        ThresholdHoldReason.NONE,
        0.0,
        0.50,
    )
    assert night.move_limited_by is ThresholdMoveLimit.LOWEST_ALLOWED


def test_a_limit_that_moved_under_a_threshold_cuts_a_move_to_nothing_and_never_pushes_it_back() -> None:
    """The lowest allowed score was raised to 0.50 while the lower threshold stood at 0.45.

    A limit shortens a move and does not lengthen or turn one round, so the threshold does
    not jump to the limit: it cannot fall further, and it can still rise by a step.
    """
    further_out = lower(before=0.45, gap=-0.03)
    in_a_little = lower(before=0.45, gap=0.03, previous=SECOND_NIGHT_OF_A_RISE)

    assert (further_out.move, further_out.threshold_after) == (0.0, 0.45)
    assert further_out.move_limited_by is ThresholdMoveLimit.LOWEST_ALLOWED
    assert in_a_little.move == pytest.approx(SETTINGS.narrowing_step)
    assert in_a_little.move_limited_by is ThresholdMoveLimit.NARROWING_STEP


def test_a_range_narrower_than_the_smallest_gap_never_has_an_inward_move_turned_outward() -> None:
    """The smallest gap was raised to 0.12 while the thresholds stood 0.09 apart."""
    night = lower(before=0.70, gap=0.05, other=0.79, previous=SECOND_NIGHT_OF_A_RISE)

    assert (night.move, night.threshold_after) == (0.0, 0.70)
    assert night.move_limited_by is ThresholdMoveLimit.SMALLEST_GAP


def test_the_lower_threshold_stops_the_smallest_gap_short_of_the_upper_one() -> None:
    night = lower(before=0.808, gap=0.05, other=0.93, previous=SECOND_NIGHT_OF_A_RISE)

    assert night.threshold_after == pytest.approx(0.81)
    assert night.move_limited_by is ThresholdMoveLimit.SMALLEST_GAP


def test_the_upper_threshold_stops_the_smallest_gap_beyond_the_lower_one() -> None:
    night = upper(before=0.922, gap=-0.05, other=0.80, previous=SECOND_NIGHT_OF_A_FALL)

    assert night.threshold_after == pytest.approx(0.92)
    assert night.move_limited_by is ThresholdMoveLimit.SMALLEST_GAP


def test_two_thresholds_narrowing_together_never_pass_the_smallest_gap() -> None:
    """The lower one is limited by where the upper one stands, then the upper one by where it ends.

    At exactly the smallest gap both want to come in, and each would otherwise take its step
    from the other's old place and leave them a step too close.
    """
    first = lower(before=0.80, gap=0.05, other=0.92, previous=SECOND_NIGHT_OF_A_RISE)
    second = upper(before=0.92, gap=-0.05, other=first.threshold_after, previous=SECOND_NIGHT_OF_A_FALL)

    assert second.threshold_after - first.threshold_after >= SETTINGS.smallest_gap - 1e-9
    assert (first.move_limited_by, second.move_limited_by) == (
        ThresholdMoveLimit.SMALLEST_GAP,
        ThresholdMoveLimit.SMALLEST_GAP,
    )


def test_a_move_out_frees_the_other_threshold_to_come_in_by_as_much() -> None:
    first = lower(before=0.80, gap=-0.03)
    second = upper(before=0.92, gap=-0.03, other=first.threshold_after, previous=SECOND_NIGHT_OF_A_FALL)

    assert first.threshold_after == pytest.approx(0.78)
    assert second.threshold_after == pytest.approx(0.91)
    assert second.move_limited_by is ThresholdMoveLimit.NARROWING_STEP


def test_every_word_of_the_move_vocabulary_is_reached_by_the_cases_above() -> None:
    reached = {
        lower(gap=-0.015).move_limited_by,
        lower(gap=-0.03).move_limited_by,
        lower(gap=0.03, previous=SECOND_NIGHT_OF_A_RISE).move_limited_by,
        lower(gap=-0.10).move_limited_by,
        lower(before=0.51, gap=-0.05).move_limited_by,
        upper(before=0.98, gap=0.05, other=0.80).move_limited_by,
        lower(before=0.808, gap=0.05, previous=SECOND_NIGHT_OF_A_RISE).move_limited_by,
    }

    assert reached == set(ThresholdMoveLimit)
