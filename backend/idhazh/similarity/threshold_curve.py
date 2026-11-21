"""Where does the same-story share cross a level, read off one threshold's evidence?

The share of pairs the judge calls the same story rises with the similarity score, and
this module fits that rise as a logistic curve,

    P(same story | score s) = 1 / (1 + exp(-(a + b * s)))

where `a` is the intercept and `b` the steepness. The fit maximises the log-likelihood of
the answers less a pull on the steepness, `(b - b0)^2 / (2 * sigma^2)`: `b0` is where the
steepness has recently sat and `sigma` how loosely it is held there. Nothing pulls the
intercept, so the curve is free to shift while its slope stays steady, which is the move the
evidence has to be able to show.

**The fit is unweighted.** How many pairs the draw took at a score depends on the score alone,
so it changes how much evidence there is at a score and not what share the evidence shows.
Weights would hand the few pairs from the lightly sampled ends the loudest voice in a fit
about the scores beside a threshold.

**The curve is two parameters and a concave surface, so Newton's method is the whole of it.**
Each step is the Newton step, halved until the surface does not fall. A window whose pairs
all got one answer has no maximum in the intercept: the curve keeps sliding away and the
iteration never settles. That is reported as no curve rather than as a curve that has not
yet been found, because nothing here can tell a fit that will not settle from one that
needs more steps.

Pure arithmetic: no file, no config, no clock. The caller names the pull and what the data
is.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta
from statistics import median
from typing import Final

from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.similarity.threshold_evidence import Side

#: The most Newton steps a fit takes. A concave surface of two parameters settles in well
#: under fifteen on any data that has a maximum, so a fit still moving after fifty has none.
MAX_NEWTON_STEPS: Final = 50

#: A fit is settled when its largest parameter step is below a millionth. Newton's method
#: roughly squares its error each step, so the answer is then exact to far more digits than a
#: score is ever read to. It is not a billionth, because the surface is a long narrow ridge
#: (a high intercept goes with a steep slope) and along it rounding alone keeps the step near a
#: billionth, so a tighter bound can be never met by a fit that has long since arrived.
SETTLED_STEP: Final = 1e-6

#: How many times one Newton step is halved looking for a step that does not lower the
#: surface. Near the maximum the surface is flat to rounding, so a step that cannot be made
#: to rise by then is a step the arithmetic cannot see.
MAX_HALVINGS: Final = 40

#: How far below the surface's height a step may land and still be taken, as a share of the
#: height (at least one). The last useful steps gain less than one rounding step of a
#: surface that sits a few hundred below zero, so a test of "did not fall" refuses them and
#: the fit halves to nothing on a window that has a maximum. A trillionth of the height is far
#: below any gain that moves the answer.
HEIGHT_NOISE: Final = 1e-12


@dataclass(frozen=True, slots=True)
class Curve:
    """A fitted logistic curve: the intercept `a` and the steepness `b`, with `b` above zero."""

    intercept: float
    steepness: float

    def probability_at(self, score: float) -> float:
        """The fitted probability of a YES at this score."""
        return _sigmoid(self.intercept + self.steepness * score)

    def score_at(self, share: float) -> float | None:
        """The score where this curve reaches `share`, or none when no finite score does.

        `(ln(p / (1 - p)) - a) / b`. A curve this flat that the answer leaves floating point
        is one the next night could not use, so it is no answer.
        """
        score = (math.log(share / (1.0 - share)) - self.intercept) / self.steepness
        return score if math.isfinite(score) else None


def pull_centre(
    steepness_by_night: Sequence[float], *, minimum_nights: int, start: float
) -> float:
    """The steepness the fit is pulled towards: the median of recent nights, else the start.

    With fewer than `minimum_nights` nights of history the median is a handful of numbers
    the fit itself made, so it is not yet a better guess than the configured start.
    """
    if len(steepness_by_night) < minimum_nights:
        return start
    return median(steepness_by_night)


def steepness_by_night(
    history: Sequence[StorySimilarityThresholdHistoryRow],
    *,
    side: Side,
    night: str,
    window_nights: int,
) -> list[float]:
    """The steepness one threshold's fit stored on each of the nights before `night`.

    **Guardrail #12 declaration.** The fixed-size input is `history`, the rows of the
    `window_nights` days before the night, which the caller read by naming those days.

    One value a night: the newest row of a date, because two runs of one night are one
    night of history and not two. A night whose newest row stored no steepness - the fit
    failed, or the evidence was too thin to fit - adds none, so the median is over nights
    that gave one.
    """
    first = (date_type.fromisoformat(night) - timedelta(days=window_nights)).isoformat()
    newest: dict[str, StorySimilarityThresholdHistoryRow] = {}
    for row in history:
        if first <= row.date < night:
            newest[row.date] = row
    values: list[float] = []
    for day in sorted(newest):
        steepness = getattr(newest[day], f"{side}_curve_steepness")
        if steepness is not None:
            values.append(steepness)
    return values


def _sigmoid(z: float) -> float:
    """1 / (1 + exp(-z)) without overflowing for a large z of either sign."""
    if z >= 0.0:
        return 1.0 / (1.0 + math.exp(-z))
    smaller = math.exp(z)
    return smaller / (1.0 + smaller)


def _softplus(z: float) -> float:
    """ln(1 + exp(z)) without overflowing for a large z."""
    return max(z, 0.0) + math.log1p(math.exp(-abs(z)))


def _surface(
    a: float,
    b: float,
    scores: Sequence[float],
    answers: Sequence[int],
    *,
    centre: float,
    spread: float,
) -> float:
    """The log-likelihood of the answers under the curve, less the pull on its steepness."""
    total = 0.0
    for score, answer in zip(scores, answers, strict=True):
        z = a + b * score
        total += answer * z - _softplus(z)
    return total - (b - centre) ** 2 / (2.0 * spread**2)


def fit_pulled_curve(
    scores: Sequence[float],
    answers: Sequence[int],
    *,
    centre: float,
    spread: float,
) -> Curve | None:
    """The curve that maximises the pulled log-likelihood, or none when no curve settles.

    `answers` is 1 for a pair the judge called the same story and 0 for any other answer,
    one for each score. None comes back for no data, for a window whose answers are all
    alike, for a fit still moving after the last step, and for a steepness that is not
    above zero: a curve that does not rise says nothing about where a share is crossed.

    The start is the curve through the data's own mean at the pull centre's steepness, so
    it depends on the data and on nothing a threshold decides.
    """
    if len(scores) != len(answers):
        raise ValueError("one answer is needed for each score")
    if not scores:
        return None
    pull = 1.0 / spread**2
    mean_score = math.fsum(scores) / len(scores)
    mean_answer = min(max(math.fsum(answers) / len(answers), 0.01), 0.99)
    a, b = math.log(mean_answer / (1.0 - mean_answer)) - centre * mean_score, centre
    height = _surface(a, b, scores, answers, centre=centre, spread=spread)

    for _ in range(MAX_NEWTON_STEPS):
        slope_a = slope_b = weight = weight_score = weight_square = 0.0
        for score, answer in zip(scores, answers, strict=True):
            chance = _sigmoid(a + b * score)
            miss = answer - chance
            curvature = chance * (1.0 - chance)
            slope_a += miss
            slope_b += miss * score
            weight += curvature
            weight_score += curvature * score
            weight_square += curvature * score * score
        slope_b -= (b - centre) * pull
        weight_square += pull
        determinant = weight * weight_square - weight_score * weight_score
        if not determinant > 0.0:
            return None
        step_a = (weight_square * slope_a - weight_score * slope_b) / determinant
        step_b = (weight * slope_b - weight_score * slope_a) / determinant
        if max(abs(step_a), abs(step_b)) < SETTLED_STEP:
            a, b = a + step_a, b + step_b
            return Curve(a, b) if b > 0.0 and math.isfinite(a) and math.isfinite(b) else None
        scale = 1.0
        for _ in range(MAX_HALVINGS):
            raised = _surface(
                a + scale * step_a,
                b + scale * step_b,
                scores,
                answers,
                centre=centre,
                spread=spread,
            )
            if raised >= height - HEIGHT_NOISE * max(1.0, abs(height)):
                break
            scale /= 2.0
        else:
            return None
        a, b, height = a + scale * step_a, b + scale * step_b, raised
    return None
