"""The day's one order, and the frame a person set over its head.

Unit tier (CLAUDE.md section 13). Nothing here is mocked, no test touches the
network, and nothing reads the committed archive: every day below is built in
the test, including the day this plan needs and the archive has never produced -
one desk holding 18 of the top 20, one feed holding 9 of the top 10
(Guardrail #12).

What every test here defends is one sentence: **the frame moves a story and
never removes one.** A cap that drops rather than displaces shortens the day,
and a reader cannot see what was left out.
"""

from __future__ import annotations

from collections import Counter

import pytest

from idhazh.contracts.app_config import PlacementConfig
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.placement import place, stream_order

#: The five desks the taxonomy declares today.
DESKS = ("india", "world", "ai", "energy", "business-economy")


def story(
    item_id: str,
    *,
    vertical: str,
    source_id: str,
    rank_score: float | None,
    desk: str | None = None,
    published_at: str | None = "2026-09-13T09:00:00Z",
) -> DigestItem:
    """One published story, with every field the frame reads set explicitly."""
    return DigestItem(
        item_id=item_id,
        vertical=vertical,
        desk=desk,
        title="Something happened",
        source_url=f"https://example.test/{item_id}",
        source_id=source_id,
        source_name=source_id,
        summary="A summary.",
        key_points=["A point."],
        band=ConfidenceBand.HIGH,
        introduced_by_run=1,
        published_at=published_at,
        rank_score=rank_score,
    )


def desk_of(item: DigestItem) -> str:
    return item.desk or item.vertical


def lopsided_day() -> list[DigestItem]:
    """A day built to break the frame, which no committed day has ever been.

    The top twenty by score are eighteen `india` stories and two others, and the
    top ten are nine stories from one feed and one from a second. Every other
    desk then supplies eight stories from eight distinct feeds, so the frame has
    somewhere to go: without that supply the day could not fill a capped head and
    the test would be measuring the shortage instead of the cap.
    """
    items: list[DigestItem] = []
    score = 100.0

    for index in range(9):
        items.append(
            story(f"india-pti-{index:02d}", vertical="india", source_id="feed-pti", rank_score=score)
        )
        score -= 1.0
    for index in range(9):
        items.append(
            story(
                f"india-other-{index:02d}",
                vertical="india",
                source_id=f"feed-india-{index}",
                rank_score=score,
            )
        )
        score -= 1.0
    items.append(story("world-top-00", vertical="world", source_id="feed-reuters", rank_score=score))
    score -= 1.0
    items.append(story("ai-top-00", vertical="ai", source_id="feed-verge", rank_score=score))
    score -= 1.0

    for desk in ("world", "ai", "energy", "business-economy"):
        for index in range(8):
            items.append(
                story(
                    f"{desk}-{index:02d}",
                    vertical=desk,
                    source_id=f"feed-{desk}-{index}",
                    rank_score=score,
                )
            )
            score -= 1.0
    return items


def frame(**knobs: int) -> PlacementConfig:
    return PlacementConfig(**knobs)


# --- The oracle -------------------------------------------------------------


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

    out = place(day, config=config)

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
    head = place(lopsided_day(), config=config)[: config.head_items]

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
    head = place(lopsided_day(), config=config)[: config.head_items]

    assert len({desk_of(item) for item in head}) == 4
    assert set(DESKS) - {desk_of(item) for item in head}


def test_every_displaced_story_is_still_on_the_page_below_the_head() -> None:
    """A displaced story keeps its place in the day. Nothing is left out."""
    day = lopsided_day()
    config = frame()
    out = place(day, config=config)

    india = [item.item_id for item in day if item.vertical == "india"]
    in_head = {item.item_id for item in out[: config.head_items]}
    below = {item.item_id for item in out[config.head_items :]}

    assert len(india) == 18
    assert len(in_head & set(india)) == config.max_desk_in_head
    assert set(india) - in_head <= below


# --- What the frame may never do -------------------------------------------


def test_the_first_slot_is_the_scores_own_first_pick() -> None:
    """No cap can bind on an empty head, so the frame never argues about the lead."""
    day = lopsided_day()
    assert place(day, config=frame())[0].item_id == stream_order(day)[0].item_id


def test_past_the_head_the_order_is_the_scores_untouched() -> None:
    """The frame is a claim about the first screen and about nothing else."""
    day = lopsided_day()
    config = frame()
    out = place(day, config=config)

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
    out = place(day, config=frame())

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
    out = place(day, config=frame())

    assert len(out) == 12
    assert [item.item_id for item in out] == [item.item_id for item in stream_order(day)]


# --- The order itself -------------------------------------------------------


def test_an_unscored_story_sorts_last_and_never_as_zero() -> None:
    """`rank_score` is null on every day published before the field landed.

    Reading that as a score of zero would put those stories at the bottom on a
    day where every score is positive and at the top on a day where they are
    not, which is a claim the payload never made.
    """
    day = [
        story("ai-scored-low-10", vertical="ai", source_id="feed-a", rank_score=0.0),
        story("world-unscored-10", vertical="world", source_id="feed-b", rank_score=None),
        story("india-scored-high-10", vertical="india", source_id="feed-c", rank_score=9.0),
    ]
    assert [item.item_id for item in stream_order(day)] == [
        "india-scored-high-10",
        "ai-scored-low-10",
        "world-unscored-10",
    ]


def test_ties_break_on_the_time_then_the_address() -> None:
    """Two runs over one day must not disagree about the order.

    An alphabetical tie-break alone would hand a day of close scores to whichever
    host sorts first, so the story's own time is asked before its address.
    """
    day = [
        story(
            "ai-late-11",
            vertical="ai",
            source_id="feed-a",
            rank_score=1.0,
            published_at="2026-09-13T08:00:00Z",
        ),
        story(
            "ai-early-10",
            vertical="ai",
            source_id="feed-a",
            rank_score=1.0,
            published_at="2026-09-13T07:00:00Z",
        ),
        story(
            "ai-late-12",
            vertical="ai",
            source_id="feed-a",
            rank_score=1.0,
            published_at="2026-09-13T08:00:00Z",
        ),
    ]
    assert [item.item_id for item in stream_order(day)] == [
        "ai-late-11",
        "ai-late-12",
        "ai-early-10",
    ]
    assert [item.item_id for item in stream_order(list(reversed(day)))] == [
        "ai-late-11",
        "ai-late-12",
        "ai-early-10",
    ]


def test_the_frame_counts_the_desk_the_reader_sees() -> None:
    """`desk` is null until something reads the article and a page falls back.

    The frame has to count the same name a reader meets under the story, or it
    caps a grouping nobody is shown.
    """
    day = [
        story(
            f"origin-{index}-10",
            vertical=f"origin-{index}",
            source_id=f"feed-{index}",
            rank_score=100.0 - index,
            desk="ai",
        )
        for index in range(8)
    ] + [
        story(
            f"world-{index:02d}",
            vertical="world",
            source_id=f"feed-w-{index}",
            rank_score=50.0 - index,
        )
        for index in range(8)
    ]
    config = frame(head_items=10, head_no_repeat=0, max_desk_in_head=5)
    head = place(day, config=config)[: config.head_items]

    assert Counter(desk_of(item) for item in head)["ai"] == 5


# --- The knobs are knobs ----------------------------------------------------


def test_changing_the_desk_cap_changes_the_order_with_no_source_edit() -> None:
    """Guardrail #6's substitution test, run on the frame's own knob."""
    day = lopsided_day()
    tight = [item.item_id for item in place(day, config=frame(max_desk_in_head=5))]
    loose = [item.item_id for item in place(day, config=frame(max_desk_in_head=8))]

    assert tight != loose
    assert sorted(tight) == sorted(loose)


def test_changing_the_no_repeat_window_changes_the_order() -> None:
    day = lopsided_day()
    narrow = [item.item_id for item in place(day, config=frame(head_no_repeat=0))]
    wide = [item.item_id for item in place(day, config=frame(head_no_repeat=10))]

    assert narrow != wide
    assert sorted(narrow) == sorted(wide)


def test_a_head_of_zero_switches_the_frame_off() -> None:
    """An operator can publish the score's order whole and see what it looks like."""
    day = lopsided_day()
    out = place(day, config=frame(head_items=0, head_no_repeat=0))

    assert [item.item_id for item in out] == [item.item_id for item in stream_order(day)]


def test_a_no_repeat_window_wider_than_the_head_is_refused() -> None:
    """A rule that governs slots the frame does not reach reads as live and is not."""
    with pytest.raises(ValueError, match="cannot be wider than head_items"):
        PlacementConfig(head_items=10, head_no_repeat=11)


def test_the_committed_defaults_are_the_ones_that_were_ruled_on() -> None:
    """A fresh clone runs on these, so they are the numbers that ship."""
    config = PlacementConfig()

    assert (config.head_items, config.max_desk_in_head, config.head_no_repeat) == (20, 5, 10)
