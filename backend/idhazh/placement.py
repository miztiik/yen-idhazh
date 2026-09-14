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

The same rule governs the desk floor and the desk ceiling below. They change
which desk a story is filed under and nothing else: no story is admitted, none
is dropped, and the day comes back exactly as long as it went in. A story they
move keeps a claim on the desk it left, so a story names at most two desks and
the payload never loses what the story is about.

**A later run appends, and this order runs inside what a run added.** The day
publishes five times and a reader can read it after any of them, so an order
computed over the whole day would move a story somebody has already read - the
one thing `layout.md` names as the most disorienting thing this system could do,
and the rule `DigestDay` refuses a payload for breaking. So the sort, the desk
rules and the frame all run, and they run over one run's block at a time: the
day stays the blocks in the order the runs published them, and inside a block it
is the order this file computes. The day's best story reaching the top of the
page is `assemble.leading_stories`' job, and it is chosen across the whole day -
a second order over the same list, which costs a reader's memory nothing.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Container, Mapping, Sequence
from dataclasses import dataclass

from idhazh.contracts.app_config import PlacementConfig
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.taxonomy import Taxonomy


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


@dataclass(frozen=True, slots=True)
class DeskBounds:
    """What one desk may not fall below, and what it may not rise above.

    `floor` is a count and `ceiling` is a share of the published day. A count is
    a moving share - ten stories is 1.4 percent of a 731-story day and a quarter
    of a 40-story one - so the rule about crowding out the rest of the day is the
    share. A floor is a count because it asks whether the desk is worth opening
    at all, and six stories is a fragment on any size of day.
    """

    floor: int
    ceiling: float


def desk_bounds(taxonomy: Taxonomy) -> dict[str, DeskBounds]:
    """The two numbers per desk, read off `config/taxonomy.json`.

    Every desk the vocabulary carries, retired ones included. A day published
    last month can still hold a desk this file has since retired, and leaving it
    out here would hand that desk no rule rather than the rule it had.
    """
    return {
        vertical.id: DeskBounds(floor=vertical.floor, ceiling=vertical.ceiling)
        for vertical in taxonomy.verticals
    }


def _allowance(bounds: Mapping[str, DeskBounds], desk: str, *, day: int) -> int:
    """The most stories this desk may hold in a day of `day` stories.

    Never below the desk's own floor. A ceiling that cut a desk under the floor
    would be two rules contradicting each other on any small day - five desks at
    a floor of six need thirty stories, and a quarter of a twenty-story day is
    five - and the arithmetic that resolves it is the one
    `rank.day_source_ceiling` already uses for the per-feed case. It also means
    the ceiling switches itself off on a day too thin to backfill, at the exact
    point where it would have cut a desk below the breadth the floor guarantees,
    rather than at a day size somebody guessed. Ruled by Editor, 2026-09-13.

    A desk with no entry may hold the whole day. An absent rule is no rule.
    """
    bound = bounds.get(desk)
    if bound is None:
        return day
    return max(bound.floor, int(bound.ceiling * day))


def secondary_desk_of(
    secondary: str | None, *, filed_as: str, below_floor: Container[str]
) -> str | None:
    """The second desk a finished item may publish, or None where it may not.

    Two things disqualify a reading, and each would put a claim in the payload
    that nothing can honour. A second desk equal to the one the day already
    filed the story under is one desk written twice. A desk this run found under
    its feed floor renders nothing today, so a story pointing at it would be
    reachable under a name the same day's payload says planned nothing - which
    is the disagreement `rank.desk_of` already exists to stop, applied to the
    second name as well as the first.

    Null is nothing having said. It is never "this story has no second desk":
    the day falls back to the feed's declared vertical, which is what `refile`
    reads when this is absent.
    """
    if secondary is None or secondary == filed_as or secondary in below_floor:
        return None
    return secondary


def second_desk(item: DigestItem, *, filed_as: str, closed: Container[str]) -> str | None:
    """The desk a story falls back to when the desk it is on has no room for it.

    **The article's own second reading, and the feed's declared vertical only
    where there is no reading.** The feed's word was the whole answer until
    2026-09-13 and it is now the fallback: it could only ever send a story back
    to where it arrived, so a story already filed under its feed's word had
    nowhere to go and a crowded desk stayed crowded. A story has one second desk
    and never a list - a story on four desks is a story on no desk - so where a
    reading names one, that reading IS the answer and the feed's word is not a
    third try behind it.

    It reads where the story is filed NOW rather than where it arrived, so a
    story that has already moved has no second desk left and cannot move twice.
    That is what makes the whole re-file a single well-defined thing: it only
    ever undoes a relabel, and it never invents a filing nothing claimed.

    **A desk this run refused to render is never an answer.** `rank.desk_of`
    already sends a story away from a below-floor desk, and a rule that sent it
    back would publish stories under a name the same day's payload says planned
    nothing - the page and the operator surface saying opposite things about one
    word. `secondary_desk_of` keeps one out of a payload this run writes; this
    keeps one out of a move, and both are owed because the day also holds items
    an earlier run published against a different set of closed desks.
    """
    other = item.secondary_desk or item.vertical
    if other == filed_as or other in closed:
        return None
    return other


def refile(
    stream: Sequence[DigestItem],
    *,
    bounds: Mapping[str, DeskBounds],
    closed: Container[str] = frozenset(),
) -> list[DigestItem]:
    """Hold every desk under its ceiling and every desk at or over its floor.

    Takes the day already in score order and gives back the same stories in the
    same order, with some of them filed under a different desk. **It is the only
    thing this does.** Nothing is admitted, nothing is dropped, and the day is
    exactly as long as it arrived - so a reader's stream is untouched and only
    the desk pages move.

    Two passes, and the ceiling runs first because its overflow is the supply
    the floor fills from. Both move the same story - **a desk gives up its
    lowest-scoring movable one**, so the crowded desk keeps its best - and each
    answers a different question, so each stops somewhere different. The ceiling
    stops when the crowded desk is inside its share, whatever that leaves the
    desks it fed; a desk it opens with one story is a thin desk carrying a true
    label, which `DigestVerticalRef` already says is thin. The floor is taken in
    one piece: a desk is opened to its floor or left exactly as it was, because
    half a floor is two thin desks where there was one full one.

    Three things a floor may never do, and each one is a test.

    - **It never admits a story a gate refused.** `too_old`, `below_feed_floor`,
      a failed extraction and a failed summary all stand. The structural half is
      that a refused story never became a `DigestItem`, so it is not in the
      sequence this reads; the half that needs saying is `closed`, which keeps a
      desk the run will not render from receiving anything.
    - **It never reaches a previous day.** A day fills from its own stories.
    - **It never files a story on a desk the story has no claim to.** A story
      with no second desk stays where it is, and a desk it cannot fill publishes
      thin. `DigestVerticalRef` already carries why.

    A desk over its ceiling with nowhere to send the overflow stays over its
    ceiling. A rule that dropped the surplus would shorten the day, which is the
    one thing a frame may not buy.

    **A move swaps the two desks rather than overwriting the first.** The story
    goes to its second desk and the desk it left becomes its second, so the
    payload keeps saying what the story is about. A ceiling says a desk is busy
    today; it is not a judgement that the story was filed wrongly, and erasing
    the reading would give a crowding rule a second job nobody handed it. No
    count moves for it - `count` and `desk_count` both still answer for the desk
    a story is filed under, and the pill and the desk page widen together in a
    later change or neither does (Editor, 2026-09-13).
    """
    filed = {item.item_id: _desk_of(item) for item in stream}
    counts = Counter(filed.values())
    day = len(stream)
    allowed = {desk: _allowance(bounds, desk, day=day) for desk in {*filed.values(), *bounds}}
    floors = {desk: bound.floor for desk, bound in bounds.items()}

    def move(item: DigestItem, home: str, other: str) -> None:
        filed[item.item_id] = other
        counts[home] -= 1
        counts[other] += 1

    # The ceiling, worst-scoring first, so a crowded desk keeps its best. A desk
    # only ever falls as far as its allowance, and an allowance is never under a
    # floor, so this pass cannot open a hole the next one has to fill.
    for item in reversed(stream):
        home = filed[item.item_id]
        if counts[home] <= allowed.get(home, day):
            continue
        other = second_desk(item, filed_as=home, closed=closed)
        if other is None or counts[other] >= allowed.get(other, day):
            continue
        move(item, home, other)

    # The floor, taken in one piece per desk.
    for desk in sorted(floors):
        want = floors[desk] - counts[desk]
        if want <= 0:
            continue
        spare = Counter(counts)
        taken: list[tuple[DigestItem, str]] = []
        for item in reversed(stream):
            if len(taken) == want:
                break
            home = filed[item.item_id]
            if second_desk(item, filed_as=home, closed=closed) != desk:
                continue
            # A desk never dips under its own floor to lift another one over
            # theirs. That is two thin desks where there was one full one.
            if spare[home] - 1 < floors.get(home, 0):
                continue
            spare[home] -= 1
            taken.append((item, home))
        if len(taken) < want:
            continue
        for item, home in taken:
            move(item, home, desk)

    return [
        item
        if filed[item.item_id] == _desk_of(item)
        else item.model_copy(
            update={"desk": filed[item.item_id], "secondary_desk": _desk_of(item)}
        )
        for item in stream
    ]


def place(
    items: Sequence[DigestItem],
    *,
    config: PlacementConfig,
    bounds: Mapping[str, DeskBounds] | None = None,
    closed: Container[str] = frozenset(),
) -> list[DigestItem]:
    """The day in one order, with the desk rules applied and the frame on its head.

    Four things hold whatever the config says, and each one is a test:

    - **Every story comes back, exactly once.** `len(out) == len(in)`.
    - **A later run appends.** `introduced_by_run` never decreases down the
      list, because the order is computed inside each run's block and the blocks
      keep the order the runs published them in. That is the rule `DigestDay`
      refuses a payload for breaking, and it is why this is not one sort over
      the whole day.
    - **The first slot is the score's own first pick** among the stories the
      first run published. No cap can bind on an empty head, so the frame can
      never argue with the ranker about which story opens the day.
    - **Past `head_items` the order is the score's, untouched.** The frame is a
      claim about what a reader meets before deciding whether to scroll, and it
      has nothing to say about the four hundredth story.

    Where the caps cannot fill the head - a day with one desk, or a day shorter
    than the head - the best story a cap held down takes the slot back. The frame
    yields before the day does.

    **The head is the day's first `head_items` slots, not each block's.** A run
    that lands on a day already holding twenty stories gets no head at all and
    is published in plain score order, and a first run that published five
    leaves fifteen slots for the second. Counting per block would put a second
    framed head four hundred stories down the page, where nobody meets it.

    `refile` runs before the frame rather than after it, and over the whole day
    rather than per block, because the frame caps how much of the head one desk
    may hold and the desk rules are what decide which desk a story is on. A
    frame that ran first would cap a filing that was about to change, and a
    ceiling counted per block would be a share of the block rather than of the
    day. `refile` only ever relabels, so running it whole-day moves nothing.
    """
    stream = refile(stream_order(items), bounds=bounds or {}, closed=closed)
    placed: list[DigestItem] = []
    desks: Counter[str] = Counter()
    feeds: set[str] = set()

    for run in sorted({item.introduced_by_run for item in stream}):
        block = [item for item in stream if item.introduced_by_run == run]
        head: list[DigestItem] = []
        held: list[DigestItem] = []

        for item in block:
            # `placed` is every slot the day has already filled, so the head is
            # the head of the page rather than of this block.
            if len(placed) + len(head) >= config.head_items:
                break
            if desks[_desk_of(item)] >= config.max_desk_in_head:
                held.append(item)
                continue
            if len(placed) + len(head) < config.head_no_repeat and item.source_id in feeds:
                held.append(item)
                continue
            head.append(item)
            desks[_desk_of(item)] += 1
            if len(placed) + len(head) <= config.head_no_repeat:
                feeds.add(item.source_id)

        while len(placed) + len(head) < config.head_items and held:
            head.append(held.pop(0))

        taken = {item.item_id for item in head}
        placed.extend(head)
        placed.extend(item for item in block if item.item_id not in taken)

    return placed
