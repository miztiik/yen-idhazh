"""Does the fitted curve find the score where the same-story share crosses a level?

The fit is checked against a maximiser that shares nothing with it but the question: a grid
search over the two parameters of a surface written out again here, narrowed ring by ring.
A Newton routine that stopped a step short, or climbed a surface of its own, would disagree
with it.

Every table is built in the test that uses it (CLAUDE.md section 13).
"""

from __future__ import annotations

import json
import math
from typing import Any

import pytest
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.similarity.threshold_curve import (
    Curve,
    fit_pulled_curve,
    pull_centre,
    steepness_by_night,
)

#: A hand-built table of 16 pairs scoring from 0.62 to 0.77 and what the judge called each:
#: mostly NO at the bottom, mostly YES at the top, and mixed in between so that a curve of
#: finite steepness is the answer.
SCORES: tuple[float, ...] = tuple(round(0.62 + 0.01 * step, 2) for step in range(16))
ANSWERS: tuple[int, ...] = (0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1, 1)

NIGHT_FIXTURE = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-threshold-history-row"
    / "a-night-that-held-both-thresholds.json"
)


def a_surface(a: float, b: float, *, centre: float, spread: float) -> float:
    """ln L(a, b) - (b - b0)^2 / (2 sigma^2), written out from the formula and nothing else."""
    total = 0.0
    for score, answer in zip(SCORES, ANSWERS, strict=True):
        z = a + b * score
        total += answer * z - (max(z, 0.0) + math.log1p(math.exp(-abs(z))))
    return total - (b - centre) ** 2 / (2.0 * spread**2)


def brute_force_maximiser(centre: float, spread: float) -> tuple[float, float]:
    """The maximum of the surface found by narrowing a grid, with no derivative in sight.

    The grid is over the curve's height at the mean score and its steepness, which keeps the
    surface's ridge square to the grid: over the intercept and the steepness the ridge runs
    corner to corner, and a grid narrowed around its best cell wanders off it. A coarse grid
    over a wide box, then a finer grid around the best cell, round after round.
    """
    mean_score = sum(SCORES) / len(SCORES)
    h_low, h_high, b_low, b_high = -20.0, 20.0, 0.0, 120.0
    steps = 40
    best = (0.0, 0.0)
    for _ in range(10):
        h_width, b_width = (h_high - h_low) / steps, (b_high - b_low) / steps
        _, best_h, best_b = max(
            (
                a_surface(
                    h_low + i * h_width - (b_low + j * b_width) * mean_score,
                    b_low + j * b_width,
                    centre=centre,
                    spread=spread,
                ),
                h_low + i * h_width,
                b_low + j * b_width,
            )
            for i in range(steps + 1)
            for j in range(steps + 1)
        )
        best = (best_h - best_b * mean_score, best_b)
        h_low, h_high = best_h - 3 * h_width, best_h + 3 * h_width
        b_low, b_high = max(best_b - 3 * b_width, 0.0), best_b + 3 * b_width
    return best


@pytest.mark.parametrize(
    ("centre", "spread"),
    [(24.6, 8.0), (10.0, 8.0), (24.6, 2.0), (40.0, 30.0)],
    ids=["committed pull", "centre below the data", "tight pull", "loose pull"],
)
def test_the_newton_fit_equals_a_brute_force_maximiser_of_the_same_surface(
    centre: float, spread: float
) -> None:
    fitted = fit_pulled_curve(SCORES, ANSWERS, centre=centre, spread=spread)
    searched_a, searched_b = brute_force_maximiser(centre, spread)

    assert fitted is not None
    assert fitted.intercept == pytest.approx(searched_a, abs=1e-4)
    assert fitted.steepness == pytest.approx(searched_b, abs=1e-4)


def test_a_tighter_pull_holds_the_steepness_nearer_its_centre() -> None:
    loose = fit_pulled_curve(SCORES, ANSWERS, centre=60.0, spread=40.0)
    tight = fit_pulled_curve(SCORES, ANSWERS, centre=60.0, spread=0.5)

    assert loose is not None and tight is not None
    assert abs(tight.steepness - 60.0) < abs(loose.steepness - 60.0)
    assert tight.steepness == pytest.approx(60.0, abs=1.0)


def test_the_curve_reaches_a_share_where_its_own_formula_says() -> None:
    curve = Curve(intercept=-17.0, steepness=24.0)

    assert curve.score_at(0.5) == pytest.approx(17.0 / 24.0)
    for share in (0.05, 0.9):
        score = curve.score_at(share)
        assert score is not None
        assert 1.0 / (1.0 + math.exp(-(curve.intercept + curve.steepness * score))) == (
            pytest.approx(share)
        )


def test_a_curve_so_flat_that_no_finite_score_reaches_the_share_gives_no_score() -> None:
    assert Curve(intercept=-1.0, steepness=1e-320).score_at(0.9) is None


@pytest.mark.parametrize("answer", [0, 1], ids=["all NO", "all YES"])
def test_a_window_whose_answers_are_all_alike_has_no_curve(answer: int) -> None:
    """The intercept has no maximum, so the iteration never settles and nothing is claimed."""
    assert fit_pulled_curve(SCORES, [answer] * len(SCORES), centre=24.6, spread=8.0) is None


def test_no_pairs_is_no_curve() -> None:
    assert fit_pulled_curve([], [], centre=24.6, spread=8.0) is None


def test_a_curve_that_falls_with_the_score_is_no_curve() -> None:
    """Higher scores called NO more often is a window that says nothing about a share rising."""
    scores = [round(0.60 + 0.01 * step, 2) for step in range(20)]
    answers = [1] * 10 + [0] * 10

    assert fit_pulled_curve(scores, answers, centre=24.6, spread=8.0) is None


def test_every_ordinary_window_with_both_answers_gets_a_curve() -> None:
    """300 windows of 500 pairs, steepness 15 to 60, and none of them stalls short of its maximum.

    The last useful Newton steps gain less than a rounding step of a surface a few hundred below
    zero, so a line search that insists the surface did not fall halves them to nothing and the
    fifty steps run out. About one window in a hundred did that, and the night would then hold
    for a failed fit that is no fault of the data.
    """
    failed: list[int] = []
    for window in range(300):
        steepness = 15.0 + 5.0 * (window % 10)
        true_point = 0.66 + 0.008 * (window % 11)
        scores = [true_point - 0.06 + 0.12 * (j + 0.5) / 500 for j in range(500)]
        answers = [
            int(
                ((j + 1) * 0.6180339887 + window * 0.3141592654) % 1.0
                < 1.0 / (1.0 + math.exp(-steepness * (s - true_point) + math.log(19.0)))
            )
            for j, s in enumerate(scores)
        ]
        if 0 < sum(answers) < len(answers) and fit_pulled_curve(
            scores, answers, centre=24.6, spread=8.0
        ) is None:
            failed.append(window)

    assert failed == []


def test_a_score_without_an_answer_is_refused() -> None:
    with pytest.raises(ValueError, match="one answer is needed for each score"):
        fit_pulled_curve([0.7, 0.71], [1], centre=24.6, spread=8.0)


def drawn_from(intercept: float, steepness: float, *, count: int) -> tuple[list[float], list[int]]:
    """`count` pairs spread evenly over 0.64 to 0.76, each called YES as the curve says it should.

    A pair is YES when the golden-ratio sequence, which spreads evenly over 0 to 1, falls below
    the curve at its score, so the table matches the curve to within a few pairs and has no
    chance in it.
    """
    scores = [0.64 + 0.12 * (index + 0.5) / count for index in range(count)]
    answers = [
        int((index * 0.6180339887498949) % 1.0 < 1.0 / (1.0 + math.exp(-(intercept + steepness * s))))
        for index, s in enumerate(scores)
    ]
    return scores, answers


def test_a_large_window_settles_and_recovers_the_score_it_was_drawn_around() -> None:
    """600 pairs along a known curve, which is the size of a real night's window.

    The surface is a long narrow ridge here, which is where a step tolerance tighter than
    rounding can resolve would keep a fit that has arrived from ever being called settled.
    """
    intercept, steepness = -17.0, 24.0
    scores, answers = drawn_from(intercept, steepness, count=600)

    fitted = fit_pulled_curve(scores, answers, centre=24.6, spread=8.0)

    assert fitted is not None
    where = fitted.score_at(0.5)
    assert where is not None
    assert where == pytest.approx(-intercept / steepness, abs=0.005)


def test_the_pull_centre_is_the_median_of_the_nights_once_there_are_enough() -> None:
    nights = [20.0, 30.0, 22.0, 28.0, 21.0, 40.0, 24.0]

    assert pull_centre(nights, minimum_nights=7, start=24.6) == 24.0
    assert pull_centre(nights[:6], minimum_nights=7, start=24.6) == 24.6
    assert pull_centre([], minimum_nights=1, start=24.6) == 24.6


def a_night(date: str, *, run: int = 9, **changes: Any) -> StorySimilarityThresholdHistoryRow:
    """The contract's own night that held both thresholds, moved to `date` with cells changed."""
    raw = json.loads(read_text(NIGHT_FIXTURE))
    return StorySimilarityThresholdHistoryRow.model_validate(
        raw | {"date": date, "run_id": f"{date}-{run}"} | changes
    )


def test_one_steepness_a_night_comes_from_the_newest_row_of_a_date_inside_the_window() -> None:
    """A re-run's row replaces its night's, and a night's own row or a later one is no history.

    The lower and the upper threshold read their own columns, and a night whose newest row
    stored no steepness gives none rather than a stale one.
    """
    no_lower_curve: dict[str, Any] = {
        "lower_curve_intercept": None,
        "lower_curve_steepness": None,
        "lower_estimate": None,
        "lower_gap": None,
        "lower_nights_beyond_ignore_range": 0,
        "lower_held_because": "fit_failed",
        "lower_window_first_date": None,
        "lower_nights_used": 0,
        "lower_usable_pairs_used": 0,
    }
    history = [
        a_night("2026-10-01", lower_curve_steepness=99.0, upper_curve_steepness=99.0),
        a_night("2026-11-10", lower_curve_steepness=20.0, upper_curve_steepness=30.0),
        a_night("2026-11-11", run=8, lower_curve_steepness=21.0, upper_curve_steepness=31.0),
        a_night("2026-11-11", run=9, lower_curve_steepness=22.0, upper_curve_steepness=32.0),
        a_night("2026-11-12", upper_curve_steepness=33.0, **no_lower_curve),
        a_night("2026-11-19", lower_curve_steepness=77.0, upper_curve_steepness=77.0),
        a_night("2026-11-20", lower_curve_steepness=88.0, upper_curve_steepness=88.0),
    ]

    lower = steepness_by_night(history, side="lower", night="2026-11-19", window_nights=28)
    upper = steepness_by_night(history, side="upper", night="2026-11-19", window_nights=28)

    assert lower == [20.0, 22.0]
    assert upper == [30.0, 32.0, 33.0]
