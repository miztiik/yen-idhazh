"""How much did the full eligible score mix change against comparable earlier nights?"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from itertools import accumulate, pairwise
from math import fsum, log
from typing import Final

from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityDiagnosticsConfig
from idhazh.contracts.story_similarity_diagnostics import (
    ScoreDriftBaseline,
    ScoreDriftSource,
    ScoreDriftStatus,
    ScorePoolHistogram,
    diagnostic_text,
    read_diagnostic_text,
)
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.similarity.stamps import ScorerStamp
from idhazh.similarity.thresholds_in_force import council_run_order, lookback_days

# Change when the scoring or eligible canonical-pair membership rule changes, not when the
# judge, draw cuts, or publication floor moves.
SCORE_POOL_RECIPE: Final = "eligible-canonical-cross-outlet-pairs-v1"


def pool_recipe_stamp(
    scorer: ScorerStamp,
    *,
    encoder_revision: str,
    group_identical_titles: bool,
    window_hours: float,
) -> str:
    """Identify the ruler and the pool, independently of what the judge sampled."""
    return derive_text_digest(
        canonical_json(
            {
                "recipe": SCORE_POOL_RECIPE,
                "scorer_model": scorer.scorer_model,
                "encoder_revision": encoder_revision,
                "cosine_weight": scorer.cosine_weight,
                "group_identical_titles": group_identical_titles,
                "window_hours": window_hours,
            }
        )
    )


def score_pool_histogram(
    scores: Iterable[float], *, bins: int, stamp: str
) -> ScorePoolHistogram:
    """Count each unit-range score once; an interior edge belongs to the higher bin."""
    edges = tuple((2 * index - bins) / bins for index in range(bins + 1))
    interiors = edges[1:-1]
    counts = [0] * bins
    for score in scores:
        counts[bisect_right(interiors, score)] += 1
    return ScorePoolHistogram(stamp=stamp, edges=edges, counts=tuple(counts))


def _baseline(
    target: ScorePoolHistogram,
    history: Sequence[StorySimilarityThresholdHistoryRow],
    *,
    date: str,
    run_id: str,
    rules: ContentSimilarityDiagnosticsConfig,
) -> tuple[ScoreDriftBaseline, list[int]]:
    first = lookback_days(date, within_days=rules.score_baseline_lookback_days)[0]
    before = council_run_order(run_id)
    newest: dict[str, tuple[tuple[str, int], StorySimilarityThresholdHistoryRow]] = {}
    for row in history:
        if not first <= row.date < date:
            continue
        order = council_run_order(row.run_id)
        held = newest.get(row.date)
        if order < before and (held is None or order >= held[0]):
            newest[row.date] = order, row

    sources: list[ScoreDriftSource] = []
    counts = [0] * len(target.counts)
    # Choose a run for each date first. A newer incompatible run cannot be replaced by
    # an older compatible one; a repair made by this Council run is not prior evidence.
    for day in sorted(newest, reverse=True):
        row = newest[day][1]
        text = row.score_pool_histogram
        if text is None:
            continue
        pool = read_diagnostic_text(text, column="score_pool_histogram", model=ScorePoolHistogram)
        if pool.stamp != target.stamp or pool.edges != target.edges or not any(pool.counts):
            continue
        for index, count in enumerate(pool.counts):
            counts[index] += count
        sources.append(
            ScoreDriftSource(date=day, run_id=row.run_id, histogram_sha256=derive_text_digest(text))
        )
        if len(sources) == rules.score_baseline_days:
            break
    return (
        ScoreDriftBaseline(
            sources=tuple(sources),
            required_days=rules.score_baseline_days,
            share_floor=rules.score_psi_share_floor,
        ),
        counts,
    )


def _smoothed_shares(counts: Sequence[int], *, total: int, floor: float) -> list[float]:
    floored = [max(count / total, floor) for count in counts]
    scale = fsum(floored)
    return [share / scale for share in floored]


def _distances(
    target: ScorePoolHistogram, baseline: Sequence[int], *, floor: float
) -> tuple[float, float, float]:
    """PSI uses smoothed shares; both binned distances use the unsmoothed counts."""
    target_total, baseline_total = sum(target.counts), sum(baseline)
    target_shares = _smoothed_shares(target.counts, total=target_total, floor=floor)
    baseline_shares = _smoothed_shares(baseline, total=baseline_total, floor=floor)
    psi = fsum(
        (p - q) * (log(p) - log(q)) for p, q in zip(target_shares, baseline_shares, strict=True)
    )

    # Subtract the cumulative shares before dividing so equal shares give exactly zero.
    gaps = [
        abs(p * baseline_total - q * target_total) / (target_total * baseline_total)
        for p, q in zip(accumulate(target.counts), accumulate(baseline), strict=True)
    ]
    midpoints = [(left + right) / 2 for left, right in pairwise(target.edges)]
    wasserstein = fsum(
        gap * (right - left)
        for gap, (left, right) in zip(gaps[:-1], pairwise(midpoints), strict=True)
    )
    return psi, wasserstein, max(gaps)


def drift_columns(
    pool: ScorePoolHistogram | None,
    history: Sequence[StorySimilarityThresholdHistoryRow],
    *,
    date: str,
    run_id: str,
    rules: ContentSimilarityDiagnosticsConfig,
) -> dict[str, str | float]:
    """File the histogram and exact baseline evidence, but no distances without both pools."""
    if pool is None:
        return {"score_drift_status": ScoreDriftStatus.NO_HISTOGRAM}
    columns: dict[str, str | float] = {"score_pool_histogram": diagnostic_text(pool)}
    if not any(pool.counts):
        return columns | {"score_drift_status": ScoreDriftStatus.EMPTY_POOL}

    baseline, counts = _baseline(pool, history, date=date, run_id=run_id, rules=rules)
    columns["score_drift_baseline"] = diagnostic_text(baseline)
    if len(baseline.sources) < baseline.required_days:
        return columns | {"score_drift_status": ScoreDriftStatus.INSUFFICIENT_BASELINE}
    psi, wasserstein, ks = _distances(pool, counts, floor=baseline.share_floor)
    return columns | {
        "score_drift_status": ScoreDriftStatus.MEASURED,
        "score_psi": psi,
        "score_wasserstein_distance": wasserstein,
        "score_ks_distance": ks,
    }
