"""What decides a summary's confidence band, and what does the band say is missing?"""

from __future__ import annotations

import pytest

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.evals.score import band, verdict

pytestmark = pytest.mark.slow


def test_the_bands_come_from_config() -> None:
    tuned = EvaluationConfig(band_high_min=0.9, band_medium_min=0.6)
    assert (
        band(
            0.95,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=tuned,
        )
        is ConfidenceBand.HIGH
    )
    assert (
        band(
            0.7,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=tuned,
        )
        is ConfidenceBand.MEDIUM
    )
    assert (
        band(
            0.5,
            unsupported_numbers=0,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=tuned,
        )
        is ConfidenceBand.LOW
    )


def test_an_invented_number_outvotes_a_perfect_faithfulness_score() -> None:
    """Nothing else in the row can see that defect, so nothing else may outvote it."""
    assert (
        band(
            1.0,
            unsupported_numbers=1,
            lead_coverage=1.0,
            hedge_dropped=False,
            config=EvaluationConfig(),
        )
        is ConfidenceBand.LOW
    )


def test_a_band_below_the_top_says_what_is_missing() -> None:
    """A grade tells a reader an item is worse. A reason tells them what to check.

    Both counterweights were already computed and neither reached the page.
    """
    tuned = EvaluationConfig()

    def reason_for(
        faithfulness: float | None,
        *,
        unsupported_numbers: int = 0,
        lead_coverage: float = 1.0,
        hedge_dropped: bool = False,
    ) -> tuple[ConfidenceBand, BandReason | None]:
        return verdict(
            faithfulness,
            unsupported_numbers=unsupported_numbers,
            lead_coverage=lead_coverage,
            hedge_dropped=hedge_dropped,
            config=tuned,
        )

    assert reason_for(0.95) == (ConfidenceBand.HIGH, None), "nothing to explain"
    assert reason_for(0.95, lead_coverage=0.0) == (ConfidenceBand.MEDIUM, BandReason.LEAD_MISSING)
    assert reason_for(0.95, hedge_dropped=True) == (ConfidenceBand.MEDIUM, BandReason.HEDGE_DROPPED)
    assert reason_for(0.6) == (ConfidenceBand.MEDIUM, BandReason.FAITHFULNESS)
    assert reason_for(0.2) == (ConfidenceBand.LOW, BandReason.FAITHFULNESS)
    assert reason_for(None) == (ConfidenceBand.MEDIUM, BandReason.NOT_SCORED)
    assert reason_for(1.0, unsupported_numbers=1) == (
        ConfidenceBand.LOW,
        BandReason.UNSUPPORTED_NUMBER,
    )

    # Both counterweights fail together on real rows. The reader gets one
    # sentence, and dropped facts are the larger loss.
    assert reason_for(0.95, lead_coverage=0.0, hedge_dropped=True) == (
        ConfidenceBand.MEDIUM,
        BandReason.LEAD_MISSING,
    )


def test_the_band_and_its_reason_are_decided_once() -> None:
    """Two code paths would eventually print a reason that is not why."""
    for faithfulness in (None, 0.2, 0.6, 0.95):
        for coverage in (0.0, 1.0):
            for hedged in (False, True):
                assert band(
                    faithfulness,
                    unsupported_numbers=0,
                    lead_coverage=coverage,
                    hedge_dropped=hedged,
                    config=EvaluationConfig(),
                ) is verdict(
                    faithfulness,
                    unsupported_numbers=0,
                    lead_coverage=coverage,
                    hedge_dropped=hedged,
                    config=EvaluationConfig(),
                ).band
