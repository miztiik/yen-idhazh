# Encoder readings

**This is a title-derived proxy, not a labeled event test.** Use [the model-judged evaluation](../README.md#complete-model-judged-comparison) for AP, precision, recall, calibrated thresholds and paired uncertainty.

Saved rows are not re-encoded. Their individual UTC timestamps, task settings, model IDs and recorded host/thread information remain in `encoders.json`. Costs came from separate runner hosts, not controlled same-silicon trials.

## Ranking and encoding cost

Proxy ROC AUC compares title-derived positive and negative pairs only. Sorting this table by it does not establish the best event encoder.

| Encoder | Vector dimensions | Parameters | Proxy ROC AUC | Throughput (summaries/s) | Estimated archive time (min) | Estimated batch time (min) | Peak process memory (GiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `jina-v5-nano` | 768 | 212M | 0.9961 | 3.5 | 72.6 | 4.80 | 1.91 |
| `gte-small` | 384 | 33M | 0.9944 | 90.3 | 2.8 | 0.18 | 1.14 |
| `gte-base` | 768 | 109M | 0.9943 | 1.2 | 202.9 | 13.43 | 0.97 |
| `minilm-l6` | 384 | 22M | 0.9925 | 28.6 | 8.8 | 0.58 | 0.87 |
| `gte-modernbert` | 768 | 149M | 0.9915 | 0.6 | 400.1 | 26.47 | 1.08 |
| `embeddinggemma-two` | 768 | 270M | 0.9905 | 3.0 | 85.3 | 5.64 | 3.30 |
| `bge-base` | 768 | 109M | 0.9905 | 5.1 | 49.6 | 3.28 | 1.48 |

The saved time estimates use 15,115 archive articles and 1,000 articles per batch. They are throughput projections, not measured full-archive or batch executions.

## Descriptive cosine statistics

Positive/negative here means the title-derived proxy label. Middle-overlap and same-outlet pairs have no event labels in this proxy. A larger mean difference or exceedance rate does not demonstrate better accuracy, precision, recall, over-merging or missed events.

| Encoder | Positive mean cosine | Negative mean cosine | Mean cosine difference | Middle-overlap mean cosine | Middle-overlap fraction above class-mean midpoint | Same-outlet mean cosine | Same-outlet fraction above class-mean midpoint |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `jina-v5-nano` | 0.886 | 0.537 | 0.349 | 0.740 | 0.593 | 0.881 | 0.982 |
| `gte-small` | 0.934 | 0.738 | 0.196 | 0.844 | 0.539 | 0.931 | 0.971 |
| `gte-base` | 0.929 | 0.724 | 0.205 | 0.834 | 0.535 | 0.925 | 0.961 |
| `minilm-l6` | 0.760 | 0.102 | 0.658 | 0.462 | 0.540 | 0.746 | 0.971 |
| `gte-modernbert` | 0.859 | 0.475 | 0.384 | 0.687 | 0.557 | 0.852 | 0.963 |
| `embeddinggemma-two` | 0.917 | 0.763 | 0.154 | 0.848 | 0.546 | 0.919 | 0.986 |
| `bge-base` | 0.841 | 0.457 | 0.384 | 0.666 | 0.537 | 0.838 | 0.973 |

## Metric glossary

| Term | Meaning and measurement |
| --- | --- |
| Cosine similarity | Dot product divided by the vector norms; for unit vectors it is their dot product. A score, not a probability. |
| ROC AUC | Area under the receiver operating characteristic curve; probability a positive pair outscores a negative pair, with half credit for ties. 0.5 is chance-level, 1 is perfect ordering. |
| Average precision (AP) | Precision averaged over increases in recall as the threshold is lowered. A ranking measure, not accuracy. Reported on model-judged pairs, not calculated from unlabeled middle pairs. |
| Precision | TP / (TP + FP): the fraction of predicted matches labeled same. Undefined when there are no predicted matches. |
| Recall | TP / (TP + FN): the fraction of labeled same pairs found. |
| TP / FP / FN / TN | Correct match / incorrect match / missed match / correct non-match, according to the stated labels. |
| Mean cosine difference | Positive mean minus negative mean. Descriptive only; not standard deviation, Cohen's d or a scale-free quality score. |
| Class-mean midpoint | (positive mean + negative mean) / 2. A diagnostic reference, not a calibrated or production decision threshold. |
| Fraction above midpoint | Number of unlabeled scores strictly above that encoder's midpoint, divided by the group size. A descriptive exceedance rate, not a standard selection metric. |
| Precision target | Constraint used when choosing a threshold on calibration data. It is not guaranteed on held-out or production data. |
| Confidence interval | A range from resampling; the judged comparison uses paired article-component draws. It does not measure label errors. |
| Throughput | Encoded summaries divided by encoding seconds, on the recorded host. |
| Peak process memory | Process high-water resident memory, converted to GiB by the runner utility; excludes other processes. |

Historical JSON keys remain unchanged: `separation` = proxy ROC AUC; `spread` = mean cosine difference; `same_mean`/`different_mean` = positive/negative means; `ambiguous_mean`/`related_mean` = middle-overlap/same-outlet means; `ambiguous_lean`/`related_lean` = the two descriptive fractions above the class-mean midpoint. These aliases preserve old measured files; they do not introduce new scientific measures.

Definitions: [scikit-learn ROC AUC](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.roc_auc_score.html), [average precision](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html), [precision and recall](https://scikit-learn.org/stable/modules/model_evaluation.html#precision-recall-f-measure-metrics).
