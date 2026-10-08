"""Find the pairs the encoders disagree about, using all of them at once.

Choosing which pairs deserve a person's attention is itself a decision with a
bias in it. Let one encoder pick the hard cases and every other encoder is then
judged on that one's opinion of what is hard - a set built from the leader's
near-misses flatters the leader. So every encoder gets a vote, and the pairs
that matter are the ones they cannot agree on.

Two readings come out of this, and only this: how far apart the encoders are on
a pair, and whether a pair sits near the line for most of them. Neither can be
taken from a score, because a score is one number for a whole set. They need
the positions the scores were computed from, which is why the shards keep them.

Each encoder's similarities are turned into ranks before anything is compared.
One model calls an unrelated pair 0.10 and another calls it 0.74, so comparing
the numbers compares how widely each paints its output. Comparing where a pair
sits in each encoder's own ordering compares what the encoders think.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def ranked(values: np.ndarray) -> np.ndarray:
    """Where each value sits in its own ordering, from 0 to 1.

    A rank cannot be fooled by scale. Two encoders that order a set of pairs
    identically agree completely here, whatever cosine numbers they printed.
    """
    order = values.argsort().argsort().astype(np.float64)
    return order / max(len(values) - 1, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--vectors-from", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bucket", default="ambiguous")
    args = parser.parse_args()

    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    listed = pairs[args.bucket]
    left_index = np.array([p[0] for p in listed])
    right_index = np.array([p[1] for p in listed])

    found: dict[str, np.ndarray] = {}
    for stored in sorted(args.vectors_from.rglob("*.npy")):
        vectors = np.load(stored)
        if vectors.shape[0] != len(pairs["texts"]):
            print(f"skipping {stored.stem}: {vectors.shape[0]} vectors for "
                  f"{len(pairs['texts'])} articles")
            continue
        similarity = np.sum(vectors[left_index] * vectors[right_index], axis=1)
        found[stored.stem] = ranked(similarity)
        print(f"read {stored.stem}: {len(similarity)} pairs")

    if len(found) < 2:
        raise SystemExit("two encoders at least, or there is no disagreement")

    stacked = np.vstack([found[name] for name in sorted(found)])
    disagreement = stacked.max(axis=0) - stacked.min(axis=0)
    middling = np.abs(stacked.mean(axis=0) - 0.5)

    # A pair is worth reading when the encoders are far apart on it, or when
    # they agree it sits on the line. Both are places a threshold decides the
    # answer, and both are invisible to a set drawn by title words alone.
    worth_reading = disagreement - middling

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({
            "bucket": args.bucket,
            "encoders": sorted(found),
            "pairs": len(listed),
            "scores": [
                {
                    "pair": [int(a), int(b)],
                    "disagreement": round(float(d), 4),
                    "distance_from_line": round(float(m), 4),
                    "worth_reading": round(float(w), 4),
                }
                for (a, b), d, m, w in zip(
                    listed, disagreement, middling, worth_reading, strict=True
                )
            ],
        }),
        encoding="utf-8",
    )

    print(f"encoders         {len(found)}")
    print(f"pairs            {len(listed)}")
    print(f"widest gap       {disagreement.max():.3f}")
    print(f"median gap       {np.median(disagreement):.3f}")
    print(f"wrote            {args.out}")


if __name__ == "__main__":
    main()
