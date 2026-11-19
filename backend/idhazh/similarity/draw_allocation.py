"""How many pairs does each slice give tonight's budget?

Pure integer arithmetic over the slices and how many pairs each one held. Nothing here sees
a pair, a score or a file, so the same pools and the same settings always give the same
takes.

**The two lightly sampled ends go first.** Each takes its weight's share of the budget,
raised to its minimum, lowered to its maximum and never past what it holds. What they leave
is shared among the three buckets between the thresholds in proportion to their weights.

**Inside a bucket every slice gets an equal share.** A slice that holds fewer pairs than its
share takes them all, and the others split what it leaves. Every slice that holds a pair
therefore gets at least one. A bucket that holds fewer pairs than its share hands the rest
on to the other buckets between the thresholds, heaviest weight first, so a night judges
fewer pairs than its budget only when every slice between the thresholds is spent.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from idhazh.contracts.knobs.content_similarity_judge import DrawConfig
from idhazh.contracts.story_similarity_pair_verdict import PairBucket
from idhazh.similarity.slices import Slice

#: The three buckets between the thresholds in score order, which settles two equal weights.
_BETWEEN_THE_THRESHOLDS: Final = (
    PairBucket.LOWER_THIN,
    PairBucket.MIDDLE_COARSE,
    PairBucket.UPPER_THIN,
)


def allocate(slices: Sequence[Slice], pools: Sequence[int], *, draw: DrawConfig) -> tuple[int, ...]:
    """How many pairs to take from each slice, one number per slice in the order given.

    `pools` is how many pairs each slice held tonight. A refusal names the setting to move:
    a budget that cannot give each lightly sampled end its pairs, or that cannot give every
    slice between the thresholds that holds a pair one of its own, is a setting that cannot
    run the design, and a draw that quietly skipped a slice would file it under no chance.
    """
    if len(slices) != len(pools):
        raise ValueError("one pool is needed for each slice")
    members = {
        bucket: [index for index, one in enumerate(slices) if one.bucket is bucket]
        for bucket in PairBucket
    }
    weights = {
        PairBucket.LOWER_THIN: draw.bucket_weights.lower_thin,
        PairBucket.MIDDLE_COARSE: draw.bucket_weights.middle_coarse,
        PairBucket.UPPER_THIN: draw.bucket_weights.upper_thin,
    }
    ends = {
        PairBucket.FULLY_DISSIMILAR: draw.fully_dissimilar,
        PairBucket.FULLY_SIMILAR: draw.fully_similar,
    }
    whole = sum(weights.values()) + sum(end.weight for end in ends.values())

    takes = [0] * len(slices)
    for bucket, end in ends.items():
        target = _rounded_share(draw.pair_budget, end.weight, whole)
        wanted = max(end.minimum, min(target, end.maximum))
        for index in members[bucket]:
            takes[index] = min(pools[index], wanted)
    remaining = draw.pair_budget - sum(takes)
    if remaining < 0:
        raise ValueError(
            f"pair_budget {draw.pair_budget} is less than the {sum(takes)} pairs the two "
            "lightly sampled ends take at their minimums"
        )

    heaviest_first = sorted(
        _BETWEEN_THE_THRESHOLDS,
        key=lambda bucket: (-weights[bucket], _BETWEEN_THE_THRESHOLDS.index(bucket)),
    )
    shares = dict(
        zip(
            heaviest_first,
            _split(remaining, [weights[bucket] for bucket in heaviest_first]),
            strict=True,
        )
    )
    taken: dict[PairBucket, list[int]] = {}
    for bucket in heaviest_first:
        bucket_pools = [pools[index] for index in members[bucket]]
        holding = sum(1 for pool in bucket_pools if pool)
        if shares[bucket] < holding:
            raise ValueError(
                f"pair_budget {draw.pair_budget} leaves {shares[bucket]} pairs for the "
                f"{bucket.value} slices, and {holding} of them hold a pair tonight; raise "
                "pair_budget"
            )
        taken[bucket] = share_out(shares[bucket], bucket_pools)

    unspent = sum(shares[bucket] - sum(taken[bucket]) for bucket in heaviest_first)
    for bucket in heaviest_first:
        if not unspent:
            break
        bucket_pools = [pools[index] for index in members[bucket]]
        room = sum(bucket_pools) - sum(taken[bucket])
        if not room:
            continue
        grant = min(unspent, room)
        taken[bucket] = share_out(sum(taken[bucket]) + grant, bucket_pools)
        unspent -= grant

    for bucket in heaviest_first:
        for index, count in zip(members[bucket], taken[bucket], strict=True):
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


def _rounded_share(budget: int, weight: int, whole: int) -> int:
    """`budget * weight / whole`, rounded half up, in integers so no float decides a pair."""
    return (2 * budget * weight + whole) // (2 * whole)


def _split(total: int, weights: Sequence[int]) -> list[int]:
    """`total` in proportion to `weights`, to whole pairs, the largest fractions rounding up.

    A fraction that ties goes to the earlier weight, so the answer never depends on a sort's
    stability.
    """
    whole = sum(weights)
    shares = [total * weight // whole for weight in weights]
    by_fraction = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % whole), i))
    for index in by_fraction[: total - sum(shares)]:
        shares[index] += 1
    return shares
