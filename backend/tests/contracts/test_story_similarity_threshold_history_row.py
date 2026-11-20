"""Does the threshold history row keep each bound's numbers, words and counts telling one story?

Three questions. A bound's move, gap, curve, evidence window and held reason have to agree
with one another, the same way for the lower and the upper bound; the night's counts have to
close and its rates have to follow them; and the two JSON text columns refuse text that is
not compact JSON. A night that judged nothing is still a row.

What none of this settles is whether the numbers are the right ones to follow: nothing writes
this row yet, and the writer's own recomputation proves that.

Every payload here is the committed fixture with a few cells changed, built in memory.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
    ThresholdHoldReason,
    ThresholdMoveLimit,
)

pytestmark = pytest.mark.contract

FIXTURE = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-threshold-history-row"
    / "a-night-that-held-both-thresholds.json"
)

SIDES = ("lower", "upper")

#: Where each bound stood in the fixture, and why it held: the lower gap sat inside the ignore
#: range, and the upper gap sat beyond it for the first night of two.
BEFORE = {"lower": 0.7, "upper": 0.93}
HELD_FOR = {"lower": "within_ignore_range", "upper": "waiting_for_second_night"}

#: The night's own columns when nothing was judged: no model, no readings, no evidence.
NOTHING_JUDGED: dict[str, Any] = {
    "judge_model": None,
    "judge_policy_version": None,
    "above_upper_pairs_available": 0,
    "above_upper_pairs_usable": 0,
    "above_upper_same_story_estimated": None,
    "below_lower_pairs_available": 0,
    "below_lower_pairs_usable": 0,
    "below_lower_different_story_estimated": None,
    "runners_reported": 0,
    "pairs_dealt": 0,
    "pairs_valid": 0,
    "pairs_agreed": 0,
    "pairs_unreadable": 0,
    "pairs_refused": 0,
    "pairs_abandoned": 0,
    "disagreement_rate": None,
    "unclear_rate": None,
    "decode_seconds_total": None,
    "decode_seconds_slowest_runner": None,
    "canary_answers": None,
}


def a_night(**changes: Any) -> dict[str, Any]:
    """The committed night, where both thresholds held, as a payload with some cells changed."""
    payload: dict[str, Any] = json.loads(read_text(FIXTURE))
    return payload | changes


def on(side: str, **changes: Any) -> dict[str, Any]:
    """These per-threshold cells, named for one bound."""
    return {f"{side}_{name}": value for name, value in changes.items()}


def without_a_fit(side: str) -> dict[str, Any]:
    """One bound with no evidence read and no curve fitted, as a night with no data leaves it."""
    return on(
        side,
        nights_used=0,
        usable_pairs_used=0,
        window_first_date=None,
        curve_intercept=None,
        curve_steepness=None,
        estimate=None,
        gap=None,
        nights_beyond_ignore_range=0,
        held_because="not_enough_evidence",
        move=0.0,
        move_limited_by="none",
    )


def a_move(side: str, **changes: Any) -> dict[str, Any]:
    """One bound that moved inward by the narrowing step, with the gap and nights behind it."""
    before = BEFORE[side]
    sign = 1 if side == "lower" else -1
    moved = on(
        side,
        estimate=round(before + sign * 0.0135, 4),
        gap=sign * 0.0135,
        nights_beyond_ignore_range=2,
        held_because="none",
        move_limited_by="narrowing_step",
        move=sign * 0.005,
        threshold_after=round(before + sign * 0.005, 3),
    )
    return moved | on(side, **changes)


def refused(**changes: Any) -> str:
    """The refusal a payload with these cells changed draws, as one string."""
    with pytest.raises(ValidationError) as refusal:
        StorySimilarityThresholdHistoryRow.model_validate(a_night(**changes))
    return str(refusal.value)


def accepted(**changes: Any) -> StorySimilarityThresholdHistoryRow:
    return StorySimilarityThresholdHistoryRow.model_validate(a_night(**changes))


@pytest.mark.parametrize("side", SIDES)
def test_a_held_threshold_has_not_moved(side: str) -> None:
    """A move, a different threshold after, or a limit on a held bound is a row that lies."""
    before = BEFORE[side]
    refusals = {
        f"was held ({HELD_FOR[side]})": on(side, move=0.01, threshold_after=before + 0.01),
        "move is 0.0, and the threshold went from": on(side, threshold_after=before + 0.01),
        "no move was made": on(side, move_limited_by="widening_step"),
    }

    for message, changes in refusals.items():
        assert message in refused(**changes)


@pytest.mark.parametrize("side", SIDES)
def test_a_threshold_that_moved_shows_its_move_or_the_limit_that_cut_it_to_nothing(
    side: str,
) -> None:
    moved = accepted(**a_move(side))
    clamped = accepted(
        **a_move(side, move=0.0, move_limited_by="lowest_allowed", threshold_after=BEFORE[side])
    )

    assert getattr(moved, f"{side}_held_because") is ThresholdHoldReason.NONE
    assert getattr(clamped, f"{side}_move_limited_by") is ThresholdMoveLimit.LOWEST_ALLOWED
    assert "the row carries a move" in refused(
        **a_move(side, move=0.0, move_limited_by="none", threshold_after=BEFORE[side])
    )


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"gap": 0.02}, "gap is 0.02"),
        ({"curve_intercept": None}, "all on the row or all absent"),
        ({"curve_steepness": 0.0}, "greater than 0"),
        ({"curve_steepness": -3.0}, "greater than 0"),
        ({"held_because": "fit_failed"}, "fit failed, so the row carries no curve from it"),
    ],
)
def test_the_curve_is_all_present_or_all_absent_and_a_failed_fit_leaves_none(
    side: str, changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**on(side, **changes))


@pytest.mark.parametrize("side", SIDES)
def test_a_hold_for_a_gap_needs_a_curve_and_a_hold_for_thin_evidence_does_not(side: str) -> None:
    no_curve = on(
        side,
        curve_intercept=None,
        curve_steepness=None,
        estimate=None,
        gap=None,
        nights_beyond_ignore_range=0,
    )

    assert "comes from a gap" in refused(**no_curve)
    for reason in ("not_enough_evidence", "fit_failed"):
        row = accepted(**no_curve | on(side, held_because=reason))
        assert getattr(row, f"{side}_estimate") is None
    thin_but_fitted = accepted(**on(side, held_because="not_enough_evidence"))
    assert getattr(thin_but_fitted, f"{side}_estimate") is not None


@pytest.mark.parametrize("side", SIDES)
@pytest.mark.parametrize(
    "changes", [{"window_first_date": None}, {"nights_used": 0, "usable_pairs_used": 0}]
)
def test_the_evidence_window_names_a_date_exactly_when_something_was_read(
    side: str, changes: dict[str, Any]
) -> None:
    assert "starts on a date exactly when" in refused(**on(side, **changes))
    assert getattr(accepted(**without_a_fit(side)), f"{side}_window_first_date") is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (on("lower", nights_beyond_ignore_range=1), "no night stands beyond it"),
        (on("upper", nights_beyond_ignore_range=0), "at least tonight stands beyond it"),
        (
            without_a_fit("lower") | on("lower", nights_beyond_ignore_range=2),
            "no gap, so no night stands beyond",
        ),
    ],
)
def test_the_nights_beyond_the_ignore_range_follow_the_hold(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"lower_share_level": 0.9, "upper_share_level": 0.05},
        on("upper", threshold_before=0.7, threshold_after=0.7, estimate=0.6895),
    ],
)
def test_the_lower_bound_stays_below_the_upper_one(changes: dict[str, Any]) -> None:
    """Two sets of columns filed the wrong way round are refused rather than read."""
    assert "is not below the upper bound's" in refused(**changes)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pairs_dealt": 151}, "the runners account for 150"),
        ({"pairs_agreed": 148}, "pairs_agreed is 148 over 147 valid"),
        ({"runners_reported": 6}, "6 runners reported of 5 expected"),
        ({"disagreement_rate": 0.5}, "disagreement_rate is the share of valid pairs"),
        ({"unclear_rate": None}, "unclear_rate is empty exactly when no pair agreed"),
        ({"above_upper_pairs_usable": 413}, "only 412 were available"),
        ({"above_upper_same_story_estimated": None}, "empty exactly when no pair there"),
        ({"below_lower_different_story_estimated": 1531.0}, "only 1530 pairs were available"),
        ({"below_lower_pairs_usable": 0}, "empty exactly when no pair there"),
    ],
)
def test_the_night_s_counts_close_and_its_rates_follow_them(
    changes: dict[str, Any], message: str
) -> None:
    assert message in refused(**changes)


def test_a_night_that_lost_a_runner_still_closes_over_the_runners_that_reported() -> None:
    row = accepted(
        runners_reported=4,
        pairs_dealt=120,
        pairs_valid=118,
        pairs_agreed=111,
        pairs_refused=2,
        disagreement_rate=7 / 118,
    )

    assert (row.runners_expected, row.runners_reported) == (5, 4)


def test_a_night_that_judged_nothing_is_still_a_row() -> None:
    """A night with no model and no evidence degrades to a row of nothing, and is not refused."""
    row = accepted(**NOTHING_JUDGED | without_a_fit("lower") | without_a_fit("upper"))

    assert row.judge_model is None and row.pairs_dealt == 0
    assert row.lower_held_because is ThresholdHoldReason.NOT_ENOUGH_EVIDENCE


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "{}",
        '[["NO","NO",0.9,0.9,800,0]]',
        '{"same-1": ["YES","YES",0.98,0.99,812,2]}',
        '{"same-1":["YES","YES",0.98,0.99,812]}',
        '{"same-1":["MAYBE","YES",0.98,0.99,812,2]}',
        '{"same-1":["YES","YES",1.5,0.99,812,2]}',
        '{"same-1":["YES","YES",0.98,0.99,-1,2]}',
        '{"same-1":["YES","YES",0.98,0.99,812,null]}',
        '{"same-1":["YES","YES",0.98,0.99,812,5]}',
        '{"Same One":["YES","YES",0.98,0.99,812,2]}',
        '{"same-1":["YES","YES",0.98,0.99,812,2],"different-1":["NO","NO",0.9,0.9,800,3]}',
    ],
)
def test_canary_answers_are_compact_json_of_six_typed_cells_from_an_expected_runner(
    text: str,
) -> None:
    assert "canary_answers" in refused(canary_answers=text)


def test_a_missing_reading_is_a_null_cell_and_no_canary_is_none() -> None:
    refused_pair = '{"unclear-1":[null,null,null,null,null,1]}'

    assert accepted(canary_answers=refused_pair).canary_answers == refused_pair
    assert accepted(canary_answers=None).canary_answers is None


@pytest.mark.parametrize(
    "text", ["not json", "{}", '{"judges/content-similarity-judge.json": "2026-11-18"}']
)
def test_config_versions_is_one_compact_json_object(text: str) -> None:
    assert "config_versions" in refused(config_versions=text)
