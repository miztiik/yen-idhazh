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

import logging
import statistics
from collections.abc import Sequence
from math import nextafter
from typing import Any, Final

import pytest
from support.judged_pairs import CONFIG_VERSIONS, a_judged_pair, a_night_of_pairs
from support.threshold_nights import LOOKBACK, RULES, STEADY, a_day, pairs_beside

from idhazh.contracts.knobs.content_similarity_judge import ThresholdsConfig
from idhazh.contracts.story_similarity_diagnostics import (
    JudgeProbabilityEvidence,
    JudgeProbabilityStatus,
    read_diagnostic_text,
)
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
    ThresholdHoldReason,
)
from idhazh.similarity.probability_diagnostics import _ece, probability_columns
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
            for day in evidence_days(date, window_nights=self.rules.effective_max_window_nights)
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


def _fit_batch(
    date: str,
    run_id: str,
    *,
    low: float = 0.89,
    judge_temperature: float = 0.0,
    **cells: Any,
) -> list[StorySimilarityPairVerdict]:
    return a_night_of_pairs(
        [(low, "NO"), (0.95, "UNCLEAR"), (0.965, "YES")],
        date=date,
        run_id=run_id,
        judge_temperature=judge_temperature,
        **cells,
    )


def _fit(
    rows: Sequence[StorySimilarityPairVerdict], *, pair_limit: int | None = 3
) -> StorySimilarityThresholdHistoryRow:
    fitted = build_threshold_row(
        rows[0].date,
        run_id=rows[0].run_id,
        window=rows,
        history=(),
        draw_rows=(),
        readings=(),
        expected_shards=1,
        rules=RULES,
        lookback_days_of_the_draw=LOOKBACK,
        versions=CONFIG_VERSIONS,
        fit_pair_limit=pair_limit,
    )
    assert fitted is not None and fitted.upper_curve_intercept is not None
    return fitted


@pytest.mark.parametrize(
    ("pair_limit", "temperatures", "missing_reason"),
    [
        (3, (0.0, 0.0, 0.0), None),
        (2, (0.0, 0.0, 0.0), "fit_pair_limit"),
        (3, (0.0, 0.2, 0.0), "mixed_temperature"),
        (3, (None, None, None), "missing_reading_identity"),
    ],
    ids=["at the cap", "over cap", "mixed temperatures", "legacy temperature missing"],
)
def test_retaining_exact_membership_neither_truncates_nor_refuses_the_fit(
    pair_limit: int,
    temperatures: tuple[float | None, ...],
    missing_reason: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    batch = _fit_batch("2026-11-19", "2026-11-21-2")
    readings = [
        StorySimilarityPairVerdict.model_validate(row.model_dump() | {"judge_temperature": temp})
        for row, temp in zip(batch, temperatures, strict=True)
    ]
    before = _fit(readings, pair_limit=None)
    with caplog.at_level(logging.INFO, logger="idhazh"):
        after = _fit(readings, pair_limit=pair_limit)
    assert after.model_dump(exclude={"upper_fit_evidence"}) == before.model_dump(
        exclude={"upper_fit_evidence"}
    )
    assert (after.upper_fit_evidence is None) == (missing_reason is not None)
    if missing_reason is not None:
        assert "upper fit evidence absent: " + missing_reason in caplog.text


def test_the_newest_comparable_fit_is_kept_even_when_an_older_one_could_score() -> None:
    date, run_id, prior_day = "2026-11-20", "2026-11-21-20", "2026-11-19"
    older = _fit(_fit_batch("2026-11-18", "2026-11-21-18"))
    lower_run = _fit(_fit_batch(prior_day, "2026-11-21-9"))
    chosen = _fit(_fit_batch(prior_day, "2026-11-21-10", low=0.94))
    same_run = _fit(_fit_batch(prior_day, run_id))
    future_run = _fit(_fit_batch(prior_day, "2026-11-21-21"))
    same_digest = _fit(_fit_batch(date, "2026-11-21-14"))
    different_prompt = _fit(_fit_batch(prior_day, "2026-11-21-19", prompt_digest="c" * 64))
    different_temperature = _fit(
        _fit_batch(prior_day, "2026-11-21-18", judge_temperature=0.2)
    )
    legacy = _fit(_fit_batch(prior_day, "2026-11-21-17"), pair_limit=None)
    match = a_judged_pair(200, score=0.93, date=date, run_id=run_id)

    def score(
        history: Sequence[StorySimilarityThresholdHistoryRow],
        attempt: Sequence[StorySimilarityPairVerdict] | None = (match,),
    ) -> dict[str, str | float]:
        return probability_columns(
            attempt, history, date=date, run_id=run_id, within_days=14, bins=10
        )

    history = [
        different_prompt, older, same_run, same_digest, future_run, lower_run,
        chosen, legacy, different_temperature,
    ]
    assert score([older])["judge_probability_status"] == JudgeProbabilityStatus.MEASURED
    status = score(history)
    assert set(status) == {"judge_probability_status", "judge_probability_evidence"}
    assert status["judge_probability_status"] == JudgeProbabilityStatus.NO_ELIGIBLE_PAIRS
    payload = status["judge_probability_evidence"]
    assert isinstance(payload, str)
    source = read_diagnostic_text(
        payload, column="judge_probability_evidence", model=JudgeProbabilityEvidence
    )
    assert (source.source_date, source.source_run_id, source.pairs, source.yes) == (
        prior_day, "2026-11-21-10", 0, 0
    )
    assert score([_fit(_fit_batch("2026-11-06", "2026-11-07-1"))])[
        "judge_probability_status"
    ] == JudgeProbabilityStatus.MEASURED
    too_old = _fit(_fit_batch("2026-11-05", "2026-11-06-1"))
    unknown = {"judge_probability_status": JudgeProbabilityStatus.NO_REFERENCE_FIT}
    assert score([too_old, legacy, different_prompt, different_temperature]) == unknown
    assert score(history, None) == unknown
    mixed = a_judged_pair(201, score=0.95, date=date, run_id=run_id, judge_temperature=0.2)
    assert score(history, (match, mixed)) == unknown
    split = a_judged_pair(201, score=0.95, date=date, run_id=run_id, answer=("YES", "NO"))
    assert score(history, (split,)) == status  # A split still supplies the reading identity.


def test_ece_groups_an_exact_edge_above_its_predecessor_and_includes_both_endpoints() -> None:
    predictions = [(0.0, False), (nextafter(0.5, 0), False), (0.5, False), (0.75, True), (1.0, True)]
    assert _ece(predictions, bins=2) == pytest.approx((0.5 + 0.25) / 5)


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

    assert widest_out <= RULES.widening_step + 1e-9
    assert widest_out > RULES.narrowing_step
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


def test_build_threshold_row_adapts_lower_and_upper_evidence_windows_independently() -> None:
    """Upper stays at 7 nights when full while lower expands to 10 nights to clear 240 pairs."""
    window: list[StorySimilarityPairVerdict] = []
    for step in range(12):
        day = a_day(step)
        lower_pairs = [
            (round(0.66 + 0.08 * (index + 0.5) / 24, 6), "YES" if index >= 22 else "NO")
            for index in range(24)
        ]
        upper_pairs = [
            (round(0.89 + 0.08 * (index + 0.5) / 40, 6), "YES" if index >= 10 else "NO")
            for index in range(40)
        ]
        window.extend(
            a_night_of_pairs(
                [*lower_pairs, *upper_pairs],
                date=day,
                run_id=f"{day}-9",
                first_index=step * 1000,
            )
        )

    night = a_day(11)
    row = build_threshold_row(
        night,
        run_id=f"{night}-9",
        window=window,
        history=(),
        draw_rows=(),
        readings=(),
        expected_shards=4,
        rules=RULES,
        lookback_days_of_the_draw=LOOKBACK,
        versions=CONFIG_VERSIONS,
    )
    assert row is not None
    assert (row.upper_nights_used, row.upper_usable_pairs_used, row.upper_window_first_date) == (
        7,
        280,
        a_day(5),
    )
    assert (row.lower_nights_used, row.lower_usable_pairs_used, row.lower_window_first_date) == (
        10,
        240,
        a_day(2),
    )
