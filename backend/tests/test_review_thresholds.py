"""Does a night find where each threshold stands, and does the row it files say how?

The nights here are built from pairs that follow a known curve, so what the night should
conclude is known before it runs. They are worked through `build_threshold_row` with the rows
kept in memory, which is the stage's own arithmetic without its reads. The stage itself, against
a ledger built through the real door, is `test_review_thresholds_stage.py`. Nothing walks the
committed ledger (CLAUDE.md section 13).

What none of this can settle is whether the real judge's answers follow a curve below 0.88, or
how many usable pairs the draw really leaves beside each threshold: the first real nights show
both, and the stored `usable_pairs_used` is where.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any, Final

import pytest
from support.judged_pairs import CONFIG_VERSIONS, a_night_of_pairs
from support.threshold_nights import LOOKBACK, RULES, STEADY, a_day, pairs_beside

from idhazh.contracts.knobs.content_similarity_judge import ThresholdsConfig
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
    ThresholdHoldReason,
)
from idhazh.similarity.threshold_evidence import evidence_days
from idhazh.similarity.thresholds_in_force import thresholds_in_force
from idhazh.stages.review_thresholds import build_threshold_row


class Run:
    """A run of nights worked through the night's own arithmetic, rows kept in memory."""

    def __init__(self, rules: ThresholdsConfig = RULES) -> None:
        self.rules = rules
        self.pair_rows: dict[str, list[StorySimilarityPairVerdict]] = {}
        self.history: list[StorySimilarityThresholdHistoryRow] = []

    def night(
        self, step: int, *, shift: float = 0.0, reruns: int = 1, **cells: Any
    ) -> StorySimilarityThresholdHistoryRow:
        """One more night: draw beside the thresholds in force, judge, review, and remember.

        `reruns` of 2 judges the same pairs a second time under another run, which keeps its
        own rows beside the first's, and the review settles the later run.
        """
        date = a_day(step)
        followed = thresholds_in_force(
            self.history,
            night=date,
            within_days=LOOKBACK,
            lower_start=self.rules.lower_start,
            upper_start=self.rules.upper_start,
        )
        pairs = pairs_beside(followed.lower, followed.upper, shift=shift, night=step)
        self.pair_rows[date] = [
            row
            for attempt in range(reruns)
            for row in a_night_of_pairs(
                pairs,
                date=date,
                run_id=f"{date}-{9 + attempt}",
                first_index=step * 1000,
                lower=followed.lower,
                upper=followed.upper,
                **cells,
            )
        ]
        window = [
            row
            for day in evidence_days(date, window_nights=self.rules.window_nights)
            for row in self.pair_rows.get(day, [])
        ]
        row = build_threshold_row(
            date,
            run_id=f"{date}-{9 + reruns - 1}",
            window=window,
            history=self.history,
            draw_rows=[],
            readings=[],
            expected_shards=4,
            rules=self.rules,
            lookback_days_of_the_draw=LOOKBACK,
            versions=CONFIG_VERSIONS,
        )
        assert row is not None
        self.history.append(row)
        return row


def after(rows: Sequence[StorySimilarityThresholdHistoryRow], side: str) -> list[float]:
    """The threshold a side ended each night at."""
    return [getattr(row, f"{side}_threshold_after") for row in rows]


def through_a_shift(shift: float, *, shifted_nights: int = 14) -> list[StorySimilarityThresholdHistoryRow]:
    run = Run()
    return [
        run.night(step, shift=shift if step >= STEADY else 0.0)
        for step in range(STEADY + shifted_nights)
    ]


def test_nights_that_follow_the_starts_hold_both_thresholds_where_they_are() -> None:
    run = Run()
    rows = [run.night(step) for step in range(9)]

    assert all(row.lower_held_because is not ThresholdHoldReason.NONE for row in rows)
    assert all(row.upper_held_because is not ThresholdHoldReason.NONE for row in rows)
    assert after(rows, "lower") == [0.70] * 9
    assert after(rows, "upper") == [0.93] * 9
    last = rows[-1]
    assert (last.lower_nights_used, last.lower_usable_pairs_used) == (7, 280)
    assert last.lower_estimate == pytest.approx(0.70, abs=0.01)
    assert last.upper_estimate == pytest.approx(0.93, abs=0.01)


@pytest.mark.parametrize("shift", [-0.05, 0.05], ids=["the curve falls 0.05", "the curve rises 0.05"])
def test_a_shift_of_0_05_is_first_acted_on_from_the_second_night_to_the_fifth(shift: float) -> None:
    """Never the first night, in either direction at either threshold.

    A gap beyond the ignore range must stand for two nights before a move, so the earliest a
    threshold can move is the second night of the shift. The window still holds six nights of
    the old curve when the shift begins, so the estimate takes a few nights to leave the ignore
    range: on this fixture the four cases first move on nights 2, 3, 4 and 5.
    """
    shifted = through_a_shift(shift)[STEADY:]

    for side in ("lower", "upper"):
        first = next(
            night
            for night, row in enumerate(shifted, start=1)
            if getattr(row, f"{side}_held_because") is ThresholdHoldReason.NONE
        )
        assert 2 <= first <= 5, f"the {side} threshold first moved on night {first} of the shift"
        assert getattr(shifted[first - 1], f"{side}_nights_beyond_ignore_range") >= 2
        assert (
            getattr(shifted[first - 2], f"{side}_held_because")
            is ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT
        )


SHIFTS: Final = [
    pytest.param(-0.05, "lower", "upper", id="the curve falls 0.05"),
    pytest.param(0.05, "upper", "lower", id="the curve rises 0.05"),
]


@pytest.mark.parametrize(("shift", "outward", "inward"), SHIFTS)
def test_no_night_moves_a_threshold_by_more_than_its_step_and_out_uses_the_larger_one(
    shift: float, outward: str, inward: str
) -> None:
    shifted = through_a_shift(shift)[STEADY:]

    widest_out = max(abs(getattr(row, f"{outward}_move")) for row in shifted)
    widest_in = max(abs(getattr(row, f"{inward}_move")) for row in shifted)

    assert widest_out == pytest.approx(RULES.widening_step, abs=1e-9)
    assert widest_in == pytest.approx(RULES.narrowing_step, abs=1e-9)


@pytest.mark.parametrize(("shift", "outward", "inward"), SHIFTS)
def test_a_threshold_follows_a_shift_without_turning_back_and_out_comes_sooner_than_in(
    shift: float, outward: str, inward: str
) -> None:
    """Nights until each threshold is within twice the ignore range of the shifted point.

    The ceilings are measured on this fixture, at 40 pairs a night beside each threshold, and
    are regression ceilings and not a promise about the real judge. Out came in 6 and 7 nights
    and in came in 10 and 9. That is a smaller difference than the steps (0.02 against 0.005)
    suggest because each move out pushes about a third of the older pairs out of the window,
    and the next move waits for the window to refill: out is fast per move and not per night.
    """
    shifted = through_a_shift(shift)[STEADY:]
    truth = {"lower": 0.70 + shift, "upper": 0.93 + shift}

    def nights_until_near(side: str) -> int:
        for night, row in enumerate(shifted, start=1):
            if abs(getattr(row, f"{side}_threshold_after") - truth[side]) <= 2 * RULES.ignore_range + 1e-9:
                return night
        raise AssertionError(f"the {side} threshold never came near the shifted point")

    for side in ("lower", "upper"):
        assert all(getattr(row, f"{side}_move") * shift >= 0.0 for row in shifted)
    assert nights_until_near(outward) <= 9
    assert nights_until_near(inward) <= 12
    assert nights_until_near(outward) < nights_until_near(inward)


def test_a_rerun_of_a_night_counts_each_of_its_pairs_once() -> None:
    once, twice = Run(), Run()
    for step in range(8):
        single = once.night(step)
        doubled = twice.night(step, reruns=2)

    assert doubled.lower_usable_pairs_used == single.lower_usable_pairs_used == 280
    assert doubled.upper_usable_pairs_used == single.upper_usable_pairs_used == 280
    assert doubled.lower_curve_steepness == pytest.approx(single.lower_curve_steepness)


def test_a_change_of_judge_restarts_the_window_and_the_night_says_so() -> None:
    run = Run()
    for step in range(9):
        run.night(step)

    changed = [run.night(step, judge_model="another-model-q4") for step in range(9, 12)]

    assert [row.lower_nights_used for row in changed] == [1, 2, 3]
    assert [row.lower_usable_pairs_used for row in changed] == [40, 80, 120]
    assert changed[0].lower_window_first_date == a_day(9)
    assert changed[0].judge_model == "another-model-q4"


def test_a_window_with_fewer_nights_than_the_setting_says_how_many_it_had() -> None:
    run = Run()
    rows = [run.night(step) for step in range(3)]

    assert [row.lower_nights_used for row in rows] == [1, 2, 3]
    assert rows[-1].lower_window_first_date == a_day(0)


def test_a_night_settled_out_of_order_is_computed_as_if_the_later_night_did_not_exist() -> None:
    """The council settles a repair night after the anchor, and the later row must not reach it."""
    in_order, late = Run(), Run()
    for step in range(11):
        in_order.night(step)
        late.night(step)
    late.night(12)
    expected = in_order.night(11)

    settled_late = late.night(11)

    assert settled_late.model_dump() == expected.model_dump()


def test_the_pull_centre_is_the_start_until_enough_nights_of_steepness_exist() -> None:
    run = Run()
    rows = [run.night(step) for step in range(9)]
    steepness = [
        value for row in rows if (value := row.lower_curve_steepness) is not None
    ]

    assert len(steepness) == 9
    assert [row.lower_pull_centre for row in rows[:7]] == [RULES.pull_start_steepness] * 7
    assert rows[7].lower_pull_centre == statistics.median(steepness[:7])
    assert rows[8].lower_pull_centre == statistics.median(steepness[:8])


def test_a_window_where_every_answer_is_the_same_holds_as_a_failed_fit_and_stores_no_curve() -> None:
    run = Run()
    rows = [run.night(step, shift=0.4) for step in range(8)]

    last = rows[-1]
    assert last.lower_usable_pairs_used >= RULES.minimum_usable_pairs
    assert last.lower_held_because is ThresholdHoldReason.FIT_FAILED
    assert (
        last.lower_curve_intercept,
        last.lower_curve_steepness,
        last.lower_estimate,
        last.lower_gap,
        last.lower_nights_beyond_ignore_range,
    ) == (None, None, None, None, 0)
    assert last.lower_threshold_after == last.lower_threshold_before


def test_a_gap_is_only_a_night_in_a_row_when_the_nights_are_consecutive() -> None:
    """A night with no row breaks the run, so the count starts again and a move waits a night."""
    run = Run()
    for step in range(STEADY):
        run.night(step)
    run.night(STEADY, shift=-0.05)
    run.night(STEADY + 1, shift=-0.05)
    held_back = Run()
    for step in range(STEADY):
        held_back.night(step)
    held_back.night(STEADY, shift=-0.05)
    held_back.history.pop()
    skipped = held_back.night(STEADY + 1, shift=-0.05)

    assert run.history[-1].lower_nights_beyond_ignore_range == 2
    assert skipped.lower_nights_beyond_ignore_range == 1
    assert skipped.lower_held_because is ThresholdHoldReason.WAITING_FOR_SECOND_NIGHT
