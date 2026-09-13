"""Where a story goes in the day, once the score has said how good it is.

`rank.py` scores one story against the others on its own desk. This decides what
the whole day looks like given every story's score: one order over every item the
day carries, and a frame over the head of it that a person sets in `config/`.

The frame exists because nobody reads this digest before it publishes and it
publishes five times a day. A standing editorial decision can therefore only
reach a reader as arithmetic that runs without one, and these are the two
decisions it carries: how much of the head one desk may hold, and how far down
the head one feed may repeat.

**A cap displaces; it never shortens.** A story a cap holds out of the head
keeps its place in the day, lower down - the slot it gives up goes to the best
story that fits. `rank._take` follows the same rule for the day ceiling and this
is that rule applied to an order rather than to a selection. The day a reader
gets is never one story shorter for the frame, because a reader cannot see what
was left out.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from idhazh.contracts.app_config import PlacementConfig
from idhazh.contracts.digest_day import DigestItem


def stream_order(items: Sequence[DigestItem]) -> list[DigestItem]:
    """Every story the day carries, best first, with no frame over it.

    Score, then the story's own time, then its address. Sorts are stable, so
    these compose least-significant first - the same shape `rank._ordered` uses,
    for the same reason: on a day where the scores sit close together an
    alphabetical tie-break would quietly hand the head to whichever host sorts
    first.

    A story with no score sorts last rather than at zero. `rank_score` is null on
    every day published before the field landed, and reading that as a score of
    zero would be a claim the payload never made.
    """
    ordered = sorted(items, key=lambda item: item.item_id)
    ordered.sort(key=lambda item: item.published_at or "", reverse=True)
    ordered.sort(
        key=lambda item: (item.rank_score is not None, item.rank_score or 0.0), reverse=True
    )
    return ordered


def _desk_of(item: DigestItem) -> str:
    """What the frame counts a story against, which is where the day publishes it.

    `desk` is null until something reads the article, and a page already falls
    back to the feed's declared vertical. The frame has to count the same name
    the reader sees under the story, or it would cap a grouping nobody meets.
    """
    return item.desk or item.vertical


def place(items: Sequence[DigestItem], *, config: PlacementConfig) -> list[DigestItem]:
    """The day in one order, with the frame applied to its head.

    Three things hold whatever the config says, and each one is a test:

    - **Every story comes back, exactly once.** `len(out) == len(in)`.
    - **The first slot is the score's own first pick.** No cap can bind on an
      empty head, so the frame can never argue with the ranker about the day's
      lead story.
    - **Past `head_items` the order is the score's, untouched.** The frame is a
      claim about what a reader meets before deciding whether to scroll, and it
      has nothing to say about the four hundredth story.

    Where the caps cannot fill the head - a day with one desk, or a day shorter
    than the head - the best story a cap held down takes the slot back. The frame
    yields before the day does.
    """
    stream = stream_order(items)
    head: list[DigestItem] = []
    held: list[DigestItem] = []
    desks: Counter[str] = Counter()
    feeds: set[str] = set()

    for item in stream:
        if len(head) >= config.head_items:
            break
        if desks[_desk_of(item)] >= config.max_desk_in_head:
            held.append(item)
            continue
        if len(head) < config.head_no_repeat and item.source_id in feeds:
            held.append(item)
            continue
        head.append(item)
        desks[_desk_of(item)] += 1
        if len(head) <= config.head_no_repeat:
            feeds.add(item.source_id)

    while len(head) < config.head_items and held:
        head.append(held.pop(0))

    taken = {item.item_id for item in head}
    return [*head, *(item for item in stream if item.item_id not in taken)]
