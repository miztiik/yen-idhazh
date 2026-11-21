"""How close were a prior upper curve's probabilities to new answers from this judge?"""

from __future__ import annotations

import logging
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import asdict
from math import fsum
from typing import Final

from pydantic import ValidationError

from idhazh.contracts.base import compact_json, derive_text_digest
from idhazh.contracts.story_similarity_diagnostics import (
    JudgeProbabilityEvidence,
    JudgeProbabilityStatus,
    UpperFitEvidence,
    UpperFitMeaningStamp,
    diagnostic_text,
    read_diagnostic_text,
)
from idhazh.contracts.story_similarity_pair_verdict import (
    SameStoryVerdict,
    StorySimilarityPairVerdict,
)
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.similarity.threshold_curve import Curve
from idhazh.similarity.threshold_evidence import Evidence, MeaningStamp, meaning_stamp
from idhazh.similarity.thresholds_in_force import council_run_order, lookback_days

LOG: Final = logging.getLogger("idhazh")

type _ReadingIdentity = tuple[UpperFitMeaningStamp, float]
type _Prediction = tuple[float, bool]


def _typed_stamp(stamp: MeaningStamp) -> UpperFitMeaningStamp:
    return UpperFitMeaningStamp.model_validate(asdict(stamp))


def upper_fit_text(
    evidence: Evidence,
    stamp: MeaningStamp | None,
    *,
    fitted: bool,
    pair_limit: int,
    date: str,
    run_id: str,
) -> str | None:
    """Retain the exact cohort the fitter saw, or say why its provenance is unknown."""
    if not fitted:
        reason = "no_curve"
    elif evidence.usable_pairs_used > pair_limit:
        reason = "fit_pair_limit"
    elif len(evidence.pair_keys) != evidence.usable_pairs_used:
        reason = "inexact_membership"
    elif len(evidence.judge_temperatures) > 1:
        reason = "mixed_temperature"
    elif stamp is None or None in evidence.judge_temperatures or not evidence.judge_temperatures:
        reason = "missing_reading_identity"
    else:
        temperature = next(iter(evidence.judge_temperatures))
        assert temperature is not None
        try:
            fit = UpperFitEvidence(
                meaning_stamp=_typed_stamp(stamp),
                judge_temperature=temperature,
                pair_keys=tuple(sorted(evidence.pair_keys)),
                low=min(evidence.scores),
                high=max(evidence.scores),
                yes=sum(evidence.answers),
            )
        except ValidationError:
            reason = "invalid_fit_evidence"
        else:
            return diagnostic_text(fit)
    LOG.info("review-thresholds date=%s run=%s upper fit evidence absent: %s", date, run_id, reason)
    return None


def _attempt_reading(
    rows: Sequence[StorySimilarityPairVerdict], *, date: str, run_id: str
) -> _ReadingIdentity | None:
    """Use recorded settings, even on split or refused readings, not their answers."""
    if any((row.date, row.run_id) != (date, run_id) for row in rows):
        LOG.warning(
            "review-thresholds date=%s run=%s probability batch identity mismatch", date, run_id
        )
        return None
    identities = {
        (meaning_stamp(row), row.judge_temperature) for row in rows if row.judge_model is not None
    }
    if len(identities) != 1:
        if identities:
            LOG.info(
                "review-thresholds date=%s run=%s mixed probability reading identities",
                date,
                run_id,
            )
        return None
    stamp, temperature = next(iter(identities))
    if temperature is None:
        return None
    try:
        return _typed_stamp(stamp), temperature
    except ValidationError:
        LOG.info("review-thresholds date=%s run=%s invalid probability reading stamp", date, run_id)
        return None


def _reference_fit(
    history: Sequence[StorySimilarityThresholdHistoryRow],
    reading: _ReadingIdentity,
    *,
    date: str,
    run_id: str,
    within_days: int,
) -> tuple[StorySimilarityThresholdHistoryRow, UpperFitEvidence, Curve] | None:
    first = lookback_days(date, within_days=within_days)[0]
    before = council_run_order(run_id)
    earlier = sorted(
        (row for row in history if first <= row.date < date and row.upper_fit_evidence is not None),
        key=lambda row: (row.date, council_run_order(row.run_id)),
        reverse=True,
    )
    for row in earlier:
        if council_run_order(row.run_id) >= before:
            continue
        text = row.upper_fit_evidence
        intercept, steepness = row.upper_curve_intercept, row.upper_curve_steepness
        if text is None or intercept is None or steepness is None:
            continue
        fit = read_diagnostic_text(text, column="upper_fit_evidence", model=UpperFitEvidence)
        if (fit.meaning_stamp, fit.judge_temperature) == reading:
            return row, fit, Curve(intercept, steepness)
    return None


def _ece(predictions: Sequence[_Prediction], *, bins: int) -> float:
    # Only interior edges: bisect_right sends an edge to its higher bin, including 1 last.
    edges = [index / bins for index in range(1, bins)]
    binned: list[list[_Prediction]] = [[] for _ in range(bins)]
    for chance, yes in predictions:
        binned[bisect_right(edges, chance)].append((chance, yes))
    # The absolute gap between sums is the bin's mean gap times its sample size.
    total_gap = fsum(abs(fsum(p for p, _ in group) - sum(y for _, y in group)) for group in binned)
    return total_gap / len(predictions)


def probability_columns(
    filed_rows: Sequence[StorySimilarityPairVerdict] | None,
    history: Sequence[StorySimilarityThresholdHistoryRow],
    *,
    date: str,
    run_id: str,
    within_days: int,
    bins: int,
) -> dict[str, str | float]:
    """Score one comparable prior fit and a constant YES rate on the same fresh pairs."""
    rows = filed_rows or ()
    reading = _attempt_reading(rows, date=date, run_id=run_id)
    if reading is None:
        return {"judge_probability_status": JudgeProbabilityStatus.NO_REFERENCE_FIT}
    source = _reference_fit(history, reading, date=date, run_id=run_id, within_days=within_days)
    if source is None:
        return {"judge_probability_status": JudgeProbabilityStatus.NO_REFERENCE_FIT}

    row, fit, curve = source
    training = set(fit.pair_keys)
    # The recorded readings have one matching identity; only two valid agreeing calls count.
    predictions = [
        (curve.probability_at(pair.similarity_score), pair.verdict is SameStoryVerdict.YES)
        for pair in rows
        if pair.readings_agree
        and fit.low <= pair.similarity_score <= fit.high
        and pair.pair_key not in training
    ]
    pairs = len(predictions)
    digest = derive_text_digest(
        compact_json(
            {
                "upper_fit_evidence": fit.model_dump(mode="json"),
                "upper_curve_intercept": curve.intercept,
                "upper_curve_steepness": curve.steepness,
            }
        ).removesuffix("\n")
    )
    evaluated = JudgeProbabilityEvidence(
        source_date=row.date,
        source_run_id=row.run_id,
        fit_sha256=digest,
        pairs=pairs,
        yes=sum(yes for _, yes in predictions),
        bins=bins,
    )
    columns: dict[str, str | float] = {
        "judge_probability_evidence": diagnostic_text(evaluated),
    }
    if not pairs:
        return columns | {"judge_probability_status": JudgeProbabilityStatus.NO_ELIGIBLE_PAIRS}

    baseline = fit.yes / len(fit.pair_keys)
    return columns | {
        "judge_probability_status": JudgeProbabilityStatus.MEASURED,
        "judge_probability_brier_score": fsum((p - yes) ** 2 for p, yes in predictions) / pairs,
        "judge_probability_baseline_brier_score": fsum(
            (baseline - yes) ** 2 for _, yes in predictions
        ) / pairs,
        "judge_probability_ece": _ece(predictions, bins=bins),
    }
