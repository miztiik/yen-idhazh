"""Which of a day's borderline pairs today's budget judges, in what order, and on which shard.

Nothing here opens a file, reads a config or knows what a day is. It takes
pairs that are already scored and answers the one question a budget forces: the
band holds more pairs than a run can afford to judge, so which ones go, and in
what sequence.

The order is a hash of the pair's own contents and there is no seed. A seed is
a knob somebody can turn until the answer looks nice, and this order decides
which evidence the line is eventually fitted from.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass

from idhazh.assemble import ScoredPair
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.similarity.stamps import ScorerStamp


@dataclass(frozen=True, slots=True)
class Draw:
    """What one day's budget bought, and what it was bought out of."""

    #: The pairs this day judges, in the order the shards are cut from.
    taken: list[ScoredPair]
    #: How many pairs the band held before the budget cut it. A day that hit
    #: the cap reads as partial rather than as a quiet truncation.
    pairs_in_band: int


def pair_key(left_url_key: str, right_url_key: str) -> str:
    """The pair's identity: one digest over its two addresses, sorted.

    Sorted first because the two items are symmetric, so a pair scored in
    either order is one key and the record counts one event once. The two keys
    are joined with no separator, which is the same expression the contract
    recomputes on read - a separator, or a truncation, produces a row the
    contract refuses after the model calls have been paid for.
    """
    return derive_text_digest(
        min(left_url_key, right_url_key) + max(left_url_key, right_url_key)
    )


def draw_order(pair: ScoredPair, *, date: str, stamp: ScorerStamp) -> str:
    """The sort key: a digest over the day, the ruler and the pair's two ids.

    The date is in it so two days draw different sequences out of the same
    ranking. The ruler is in it so a re-scored day is re-drawn rather than
    handed yesterday's order under today's arithmetic. Both ids are in it,
    sorted, so the key is a property of the pair and not of which side of it
    the caller happened to name first.
    """
    return derive_text_digest(
        date
        + canonical_json(asdict(stamp))
        + min(pair.left, pair.right)
        + max(pair.left, pair.right)
    )


def in_band(
    pairs: Iterable[ScoredPair], *, band_low: float, band_high: float
) -> list[ScoredPair]:
    """The pairs worth judging: both edges included.

    Inclusive at both ends because the band is the range the record keeps slots
    for, and a pair landing exactly on an edge belongs in the slot that edge
    opens. A pair below the band is nowhere near one story, so a verdict on it
    costs a model call and moves nothing.
    """
    return [pair for pair in pairs if band_low <= pair.score <= band_high]


def select(
    pairs: Sequence[ScoredPair],
    *,
    line: float,
    budget: int,
    date: str,
    stamp: ScorerStamp,
) -> Draw:
    """Everything above the line, then as much of the rest as the budget allows.

    The order is the rule. A pair at or above the line is one the day MERGED,
    so it is the whole of the precision measurement and it is never cut - a
    budget that sampled those away would leave the run unable to say how many
    of its own merges were wrong. Below the line the pairs are interchangeable
    evidence, so they are ordered by their own content hash and taken until the
    budget is spent.

    A budget smaller than the above-line population is therefore overspent
    rather than enforced, and that is deliberate: the day already made those
    merges and the reader is already living with them.
    """
    ordered = sorted(pairs, key=lambda pair: draw_order(pair, date=date, stamp=stamp))
    above = [pair for pair in ordered if pair.score >= line]
    below = [pair for pair in ordered if pair.score < line]
    room = max(budget - len(above), 0)
    return Draw(taken=[*above, *below[:room]], pairs_in_band=len(pairs))


def assign_shards(
    taken: Sequence[ScoredPair], *, shards: int
) -> list[tuple[int, ScoredPair]]:
    """Deal the draw round the shards, one pair at a time.

    Index modulo the shard count rather than a contiguous block, so a draw the
    budget cut short still spreads across every shard instead of filling the
    first and starving the last.
    """
    return [(index % shards, pair) for index, pair in enumerate(taken)]
