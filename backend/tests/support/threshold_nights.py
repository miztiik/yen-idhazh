"""Nights of pairs that follow a curve known in advance, for the tests of the threshold review.

A night's pairs are spread evenly over the thin run beside each threshold, and the judge
answers them the way a logistic curve of known steepness says, so what the review should
conclude from them is known before it runs. The answer to the j-th pair is the fractional part
of a multiple of the golden ratio, which spreads evenly over 0 to 1, so the table follows the
curve with no chance in it and a test can pin what the review finds.
"""

from __future__ import annotations

import math
from datetime import date as date_type
from datetime import timedelta
from typing import Final

from idhazh.content_similarity_judge import settings as judge_settings
from support.paths import CONFIG_DIR

JUDGE: Final = judge_settings.load(CONFIG_DIR)
RULES: Final = JUDGE.thresholds
LOOKBACK: Final = JUDGE.draw.thresholds_lookback_days

#: Steepness of the curve the judge follows, the committed pull's starting steepness.
TRUE_STEEPNESS: Final = 24.6

#: The scores at which the judge's same-story share reaches 5 and 90 percent, before any shift.
TRUE_LOWER_POINT: Final = 0.70
TRUE_UPPER_POINT: Final = 0.93

#: Nights at the starts before a shift begins, so the window is full of the old curve.
STEADY: Final = 6


def a_day(step: int) -> str:
    """The UTC day `step` nights after 2026-11-01."""
    return (date_type(2026, 11, 1) + timedelta(days=step)).isoformat()


def pairs_beside(
    lower: float, upper: float, *, shift: float, night: int, each: int = 40
) -> list[tuple[float, str]]:
    """The pairs a draw takes beside each threshold, answered by a judge whose curve is known.

    `each` pairs spread evenly over the thin run at each threshold: the lower threshold up to
    0.06 above it, the upper one down to 0.06 below it. The judge calls a pair the same story as
    the logistic curve says, crossing 5 percent at the lower true point and 90 percent at the
    upper, and `shift` moves both true points from 0.70 and 0.93.
    """
    pairs: list[tuple[float, str]] = []
    for first, share, true_point in (
        (lower, 0.05, TRUE_LOWER_POINT + shift),
        (upper - 0.06, 0.90, TRUE_UPPER_POINT + shift),
    ):
        level = math.log(share / (1.0 - share))
        for j in range(each):
            score = round(first + 0.06 * (j + 0.5) / each, 6)
            chance = 1.0 / (1.0 + math.exp(-(TRUE_STEEPNESS * (score - true_point) + level)))
            draw = ((j + 1) * 0.6180339887 + night * 0.3141592654) % 1.0
            pairs.append((score, "YES" if draw < chance else "NO"))
    return pairs
