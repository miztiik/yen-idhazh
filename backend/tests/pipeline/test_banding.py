"""What decides a summary's confidence band, and what does the band say is missing?"""

from __future__ import annotations

from idhazh.contracts.eval_row import BandReason, ConfidenceBand
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.evals.score import band, verdict


def test_the_bands_come_from_config() -> None:
    tuned = EvaluationConfig(band_high_min=0.9, band_medium_min=0.6)
    assert band(0.9, config=tuned) is ConfidenceBand.HIGH
    assert band(0.899, config=tuned) is ConfidenceBand.MEDIUM
    assert band(0.6, config=tuned) is ConfidenceBand.MEDIUM
    assert band(0.599, config=tuned) is ConfidenceBand.LOW


def test_a_band_below_the_top_says_what_is_missing() -> None:
    """A grade tells a reader an item is worse. A reason tells them what to check."""
    tuned = EvaluationConfig()

    def reason_for(faithfulness: float | None) -> tuple[ConfidenceBand, BandReason | None]:
        return verdict(faithfulness, config=tuned)

    assert reason_for(0.95) == (ConfidenceBand.HIGH, None), "nothing to explain"
    assert reason_for(0.6) == (ConfidenceBand.MEDIUM, BandReason.FAITHFULNESS)
    assert reason_for(0.2) == (ConfidenceBand.LOW, BandReason.FAITHFULNESS)
    assert reason_for(None) == (ConfidenceBand.MEDIUM, BandReason.NOT_SCORED)


def test_fresh_verdicts_only_explain_faithfulness_or_absent_scores() -> None:
    reached = {
        verdict(faithfulness, config=EvaluationConfig()).reason
        for faithfulness in (None, 0.0, 0.2, 0.6, 0.95, 1.0)
    }
    assert reached == {None, BandReason.FAITHFULNESS, BandReason.NOT_SCORED}


def test_the_band_and_its_reason_are_decided_once() -> None:
    """Two code paths would eventually print a reason that is not why."""
    for faithfulness in (None, 0.2, 0.6, 0.95):
        assert band(faithfulness, config=EvaluationConfig()) is verdict(
            faithfulness, config=EvaluationConfig()
        ).band
