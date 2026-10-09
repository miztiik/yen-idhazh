"""Render saved proxy statistics with standard terms and explicit measurement limits."""

from __future__ import annotations

from typing import Any


def render_readings(
    readings: list[dict[str, Any]], *, archive_articles: int, batch_articles: int,
) -> str:
    measured = [row for row in readings if row.get("state") == "measured"]
    measured.sort(key=lambda row: -row["separation"])
    ordered = measured + [row for row in readings if row.get("state") != "measured"]
    lines = [
        "# Encoder readings",
        "",
        "**This is a title-derived proxy, not a labeled event test.** Use "
        "[the model-judged evaluation](../README.md#complete-model-judged-comparison) "
        "for AP, precision, recall, calibrated thresholds and paired uncertainty.",
        "",
        "Saved rows are not re-encoded. Their individual UTC timestamps, task settings, "
        "model IDs and recorded host/thread information remain in `encoders.json`. "
        "Costs came from separate runner hosts, not controlled same-silicon trials.",
        "",
        "## Ranking and encoding cost",
        "",
        "Proxy ROC AUC compares title-derived positive and negative pairs only. "
        "Sorting this table by it does not establish the best event encoder.",
        "",
        "| Encoder | Vector dimensions | Parameters | Proxy ROC AUC | Throughput "
        "(summaries/s) | Estimated archive time (min) | Estimated batch time (min) | "
        "Peak process memory (GiB) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ordered:
        if row.get("state") != "measured":
            progress = f"{row.get('articles_done', 0)}/{row.get('articles_to_encode', 0)}"
            lines.append(
                f"| `{row['slug']}` | | | {row.get('state', 'did not report')} "
                f"{progress} | | | | |"
            )
            continue

        def shown(value: object, places: int) -> str:
            return f"{value:.{places}f}" if isinstance(value, (int, float)) else ""

        lines.append(
            f"| `{row['slug']}` | {row['numbers_an_article']} | "
            f"{row['parameters_millions']}M | {shown(row['separation'], 4)} | "
            f"{shown(row.get('articles_a_second'), 1)} | "
            f"{shown(row.get('minutes_for_whole_archive'), 1)} | "
            f"{shown(row.get('minutes_for_one_day'), 2)} | "
            f"{shown(row.get('peak_memory_gb'), 2)} |"
        )
    lines += [
        "",
        f"The saved time estimates use {archive_articles:,} archive articles and "
        f"{batch_articles:,} articles per batch. They are throughput projections, "
        "not measured full-archive or batch executions.",
        "",
        "## Descriptive cosine statistics",
        "",
        "Positive/negative here means the title-derived proxy label. Middle-overlap "
        "and same-outlet pairs have no event labels in this proxy. A larger mean "
        "difference or exceedance rate does not demonstrate better accuracy, "
        "precision, recall, over-merging or missed events.",
        "",
        "| Encoder | Positive mean cosine | Negative mean cosine | Mean cosine "
        "difference | Middle-overlap mean cosine | Middle-overlap fraction above "
        "class-mean midpoint | Same-outlet mean cosine | Same-outlet fraction above "
        "class-mean midpoint |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    def statistic(row: dict[str, Any], name: str) -> str:
        value = row.get(name)
        return f"{value:.3f}" if isinstance(value, (int, float)) else ""

    for row in measured:
        lines.append(
            f"| `{row['slug']}` | {statistic(row, 'same_mean')} | "
            f"{statistic(row, 'different_mean')} | {statistic(row, 'spread')} | "
            f"{statistic(row, 'ambiguous_mean')} | {statistic(row, 'ambiguous_lean')} | "
            f"{statistic(row, 'related_mean')} | {statistic(row, 'related_lean')} |"
        )
    lines += [
        "",
        "## Metric glossary",
        "",
        "| Term | Meaning and measurement |",
        "| --- | --- |",
        "| Cosine similarity | Dot product divided by the vector norms; for unit "
        "vectors it is their dot product. A score, not a probability. |",
        "| ROC AUC | Area under the receiver operating characteristic curve; "
        "probability a positive pair outscores a negative pair, with half credit "
        "for ties. 0.5 is chance-level, 1 is perfect ordering. |",
        "| Average precision (AP) | Precision averaged over increases in recall "
        "as the threshold is lowered. A ranking measure, not accuracy. Reported "
        "on model-judged pairs, not calculated from unlabeled middle pairs. |",
        "| Precision | TP / (TP + FP): the fraction of predicted matches labeled "
        "same. Undefined when there are no predicted matches. |",
        "| Recall | TP / (TP + FN): the fraction of labeled same pairs found. |",
        "| TP / FP / FN / TN | Correct match / incorrect match / missed match / "
        "correct non-match, according to the stated labels. |",
        "| Mean cosine difference | Positive mean minus negative mean. Descriptive "
        "only; not standard deviation, Cohen's d or a scale-free quality score. |",
        "| Class-mean midpoint | (positive mean + negative mean) / 2. A diagnostic "
        "reference, not a calibrated or production decision threshold. |",
        "| Fraction above midpoint | Number of unlabeled scores strictly above "
        "that encoder's midpoint, divided by the group size. A descriptive "
        "exceedance rate, not a standard selection metric. |",
        "| Precision target | Constraint used when choosing a threshold on "
        "calibration data. It is not guaranteed on held-out or production data. |",
        "| Confidence interval | A range from resampling; the judged comparison "
        "uses paired article-component draws. It does not measure label errors. |",
        "| Throughput | Encoded summaries divided by encoding seconds, on the "
        "recorded host. |",
        "| Peak process memory | Process high-water resident memory, converted "
        "to GiB by the runner utility; excludes other processes. |",
        "",
        "Historical JSON keys remain unchanged: `separation` = proxy ROC AUC; "
        "`spread` = mean cosine difference; `same_mean`/`different_mean` = positive/"
        "negative means; `ambiguous_mean`/`related_mean` = middle-overlap/same-outlet "
        "means; `ambiguous_lean`/`related_lean` = the two descriptive fractions above "
        "the class-mean midpoint. These aliases preserve old measured files; "
        "they do not introduce new scientific measures.",
        "",
        "Definitions: [scikit-learn ROC AUC]"
        "(https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html), "
        "[average precision]"
        "(https://scikit-learn.org/stable/modules/generated/"
        "sklearn.metrics.average_precision_score.html), "
        "[precision and recall]"
        "(https://scikit-learn.org/stable/modules/model_evaluation.html#precision-recall-f-measure-metrics).",
        "",
    ]
    return "\n".join(lines)
