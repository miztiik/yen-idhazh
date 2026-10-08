"""Score an encoder the way the field scores one, and say how sure we are.

The first version of this comparison asked whether an encoder could tell a
lexically-near pair from a lexically-far one. Every encoder could: eight models
from 22 million to 568 million parameters landed between 0.9905 and 0.9925, an
ordering that puts the smallest model above the largest. A measurement that
cannot order its candidates is not ordering them, and the first version read
rank out of that gap anyway.

Three faults, each with a fix here.

**No idea how sure.** Every figure was one run over one sample with nothing
said about sampling error. Encoding is deterministic, so a vector needs no
error bar - but which pairs entered the sample is a sample, and pairs that
share an article or a wire story move together. A plain resample treats 5,517
pairs as 5,517 independent facts when the real count is nearer the number of
distinct stories. Resampling whole days keeps that dependence intact.

**A scale read as a skill.** The first version ranked on the gap between two
average similarities. Similarity scales are not comparable between encoders:
one model puts unrelated pairs near 0.10 and another near 0.74, because models
differ in how widely they paint their output. The gap then mostly reports the
painting. Dividing by the spread of the two groups removes it.

**The easy question.** Negatives were drawn from pairs whose titles share
almost nothing - different stories in different words. Separating those is
free. The decision the pipeline actually makes is between one event and a
near neighbour, and nothing measured that.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def separation_statistics(
    positive: np.ndarray, negative: np.ndarray
) -> dict[str, float]:
    """How well two groups of similarities come apart, on three readings."""
    labels = np.concatenate([np.ones(len(positive)), np.zeros(len(negative))])
    scores = np.concatenate([positive, negative])
    pooled = math.sqrt(
        (float(positive.var(ddof=1)) + float(negative.var(ddof=1))) / 2
    )
    return {
        "average_precision": float(average_precision_score(labels, scores)),
        "area_under_curve": float(roc_auc_score(labels, scores)),
        # The gap between the two averages, divided by how widely they spread.
        # The division is what makes it comparable between encoders.
        "standardised_gap": (
            float(positive.mean() - negative.mean()) / pooled if pooled > 0 else 0.0
        ),
        "positive_mean": float(positive.mean()),
        "negative_mean": float(negative.mean()),
        "raw_gap": float(positive.mean() - negative.mean()),
    }


def resample_by_day(
    positive: np.ndarray,
    negative: np.ndarray,
    positive_days: list[str],
    negative_days: list[str],
    rounds: int,
    seed: int,
) -> dict[str, tuple[float, float]]:
    """How much each reading moves when whole days are drawn again.

    Days, not pairs. Two reports of one wire story are not two independent
    facts, and nor are two pairs that share an article. Drawing whole days
    keeps those together, which is the difference between a confidence range
    that means something and one that is too narrow to be honest.
    """
    by_day_positive: dict[str, list[int]] = defaultdict(list)
    by_day_negative: dict[str, list[int]] = defaultdict(list)
    for index, day in enumerate(positive_days):
        by_day_positive[day].append(index)
    for index, day in enumerate(negative_days):
        by_day_negative[day].append(index)

    days = sorted(set(positive_days) | set(negative_days))
    rng = random.Random(seed)
    collected: dict[str, list[float]] = defaultdict(list)

    for _ in range(rounds):
        drawn = [rng.choice(days) for _ in days]
        p_index = [i for day in drawn for i in by_day_positive.get(day, [])]
        n_index = [i for day in drawn for i in by_day_negative.get(day, [])]
        if len(p_index) < 30 or len(n_index) < 30:
            continue
        for name, value in separation_statistics(
            positive[p_index], negative[n_index]
        ).items():
            collected[name].append(value)

    return {
        name: (
            float(np.percentile(values, 2.5)),
            float(np.percentile(values, 97.5)),
        )
        for name, values in collected.items()
        if values
    }


def threshold_at_precision(
    positive: np.ndarray, negative: np.ndarray, target: float
) -> dict[str, float]:
    """The cut that hits a precision target, and what it recalls there.

    One cut cannot be shared between encoders. A model whose unrelated pairs
    already sit at 0.74 and a model whose sit at 0.10 do not mean the same
    thing by the same number, so each is given the cut that earns the same
    precision and judged on what it recalls at it. Comparing them at one
    shared number compares their scales.
    """
    scores = np.concatenate([positive, negative])
    labels = np.concatenate([np.ones(len(positive)), np.zeros(len(negative))])
    order = np.argsort(-scores)
    labels = labels[order]
    scores = scores[order]

    hits = np.cumsum(labels)
    precision = hits / np.arange(1, len(labels) + 1)
    reaches = np.where(precision >= target)[0]
    if len(reaches) == 0:
        return {"threshold": float("nan"), "recall": 0.0, "precision": 0.0}

    cut = int(reaches[-1])
    return {
        "threshold": float(scores[cut]),
        "recall": float(hits[cut] / len(positive)),
        "precision": float(precision[cut]),
    }


def read_pairs(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--resample-rounds", type=int, default=1000)
    parser.add_argument("--precision-target", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=20261008)
    args = parser.parse_args()

    pairs = read_pairs(args.pairs)
    vectors = np.load(args.vectors)

    def similarity(named: str) -> np.ndarray:
        listed = pairs.get(named, [])
        if not listed:
            return np.array([])
        left = vectors[[p[0] for p in listed]]
        right = vectors[[p[1] for p in listed]]
        scored: np.ndarray = np.sum(left * right, axis=1)
        return scored

    positive = similarity("same")
    easy_negative = similarity("different")
    near_negative = similarity("ambiguous")
    second_piece = similarity("related")

    days = pairs.get("pair_days", {})
    positive_days = days.get("same", ["one"] * len(positive))
    easy_days = days.get("different", ["one"] * len(easy_negative))
    near_days = days.get("ambiguous", ["one"] * len(near_negative))

    report: dict[str, Any] = {
        "slug": args.slug,
        "pairs": {
            "same_event": len(positive),
            "clearly_different": len(easy_negative),
            "near_neighbour": len(near_negative),
            "second_piece": len(second_piece),
        },
        # The question the first version asked. Kept because an encoder that
        # fails it is unfit, and dropped as a ranking because every candidate
        # passes it.
        "against_clearly_different": separation_statistics(positive, easy_negative),
        # The question the pipeline actually faces: one event against its near
        # neighbour. This is where encoders are expected to come apart.
        "against_near_neighbour": separation_statistics(positive, near_negative),
    }

    report["against_clearly_different"]["range"] = resample_by_day(
        positive, easy_negative, positive_days, easy_days,
        args.resample_rounds, args.seed,
    )
    report["against_near_neighbour"]["range"] = resample_by_day(
        positive, near_negative, positive_days, near_days,
        args.resample_rounds, args.seed,
    )

    report["operating_point"] = {
        "precision_target": args.precision_target,
        "against_clearly_different": threshold_at_precision(
            positive, easy_negative, args.precision_target
        ),
        "against_near_neighbour": threshold_at_precision(
            positive, near_negative, args.precision_target
        ),
    }

    # Does one outlet's second piece look like a match because the event is the
    # same, or because everything that outlet publishes reads alike after the
    # summariser has levelled its register? The second would show as unrelated
    # pairs from one outlet scoring above unrelated pairs from two.
    if len(second_piece):
        report["second_piece"] = {
            "mean": float(second_piece.mean()),
            "same_event_mean": float(positive.mean()),
            "clearly_different_mean": float(easy_negative.mean()),
            "share_above_same_event_mean": float(
                (second_piece > positive.mean()).mean()
            ),
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1), encoding="utf-8")

    easy = report["against_clearly_different"]
    hard = report["against_near_neighbour"]
    easy_range = easy["range"].get("average_precision", (0.0, 0.0))
    hard_range = hard["range"].get("average_precision", (0.0, 0.0))
    print(f"{args.slug}")
    print(f"  against clearly different  AP {easy['average_precision']:.4f}  "
          f"({easy_range[0]:.4f} to {easy_range[1]:.4f})  "
          f"gap {easy['standardised_gap']:.2f}")
    print(f"  against near neighbour     AP {hard['average_precision']:.4f}  "
          f"({hard_range[0]:.4f} to {hard_range[1]:.4f})  "
          f"gap {hard['standardised_gap']:.2f}")
    point = report["operating_point"]["against_near_neighbour"]
    print(f"  at {args.precision_target:.0%} precision: cut "
          f"{point['threshold']:.3f}, recalls {point['recall']:.1%}")


if __name__ == "__main__":
    main()
