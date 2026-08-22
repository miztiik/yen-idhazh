"""The Row #7 decision rule.

The rule carries numbers rather than adjectives, so it can be tested before the
measurement it will judge exists. That is the point: when the runner finally
reports, the gate runs rather than being argued about.
"""

from __future__ import annotations

import pytest

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.validation_row import ValidationRow, ValidationVerdict
from idhazh.evals.validation import Measurement, decide, to_rows

CONFIG = EvaluationConfig()
QWEN8B = "qwen3-8b-q4-k-m"


def incumbent(measured: float = 0.72, leaderboard: float = 0.75, articles: int = 20) -> Measurement:
    return Measurement(
        model_id=QWEN8B,
        leaderboard_hhem=leaderboard,
        measured_hhem=measured,
        articles=articles,
    )


def challenger(model_id: str, measured: float, articles: int = 20) -> Measurement:
    return Measurement(
        model_id=model_id, leaderboard_hhem=0.74, measured_hhem=measured, articles=articles
    )


class TestTheRule:
    def test_a_pick_that_holds_up_is_confirmed(self) -> None:
        result = decide(incumbent(), [], evaluation=CONFIG)
        assert result.verdict is ValidationVerdict.CONFIRMED
        assert result.winner == QWEN8B

    def test_a_small_shortfall_is_not_a_problem(self) -> None:
        """0.09 below the leaderboard is inside the rule, and inside means confirmed."""
        result = decide(incumbent(measured=0.66, leaderboard=0.75), [], evaluation=CONFIG)
        assert result.verdict is ValidationVerdict.CONFIRMED

    def test_a_shortfall_past_the_threshold_rescores_the_others(self) -> None:
        result = decide(incumbent(measured=0.60, leaderboard=0.75), [], evaluation=CONFIG)
        assert result.verdict is ValidationVerdict.RESCORE_CANDIDATES
        assert "not describing this prompt" in result.detail

    def test_exactly_at_the_threshold_is_not_past_it(self) -> None:
        result = decide(incumbent(measured=0.65, leaderboard=0.75), [], evaluation=CONFIG)
        assert result.verdict is ValidationVerdict.CONFIRMED

    def test_a_clearly_better_challenger_pauses_for_sign_off(self) -> None:
        result = decide(
            incumbent(measured=0.70), [challenger("gemma3-12b", 0.78)], evaluation=CONFIG
        )
        assert result.verdict is ValidationVerdict.SWITCH_AND_PAUSE
        assert result.winner == "gemma3-12b"
        assert "pauses for sign-off" in result.detail

    def test_a_challenger_exactly_at_the_margin_still_switches(self) -> None:
        result = decide(
            incumbent(measured=0.70), [challenger("gemma3-12b", 0.75)], evaluation=CONFIG
        )
        assert result.verdict is ValidationVerdict.SWITCH_AND_PAUSE

    def test_a_challenger_inside_the_margin_changes_nothing(self) -> None:
        """Better is not enough. A model swap re-goldens every fixture."""
        result = decide(
            incumbent(measured=0.70), [challenger("gemma3-12b", 0.74)], evaluation=CONFIG
        )
        assert result.verdict is ValidationVerdict.CONFIRMED
        assert result.winner == QWEN8B

    def test_the_best_challenger_wins_not_the_first(self) -> None:
        result = decide(
            incumbent(measured=0.70),
            [challenger("a", 0.76), challenger("b", 0.81), challenger("c", 0.77)],
            evaluation=CONFIG,
        )
        assert result.winner == "b"

    def test_an_undersampled_challenger_is_ignored(self) -> None:
        """A mean over three articles is not a mean over twenty."""
        result = decide(
            incumbent(measured=0.70),
            [challenger("gemma3-12b", 0.90, articles=3)],
            evaluation=CONFIG,
        )
        assert result.verdict is ValidationVerdict.CONFIRMED

    def test_an_undersampled_incumbent_asks_for_more_scoring(self) -> None:
        result = decide(incumbent(articles=5), [], evaluation=CONFIG)
        assert result.verdict is ValidationVerdict.RESCORE_CANDIDATES
        assert "below the 20" in result.detail

    def test_a_switch_outranks_a_shortfall(self) -> None:
        """Both conditions fire. Having a better model already settles it."""
        result = decide(
            incumbent(measured=0.55, leaderboard=0.75),
            [challenger("gemma3-12b", 0.80)],
            evaluation=CONFIG,
        )
        assert result.verdict is ValidationVerdict.SWITCH_AND_PAUSE

    def test_the_thresholds_come_from_config(self) -> None:
        loose = EvaluationConfig(validation_switch_margin=0.20)
        result = decide(
            incumbent(measured=0.70), [challenger("gemma3-12b", 0.78)], evaluation=loose
        )
        assert result.verdict is ValidationVerdict.CONFIRMED


class TestTheLedger:
    def _rows(self, decision_input: list[Measurement]) -> list[ValidationRow]:
        base = incumbent(measured=0.70)
        decision = decide(base, decision_input, evaluation=CONFIG)
        return to_rows(
            base,
            decision_input,
            decision,
            measured_on="2026-08-22",
            commit_sha="a" * 40,
            runner="ubuntu-latest",
        )

    def test_every_candidate_is_recorded_not_only_the_winner(self) -> None:
        rows = self._rows([challenger("a", 0.71), challenger("b", 0.69)])
        assert [row.model_id for row in rows] == [QWEN8B, "a", "b"]

    def test_exactly_one_row_is_the_incumbent(self) -> None:
        rows = self._rows([challenger("a", 0.71)])
        assert sum(1 for row in rows if row.is_incumbent) == 1

    def test_exactly_one_row_is_selected(self) -> None:
        rows = self._rows([challenger("gemma3-12b", 0.80)])
        assert sum(1 for row in rows if row.selected) == 1

    def test_a_switch_selects_the_challenger(self) -> None:
        rows = self._rows([challenger("gemma3-12b", 0.80)])
        selected = next(row for row in rows if row.selected)
        assert selected.model_id == "gemma3-12b"
        assert not selected.is_incumbent

    def test_the_verdict_is_the_same_on_every_row(self) -> None:
        rows = self._rows([challenger("gemma3-12b", 0.80)])
        assert len({row.verdict for row in rows}) == 1

    def test_a_switch_that_selects_the_incumbent_is_refused(self) -> None:
        with pytest.raises(ValueError):
            ValidationRow(
                version=ValidationRow.schema_version(),
                model_id=QWEN8B,
                is_incumbent=True,
                selected=True,
                leaderboard_hhem=0.75,
                measured_hhem=0.70,
                articles=20,
                measured_on="2026-08-22",
                commit_sha="a" * 40,
                runner="ubuntu-latest",
                verdict=ValidationVerdict.SWITCH_AND_PAUSE,
                detail="incoherent",
            )

    def test_a_row_round_trips(self) -> None:
        rows = self._rows([challenger("a", 0.71)])
        assert ValidationRow.from_json(rows[0].to_json()) == rows[0]
