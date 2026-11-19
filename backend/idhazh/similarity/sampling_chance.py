"""What chance had a pair of being taken and usable, slice by slice?

A draw cannot know which of its pairs will come back usable, so the chance is worked out
afterwards, from the rows that arrived: the slice's usable pairs over the pairs the slice
held. A usable pair then stands for one over that many pairs of the night.

The count is over the rows that came back. A pair that left no row - a runner that died, a
pair whose items had aged out, the end of a file cut off by a deadline - was not usable, so it
lowers the chance, and the heavier weight of the usable pairs makes up for it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from idhazh.contracts.story_similarity_pair_verdict import PairBucket, StorySimilarityPairVerdict

_SliceKey = tuple[PairBucket, float, float]


def with_sampling_chance(
    rows: Sequence[StorySimilarityPairVerdict],
) -> list[StorySimilarityPairVerdict]:
    """The rows of one night's one run, each with its slice's usable count and chance filled in.

    Every row of a slice carries the same two numbers, including a row whose own readings
    disagreed. A slice with no usable pair has a chance of zero, which is a fact about the
    night and not a missing value. Rows of one slice have to agree on how many pairs it held
    and how many the draw took, which only rows of one night's one draw do, so a stray row
    from another draw is refused here instead of being weighed by a chance it has no claim to.
    """
    usable: Counter[_SliceKey] = Counter()
    seen: dict[_SliceKey, tuple[int, int]] = {}
    for row in rows:
        key = (row.bucket, row.slice_low, row.slice_high)
        counts = (row.slice_pairs_available, row.slice_pairs_judged)
        if seen.setdefault(key, counts) != counts:
            raise ValueError(
                f"the slice {row.bucket.value} {row.slice_low} to {row.slice_high} is held as "
                f"{seen[key]} by one row and as {counts} by another, so the rows are not from "
                "one draw"
            )
        usable[key] += row.readings_agree
    return [
        StorySimilarityPairVerdict.model_validate(
            row.model_dump(mode="json")
            | {
                "slice_pairs_usable": usable[key],
                "sampling_chance": usable[key] / row.slice_pairs_available,
            }
        )
        for row in rows
        for key in [(row.bucket, row.slice_low, row.slice_high)]
    ]
