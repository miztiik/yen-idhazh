"""How does a story reach a second desk, and why does it never reach a third?"""

from __future__ import annotations

from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.placement import DeskBounds, refile, secondary_desk_of, stream_order

from ._days import (
    desk_of,
    filed,
    story,
)


def cross_filed_day() -> list[DigestItem]:
    """Twenty stories, three of which a reading gave a second desk.

    Thirteen are filed on `ai` and three of those name `energy` as the one other
    desk their reading found. The other ten have no second desk at all, so the
    ceiling has exactly three stories it may move - which makes the counts below
    the rule's own arithmetic rather than whatever the fixture happened to allow.
    """
    day = [
        story(
            f"ai-crossed-{index:02d}",
            vertical="ai",
            desk="ai",
            secondary_desk="energy",
            source_id=f"feed-x{index}",
            rank_score=10.0 - index,
        )
        for index in range(3)
    ]
    day += [
        story(f"ai-only-{index:02d}", vertical="ai", desk="ai", source_id=f"feed-a{index}",
              rank_score=100.0 - index)
        for index in range(10)
    ]
    day += [
        story(f"world-own-{index:02d}", vertical="world", source_id=f"feed-w{index}",
              rank_score=50.0 - index)
        for index in range(7)
    ]
    return day

#: A day of twenty where `ai` may hold half and the other two are unbounded, so
#: the only rule that fires is the one this section is about.
CROSS_FILED_BOUNDS = {
    "ai": DeskBounds(floor=0, ceiling=0.5),
    "energy": DeskBounds(floor=0, ceiling=1.0),
    "world": DeskBounds(floor=0, ceiling=1.0),
}

def published_day(items: list[DigestItem]) -> DigestDay:
    """The day payload `assemble.build_day` writes, built here from the items.

    Every name any story holds gets a ref, so a second desk cannot be a topic
    the day never listed. The counts are handed to the real contract rather than
    re-derived in an assertion: `DigestDay` is what reconciles them, and a second
    copy of that rule in a test would only ever agree with itself.
    """
    present = sorted(
        {item.vertical for item in items}
        | {item.desk for item in items if item.desk}
        | {item.secondary_desk for item in items if item.secondary_desk}
    )
    return DigestDay(
        version=DigestDay.schema_version(),
        date="2026-09-13",
        generated_at="2026-09-13T12:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at="2026-09-13T12:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(
                id=name,
                display_name=name,
                count=sum(1 for item in items if item.vertical == name),
                desk_count=sum(1 for item in items if desk_of(item) == name),
            )
            for name in present
        ],
        items=items,
    )

def test_a_story_is_in_the_stream_once_and_on_at_most_two_desks() -> None:
    """Row #8's oracle, on a built day where three stories cross-file.

    Three assertions and the third is the one that matters. A story appears once
    in the stream; no story names more than two desks; and every desk's count
    equals the stories filed there. **A desk page showing 40 and listing 37 is
    the defect this catches**, and both numbers are the payload's own, so the
    day is built through `DigestDay` and its validators do the reconciling.
    """
    day = cross_filed_day()

    out = refile(stream_order(day), bounds=CROSS_FILED_BOUNDS)
    published = published_day(out)

    assert len(out) == len(day) == 20
    assert len(out) == len({item.item_id for item in out}), "a story is in the stream once"
    for item in out:
        named = {desk_of(item), *([item.secondary_desk] if item.secondary_desk else [])}
        assert len(named) <= 2, f"{item.item_id} names {sorted(named)}"

    crossed = sorted(item.item_id for item in out if item.secondary_desk is not None)
    assert crossed == [f"ai-crossed-{index:02d}" for index in range(3)]

    counted = {ref.id: ref for ref in published.verticals}
    assert {name: ref.count for name, ref in counted.items()} == {
        "ai": 13,
        "energy": 0,
        "world": 7,
    }
    assert {name: ref.desk_count for name, ref in counted.items()} == {
        "ai": 10,
        "energy": 3,
        "world": 7,
    }
    assert sum(ref.count for ref in published.verticals) == 20
    assert sum(ref.desk_count or 0 for ref in published.verticals) == 20

def test_the_second_desk_is_the_readings_own_and_the_feeds_word_is_the_fallback() -> None:
    """Two stories a crowded `ai` desk must give up, and they go to two places.

    One names `energy` as the desk its reading also found; it goes there. The
    other names nothing, so the feed's declared word is all there is and it goes
    back to `world`. That difference is the whole of this row: until it, the
    feed's word was the only answer, so a story already filed under its feed's
    word had nowhere to go and a crowded desk stayed crowded.
    """
    day = [
        story("world-reading-00", vertical="world", desk="ai", secondary_desk="energy",
              source_id="feed-r", rank_score=2.0),
        story("world-silent-00", vertical="world", desk="ai", source_id="feed-s", rank_score=1.0),
    ] + [
        story(f"ai-own-{index:02d}", vertical="ai", desk="ai", source_id=f"feed-a{index}",
              rank_score=100.0 - index)
        for index in range(8)
    ]

    out = refile(stream_order(day), bounds={"ai": DeskBounds(floor=0, ceiling=0.8)})
    landed = {item.item_id: item.desk for item in out}

    assert landed["world-reading-00"] == "energy"
    assert landed["world-silent-00"] == "world"
    assert len(out) == 10

def test_the_overflow_keeps_its_claim_on_the_desk_it_left() -> None:
    """The move swaps the two desks; it does not overwrite the first.

    A ceiling says a desk is busy today. It is not a judgement that the story
    was filed wrongly, so erasing what the story was read as would hand a
    crowding rule a second job nobody gave it. Ruled by Editor, 2026-09-13.
    """
    day = cross_filed_day()

    out = refile(stream_order(day), bounds=CROSS_FILED_BOUNDS)
    moved = [item for item in out if item.item_id.startswith("ai-crossed-")]

    assert [(item.desk, item.secondary_desk) for item in moved] == [("energy", "ai")] * 3
    assert all(item.vertical == "ai" for item in moved), "the address never moves"

def test_a_story_that_has_already_moved_cannot_move_twice() -> None:
    """The swap leaves a story naming two desks, and both are now taken.

    Its second desk is the desk it came from, so the ceiling cannot send it
    back and the floor cannot pull it back. A rule that could would ping a story
    between two desks for as many passes as it is given.
    """
    day = cross_filed_day()

    once = refile(stream_order(day), bounds=CROSS_FILED_BOUNDS)
    twice = refile(once, bounds=CROSS_FILED_BOUNDS)

    assert [(item.item_id, item.desk, item.secondary_desk) for item in twice] == [
        (item.item_id, item.desk, item.secondary_desk) for item in once
    ]

def test_a_second_desk_this_run_will_not_render_is_never_a_destination() -> None:
    """`closed` bounds the second desk exactly as it bounds the feed's word.

    A story sent to a desk the same day's payload says planned nothing would be
    reachable under a name the operator surface calls dark. The day also holds
    items an earlier run published against a different set of closed desks, so
    the check is owed here and not only where the item was written.
    """
    day = [
        story("world-crossed-00", vertical="world", desk="ai", secondary_desk="energy",
              source_id="feed-r", rank_score=1.0),
    ] + [
        story(f"ai-own-{index:02d}", vertical="ai", desk="ai", source_id=f"feed-a{index}",
              rank_score=100.0 - index)
        for index in range(4)
    ]

    out = refile(stream_order(day), bounds={"ai": DeskBounds(floor=0, ceiling=0.5)},
                 closed=frozenset({"energy"}))

    assert filed(out) == {"ai": 5}, "a closed desk received a story"
    assert all(item.secondary_desk in (None, "energy") for item in out)

def test_a_second_desk_is_dropped_rather_than_published_when_it_cannot_hold() -> None:
    """What `assemble.to_digest_item` may write into the payload, and what it may not.

    Two readings are refused and each would put a claim in the day that nothing
    can honour: one repeating the desk the day already filed the story under,
    and one naming a desk this run found below its feed floor. Null is nothing
    having said - the day falls back to the feed's word - and it is never the
    story saying it has no second desk.
    """
    assert secondary_desk_of("energy", filed_as="ai", below_floor=frozenset()) == "energy"
    assert secondary_desk_of(None, filed_as="ai", below_floor=frozenset()) is None
    assert secondary_desk_of("ai", filed_as="ai", below_floor=frozenset()) is None
    assert secondary_desk_of("energy", filed_as="ai", below_floor=frozenset({"energy"})) is None
