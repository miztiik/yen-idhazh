"""Does the frame spread the head without ever making the day shorter?"""

from __future__ import annotations

from collections import Counter

from idhazh.placement import stream_order

from ._days import (
    DESKS,
    desk_of,
    frame,
    lopsided_day,
    placed,
    story,
)


def test_the_frame_holds_on_a_day_built_to_break_it() -> None:
    """Both caps bind, and the day is not one story shorter for it.

    The length assertion is half this oracle and it is the half a cap gets
    wrong. A cap that refuses a story instead of moving it publishes a shorter
    day, and nothing on the page says so.
    """
    day = lopsided_day()
    config = frame()

    unframed = stream_order(day)
    assert Counter(desk_of(item) for item in unframed[: config.head_items])["india"] == 18
    assert len({item.source_id for item in unframed[: config.head_no_repeat]}) == 2

    out = placed(day, config=config)

    assert len(out) == len(day)
    assert {item.item_id for item in out} == {item.item_id for item in day}

    head = out[: config.head_items]
    assert max(Counter(desk_of(item) for item in head).values()) <= config.max_desk_in_head
    opening = out[: config.head_no_repeat]
    assert len({item.source_id for item in opening}) == len(opening)

def test_the_caps_actually_bind_on_that_day() -> None:
    """The fixture exercises both rules rather than passing by being easy.

    The second and third assertions are what the cap of 5 was chosen to buy: a
    prefix of n stories holds at least n over the cap distinct desks. Twelve is
    the cold load, because the stream pages at twelve, and twenty is the head.
    """
    config = frame()
    head = placed(lopsided_day(), config=config)[: config.head_items]

    assert Counter(desk_of(item) for item in head)["india"] == config.max_desk_in_head
    assert len({desk_of(item) for item in head[:12]}) >= 3
    assert len({desk_of(item) for item in head}) >= 4

def test_a_thin_desk_can_miss_the_head_and_that_is_the_price_of_5() -> None:
    """The cost named when the cap was ruled at 5 rather than 4, written down.

    Four desks at five apiece fill a head of twenty on their own, so the fifth
    can be absent from it. A cap of 4 would refuse that and buy a quota - a head
    pinned at four of each desk every day, which could never report a day one
    desk genuinely owned.
    """
    config = frame()
    head = placed(lopsided_day(), config=config)[: config.head_items]

    assert len({desk_of(item) for item in head}) == 4
    assert set(DESKS) - {desk_of(item) for item in head}

def test_every_displaced_story_is_still_on_the_page_below_the_head() -> None:
    """A displaced story keeps its place in the day. Nothing is left out."""
    day = lopsided_day()
    config = frame()
    out = placed(day, config=config)

    india = [item.item_id for item in day if item.vertical == "india"]
    in_head = {item.item_id for item in out[: config.head_items]}
    below = {item.item_id for item in out[config.head_items :]}

    assert len(india) == 18
    assert len(in_head & set(india)) == config.max_desk_in_head
    assert set(india) - in_head <= below

def test_the_first_slot_is_the_scores_own_first_pick() -> None:
    """No cap can bind on an empty head, so the frame never argues about the lead."""
    day = lopsided_day()
    assert placed(day, config=frame())[0].item_id == stream_order(day)[0].item_id

def test_past_the_head_the_order_is_the_scores_untouched() -> None:
    """The frame is a claim about the first screen and about nothing else."""
    day = lopsided_day()
    config = frame()
    out = placed(day, config=config)

    tail = [item.item_id for item in out[config.head_items :]]
    head = {item.item_id for item in out[: config.head_items]}
    expected = [item.item_id for item in stream_order(day) if item.item_id not in head]
    assert tail == expected

def test_the_frame_yields_before_the_day_shortens() -> None:
    """A day the caps cannot spread publishes whole, in the score's own order.

    Thirty stories on one desk cannot fill a head capped at five. The best
    story each cap held down takes the slot back rather than the head running
    short, which on a single-desk day leaves the score's order untouched.
    """
    day = [
        story(
            f"ai-solo-{index:02d}",
            vertical="ai",
            source_id=f"feed-{index}",
            rank_score=100.0 - index,
        )
        for index in range(30)
    ]
    out = placed(day, config=frame())

    assert [item.item_id for item in out] == [item.item_id for item in stream_order(day)]

def test_a_day_shorter_than_the_head_comes_back_whole() -> None:
    """Twelve stories from one feed on one desk. Every cap is unsatisfiable."""
    day = [
        story(
            f"ai-one-feed-{index:02d}",
            vertical="ai",
            source_id="feed-a",
            rank_score=100.0 - index,
        )
        for index in range(12)
    ]
    out = placed(day, config=frame())

    assert len(out) == 12
    assert [item.item_id for item in out] == [item.item_id for item in stream_order(day)]
