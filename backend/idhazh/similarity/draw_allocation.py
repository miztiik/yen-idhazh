"""How many pairs does each slice give tonight's budget?

Pure integer arithmetic over the slices and how many pairs each one held. Nothing here sees
a pair, a score or a file, so the same pools and the same settings always give the same
takes.

**Every bucket has a strict planned ceiling.** `draw.bucket_budgets()` splits `pair_budget`
across all five buckets by largest remainder. A bucket that holds fewer pairs than its
ceiling leaves the unspent pairs unused rather than padding other buckets, so sparse nights
cleanly draw fewer than `pair_budget` pairs.

**Inside a bucket, slices share the ceiling evenly up to a relative per-slice cap.** Before
sharing a bucket's ceiling `B` across its `k` slices, each slice pool is capped at
`ceil((B / k) * slice_overflow_factor)` so sibling slices cannot absorb unbounded excess
when neighbors are sparse.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction

from idhazh.contracts.knobs.content_similarity_judge import DrawConfig
from idhazh.contracts.story_similarity_pair_verdict import PairBucket
from idhazh.similarity.slices import Slice


def per_slice_cap(budget: int, slice_count: int, *, overflow_factor: float) -> int:
    """Maximum pairs one slice may take in a bucket of `slice_count` slices and ceiling `budget`."""
    if budget <= 0 or slice_count <= 0:
        return 0
    return math.ceil(Fraction(budget, slice_count) * Fraction(str(overflow_factor)))


def allocate(slices: Sequence[Slice], pools: Sequence[int], *, draw: DrawConfig) -> tuple[int, ...]:
    """How many pairs to take from each slice, one number per slice in the order given.

    `pools` is how many pairs each slice held tonight. An unfunded bucket (`budget == 0`)
    takes zero pairs. A funded bucket refuses a slice list whose non-empty slices exceed its
    ceiling, because a slice that quietly took zero would be filed under no chance; grids
    built by `slice_grid(..., draw=draw)` auto-coarsen so that refusal cannot occur.
    """
    if len(slices) != len(pools):
        raise ValueError("one pool is needed for each slice")
    members = {
        bucket: [index for index, one in enumerate(slices) if one.bucket is bucket]
        for bucket in PairBucket
    }
    budgets = draw.bucket_budgets()
    takes = [0] * len(slices)

    for bucket in PairBucket:
        indices = members[bucket]
        if not indices:
            continue
        budget = budgets[bucket]
        if budget == 0:
            continue
        bucket_pools = [pools[index] for index in indices]
        holding = sum(1 for pool in bucket_pools if pool)
        if budget < holding:
            raise ValueError(
                f"pair_budget {draw.pair_budget} leaves {budget} pairs for the "
                f"{bucket.value} slices, and {holding} of them hold a pair tonight; raise "
                "pair_budget"
            )
        cap = per_slice_cap(budget, len(indices), overflow_factor=draw.slice_overflow_factor)
        effective_pools = [min(pool, cap) for pool in bucket_pools]
        for index, count in zip(indices, share_out(budget, effective_pools), strict=True):
            takes[index] = count
    return tuple(takes)


def share_out(budget: int, pools: Sequence[int]) -> list[int]:
    """Split `budget` over slices as evenly as the pools allow.

    Every slice gets the same number, no slice more than it holds, and a slice that cannot
    take its share leaves the rest to the others. When the budget does not divide, the slices
    that still have room take one more each, lowest score first. Whatever no slice can hold
    is left unspent, and the caller decides where it goes.
    """
    level = 0
    biggest = max(pools, default=0)
    while level < biggest and sum(min(pool, level + 1) for pool in pools) <= budget:
        level += 1
    takes = [min(pool, level) for pool in pools]
    spare = budget - sum(takes)
    for index, pool in enumerate(pools):
        if not spare:
            break
        if pool > level:
            takes[index] += 1
            spare -= 1
    return takes
