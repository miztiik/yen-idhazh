"""What do complete article-neighbor judgments and overlapping memberships measure?"""

from __future__ import annotations

import math
from collections.abc import Mapping


def neighbor_metrics(ranking: list[str], relevance: Mapping[str, bool], k: int) -> dict[str, float]:
    if set(ranking) - relevance.keys():
        raise ValueError("unjudged neighbors cannot be treated as negatives")
    if len(set(ranking)) != len(ranking) or len(ranking) < k:
        raise ValueError("ranking needs k distinct neighbors")
    positives = sum(relevance.values())
    if positives == 0 or positives == len(relevance):
        raise ValueError("qrels require both relevant and nonrelevant candidate articles")
    hits = [int(relevance[identity]) for identity in ranking[:k]]
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, positives)))
    return {
        "precision_at_k": sum(hits) / k,
        "recall_at_k": sum(hits) / positives,
        "ndcg_at_k": dcg / ideal,
    }


def overlap_pair_metrics(
    gold: Mapping[str, set[str]],
    predicted: Mapping[str, set[str]],
) -> dict[str, float]:
    """Pairwise co-membership metrics support overlap; unlike ARI they assume no partition.

    Reference: overlapping pairwise evaluation, Collins & Dent (1988), Omega index
    comparisons; these are explicitly binary shared-membership precision/recall,
    not the chance-adjusted Omega statistic or ordinary partition ARI.
    """
    if gold.keys() != predicted.keys() or any(not labels for labels in gold.values()):
        raise ValueError("gold/prediction article coverage differs or gold membership is empty")
    if any(not labels for labels in predicted.values()):
        raise ValueError("prediction membership is empty")
    ids = sorted(gold)
    true_positive = false_positive = false_negative = true_negative = 0
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            actual = bool(gold[left] & gold[right])
            proposed = bool(predicted[left] & predicted[right])
            if actual and proposed:
                true_positive += 1
            elif proposed:
                false_positive += 1
            elif actual:
                false_negative += 1
            else:
                true_negative += 1
    if not true_positive + false_negative or not true_negative + false_positive:
        raise ValueError("overlap evaluation requires both shared and disjoint gold pairs")
    precision = (
        true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    )
    recall = true_positive / (true_positive + false_negative)
    return {
        "overlap_pair_precision": precision,
        "overlap_pair_recall": recall,
        "overlap_pair_f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0,
        "shared_gold_pairs": float(true_positive + false_negative),
        "disjoint_gold_pairs": float(true_negative + false_positive),
    }
