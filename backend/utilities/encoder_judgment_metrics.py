"""Calibrate tie-safe thresholds and compare saved scores with paired cluster uncertainty."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from idhazh.contracts.encoder_evaluation import (
    BootstrapAudit,
    EvaluationSettings,
    MetricInterval,
    OperatingPoint,
    RankingMetrics,
)

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


def validate_scores(labels: IntArray, scores: FloatArray) -> None:
    if labels.ndim != 1 or scores.ndim != 1 or len(labels) != len(scores):
        raise ValueError("scores and labels need matching one-dimensional shapes")
    if set(labels.tolist()) != {0, 1}:
        raise ValueError("metrics require both binary classes")
    if not np.isfinite(scores).all():
        raise ValueError("scores must be finite")


def ranking_metrics(labels: IntArray, scores: FloatArray) -> RankingMetrics:
    validate_scores(labels, scores)
    return RankingMetrics(
        average_precision=float(average_precision_score(labels, scores)),
        area_under_curve=float(roc_auc_score(labels, scores)),
    )


def operating_point(
    labels: IntArray, scores: FloatArray, threshold: float | None, reason: str | None = None,
) -> OperatingPoint:
    validate_scores(labels, scores)
    if threshold is None:
        return OperatingPoint(
            threshold=None, precision=None, recall=None,
            tp=None, fp=None, fn=None, tn=None, reason=reason,
        )
    predicted = scores >= threshold
    positive = labels == 1
    tp = int(np.sum(predicted & positive))
    fp = int(np.sum(predicted & ~positive))
    return OperatingPoint(
        threshold=threshold,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / int(np.sum(positive)),
        tp=tp, fp=fp, fn=int(np.sum(~predicted & positive)),
        tn=int(np.sum(~predicted & ~positive)),
        reason=None if tp + fp else "no predicted positives at the fixed calibration threshold",
    )


def calibrate_threshold(labels: IntArray, scores: FloatArray, target: float) -> OperatingPoint:
    """Maximize calibration recall at the target; ties use the lowest complete threshold."""
    validate_scores(labels, scores)
    if not 0 < target <= 1:
        raise ValueError("precision target must be in (0, 1]")
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    reaches = np.flatnonzero((precision[:-1] >= target) & (recall[:-1] > 0))
    if len(reaches) == 0:
        return operating_point(labels, scores, None, "calibration precision target unattainable")
    # sklearn orders thresholds ascending and treats each tied score as one complete block.
    best_recall = max(recall[reaches])
    index = next(int(index) for index in reaches if recall[index] == best_recall)
    return operating_point(labels, scores, float(thresholds[index]))


def paired_bootstrap(
    labels: IntArray,
    scores: Mapping[str, FloatArray],
    components: list[str],
    settings: EvaluationSettings,
) -> tuple[BootstrapAudit, dict[str, MetricInterval], dict[str, MetricInterval]]:
    """Draw the same whole held-out article components for every encoder and reference."""
    if settings.reference not in scores:
        raise ValueError("bootstrap reference is not in the scored encoders")
    for values in scores.values():
        validate_scores(labels, values)
    if len(components) != len(labels):
        raise ValueError("bootstrap components and labels have different lengths")
    groups = sorted(set(components))
    if len(groups) < 2:
        raise ValueError(f"paired bootstrap blocked: {len(groups)} held-out components")
    members = [np.flatnonzero(np.asarray(components) == group) for group in groups]
    rng = np.random.default_rng(settings.bootstrap_seed)
    aps: dict[str, list[float]] = {slug: [] for slug in scores}
    differences: dict[str, list[float]] = {slug: [] for slug in scores}
    one_class = 0
    for _ in range(settings.bootstrap_rounds):
        indices = np.concatenate([
            members[int(index)] for index in rng.integers(0, len(groups), size=len(groups))
        ])
        drawn_labels = labels[indices]
        if len(np.unique(drawn_labels)) < 2:
            one_class += 1
            continue
        draw = {
            slug: float(average_precision_score(drawn_labels, values[indices]))
            for slug, values in scores.items()
        }
        for slug, ap in draw.items():
            aps[slug].append(ap)
            differences[slug].append(ap - draw[settings.reference])
    valid = settings.bootstrap_rounds - one_class

    def interval(values: list[float]) -> MetricInterval:
        if valid < settings.minimum_valid_draws:
            return MetricInterval(
                lower=None, upper=None,
                reason=f"only {valid} valid draws; require {settings.minimum_valid_draws}",
            )
        tail = (1 - settings.interval_level) / 2
        lower, upper = np.quantile(values, [tail, 1 - tail])
        return MetricInterval(lower=float(lower), upper=float(upper), reason=None)

    return (
        BootstrapAudit(
            method="paired held-out component percentile bootstrap",
            rounds=settings.bootstrap_rounds, valid_draws=valid, one_class_draws=one_class,
        ),
        {slug: interval(values) for slug, values in aps.items()},
        {slug: interval(values) for slug, values in differences.items()},
    )
