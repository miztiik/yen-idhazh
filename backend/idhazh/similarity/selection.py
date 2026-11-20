"""Which pairs of a night does the budget judge, in what order, and on which shard?

Nothing here opens a file, reads a config file or knows what a day is. It takes pairs that
are already scored and the two thresholds the night follows, and answers the one question a
budget forces: the night holds far more pairs than a run can afford to judge, so which ones
go. The score range is cut into slices (`similarity.slices`), each slice gives a number of
pairs (`similarity.draw_allocation`), and the pairs a slice gives are the first ones in a
fixed order.

The order is a hash of the pair's own contents and there is no seed. A seed is a knob
somebody can turn until the answer looks nice, and this order decides which evidence the
thresholds are eventually found from.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Iterable, Mapping, Sequence, Set
from dataclasses import asdict, dataclass

from idhazh.assemble import ScoredPair
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.knobs.content_similarity_judge import DrawConfig
from idhazh.similarity.draw_allocation import allocate
from idhazh.similarity.slices import Slice, slice_grid
from idhazh.similarity.stamps import ScorerStamp


@dataclass(frozen=True, slots=True)
class DrawnPair:
    """One pair the night judges, and what its slice held and gave."""

    pair: ScoredPair
    slice: Slice
    #: How many pairs the slice held tonight, this one included.
    slice_pairs_available: int
    #: How many pairs the draw took from the slice, this one included.
    slice_pairs_judged: int
    #: Where the pair stands among the pairs its slice gave, best first, from 0.
    slice_rank: int
    #: Where the pair stands when every slice's pairs are listed in turn, lowest slice
    #: first. The shard is this number modulo the shard count.
    deal_index: int


@dataclass(frozen=True, slots=True)
class Draw:
    """What one night's budget bought, and what it was bought out of."""

    #: The pairs this night judges, in the order the verdict file lists them.
    taken: list[DrawnPair]
    #: How many pairs the night held before the budget cut it, each pair of addresses once.
    pairs_available: int


def pair_key(left_url_key: str, right_url_key: str) -> str:
    """The pair's identity: one digest over its two addresses, sorted.

    Sorted first because the two items are symmetric, so a pair scored in either order is
    one key. The two keys are joined with no separator, which is the same expression the
    contract recomputes on read - a separator, or a truncation, produces a row the contract
    refuses after the model calls have been paid for.
    """
    return derive_text_digest(
        min(left_url_key, right_url_key) + max(left_url_key, right_url_key)
    )


def draw_order_of(*, date: str, stamp: ScorerStamp) -> Callable[[ScoredPair], str]:
    """The sort key: a digest over the day, the ruler and the pair's two ids.

    The date is in it so two days draw different sequences out of the same ranking. The ruler
    is in it so a re-scored day is re-drawn rather than handed yesterday's order under
    today's arithmetic. Both ids are in it, sorted, so the key is a property of the pair and
    not of which side of it the caller happened to name first. The day and the ruler are
    joined once, and the function it returns costs one digest a pair.
    """
    prefix = date + canonical_json(asdict(stamp))

    def order(pair: ScoredPair) -> str:
        return derive_text_digest(prefix + min(pair.left, pair.right) + max(pair.left, pair.right))

    return order


def one_pair_a_key(
    pairs: Iterable[ScoredPair], *, address_of: Mapping[str, str], own: Set[str]
) -> list[ScoredPair]:
    """Each pair of addresses once, in the order the pairs came.

    A story republished on a later day keeps its address and takes a new item id, so one
    pair of addresses can arrive as two pairs of items, and a model call spent on the second
    is a call spent twice. The copy kept is the one made of the most of the night's own
    items, because the judge reads the night's own copy of an address, so the score a slice
    is cut by is then the score of the text judged. A tie keeps the first.

    `address_of` maps every item id the pairs name to the address key its row carries, and
    `own` is the ids of the night's own items.
    """
    kept: dict[str, tuple[int, ScoredPair]] = {}
    for pair in pairs:
        key = pair_key(address_of[pair.left], address_of[pair.right])
        rank = (pair.left in own) + (pair.right in own)
        held = kept.get(key)
        if held is None or rank > held[0]:
            kept[key] = (rank, pair)
    return [pair for _, pair in kept.values()]


def select(
    pairs: Iterable[ScoredPair],
    *,
    lower: float,
    upper: float,
    draw: DrawConfig,
    date: str,
    stamp: ScorerStamp,
) -> Draw:
    """Sort the pairs into slices, take each slice's number, and order what was taken.

    The pairs a slice gives are the first in the draw's own order. They are then ordered
    by how far down their slice's list they stand, so every slice's pairs are spread along
    the file in proportion. A runner that stops on its clock loses the end of its file; a
    file ordered by the hash alone would lose the small slices first, because a big pool
    gives the pairs with the smallest hashes, and a file ordered slice by slice would lose
    whole slices. Spread in proportion, the loss is a similar share of every slice, which
    the sampling chance (usable over available) corrects.
    """
    grid = slice_grid(lower, upper, draw=draw)
    held: list[list[ScoredPair]] = [[] for _ in grid.slices]
    available = 0
    for pair in pairs:
        held[grid.index_of(pair.score)].append(pair)
        available += 1
    takes = allocate(grid.slices, [len(pool) for pool in held], draw=draw)
    order = draw_order_of(date=date, stamp=stamp)
    chosen: list[DrawnPair] = []
    for one, pool, count in zip(grid.slices, held, takes, strict=True):
        for rank, pair in enumerate(heapq.nsmallest(count, pool, key=order)):
            chosen.append(DrawnPair(pair, one, len(pool), count, rank, len(chosen)))
    chosen.sort(key=lambda drawn: (drawn.slice_rank / drawn.slice_pairs_judged, order(drawn.pair)))
    return Draw(taken=chosen, pairs_available=available)


def assign_shards(
    taken: Sequence[DrawnPair], *, shards: int
) -> list[tuple[int, DrawnPair]]:
    """Deal the draw round the shards, one pair at a time, slice by slice.

    The deal runs over every slice's pairs in turn, so each slice is dealt round the shards
    and a lost runner takes a share of each, never a whole slice of two pairs or more. Index
    modulo the shard count rather than a contiguous block, so a draw the budget cut short
    still spreads across every shard instead of filling the first and starving the last.
    Each pair keeps its place in the file's own order.
    """
    return [(drawn.deal_index % shards, drawn) for drawn in taken]
