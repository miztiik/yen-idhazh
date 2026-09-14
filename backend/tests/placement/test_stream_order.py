"""What decides the order of the stream, and how is a tie broken?"""

from __future__ import annotations

from collections import Counter

from idhazh.placement import stream_order

from ._days import (
    desk_of,
    frame,
    placed,
    story,
)


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
    head = placed(day, config=config)[: config.head_items]

    assert Counter(desk_of(item) for item in head)["ai"] == 5
