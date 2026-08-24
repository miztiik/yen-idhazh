"""The Row #7 decision rule, as arithmetic rather than as an argument.

Two numbers decide it, and both are in config:

- **The drop.** If the incumbent measures more than `validation_drop_max` below
  what the leaderboard predicted, the leaderboard was not describing our
  pipeline and the other candidates have to be scored too.
- **The margin.** If a challenger beats the incumbent by at least
  `validation_switch_margin` on our own corpus, the pick changes.

A switch is never applied here. It changes a persisted contract and re-goldens
the fixtures, so the rule returns `switch_and_pause` and stops. That pause is
the point of the row.
"""

from __future__ import annotations

from dataclasses import dataclass

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.validation_row import ValidationRow, ValidationVerdict


@dataclass(frozen=True, slots=True)
class Measurement:
    """One model, scored both ways: theirs and ours."""

    model_id: str
    leaderboard_hhem: float
    measured_hhem: float
    articles: int


@dataclass(frozen=True, slots=True)
class Decision:
    verdict: ValidationVerdict
    detail: str
    winner: str


def _shortfall(measurement: Measurement) -> float:
    """How far below its own leaderboard number the model landed here."""
    return measurement.leaderboard_hhem - measurement.measured_hhem


def decide(
    incumbent: Measurement,
    challengers: list[Measurement],
    *,
    evaluation: EvaluationConfig,
) -> Decision:
    """Confirm the pick, ask for more scores, or stop for a human."""
    if incumbent.articles < evaluation.validation_articles:
        return Decision(
            verdict=ValidationVerdict.RESCORE_CANDIDATES,
            detail=(
                f"the incumbent was scored on {incumbent.articles} articles, "
                f"below the {evaluation.validation_articles} this gate requires"
            ),
            winner=incumbent.model_id,
        )

    scored = [c for c in challengers if c.articles >= evaluation.validation_articles]
    best = max(scored, key=lambda c: c.measured_hhem, default=None)

    if best is not None and best.measured_hhem - incumbent.measured_hhem >= (
        evaluation.validation_switch_margin
    ):
        gain = best.measured_hhem - incumbent.measured_hhem
        return Decision(
            verdict=ValidationVerdict.SWITCH_AND_PAUSE,
            detail=(
                f"{best.model_id} scores {gain:.3f} above {incumbent.model_id} on our own "
                f"corpus, at or past the {evaluation.validation_switch_margin} margin - "
                "switching changes a persisted contract, so this pauses for sign-off"
            ),
            winner=best.model_id,
        )

    drop = _shortfall(incumbent)
    if drop > evaluation.validation_drop_max:
        return Decision(
            verdict=ValidationVerdict.RESCORE_CANDIDATES,
            detail=(
                f"{incumbent.model_id} measured {drop:.3f} below its leaderboard number, "
                f"past the {evaluation.validation_drop_max} the rule allows - the ranking "
                "was not describing this prompt, this extraction and this corpus"
            ),
            winner=incumbent.model_id,
        )

    return Decision(
        verdict=ValidationVerdict.CONFIRMED,
        detail=(
            f"{incumbent.model_id} measured {incumbent.measured_hhem:.3f} against a "
            f"leaderboard {incumbent.leaderboard_hhem:.3f}, and no challenger cleared the "
            f"{evaluation.validation_switch_margin} margin"
        ),
        winner=incumbent.model_id,
    )


def to_rows(
    incumbent: Measurement,
    challengers: list[Measurement],
    decision: Decision,
    *,
    measured_on: str,
    commit_sha: str,
    runner: str,
) -> list[ValidationRow]:
    """The ledger the gate leaves behind. Every candidate, not just the winner.

    A ledger holding only the winner cannot answer the question someone asks six
    months later: was the runner-up close?
    """
    return [
        ValidationRow(
            version=ValidationRow.schema_version(),
            model_id=measurement.model_id,
            is_incumbent=measurement.model_id == incumbent.model_id,
            selected=measurement.model_id == decision.winner,
            leaderboard_hhem=measurement.leaderboard_hhem,
            measured_hhem=measurement.measured_hhem,
            articles=measurement.articles,
            measured_on=measured_on,
            commit_sha=commit_sha,
            runner=runner,
            verdict=decision.verdict,
            detail=decision.detail,
        )
        for measurement in [incumbent, *challengers]
    ]
