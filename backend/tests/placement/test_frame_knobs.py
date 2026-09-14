"""Does changing a frame knob change the order with no source edit?"""

from __future__ import annotations

from collections import Counter

import pytest

from idhazh.contracts.app_config import PlacementConfig
from idhazh.placement import stream_order

from ._days import (
    BOUNDS,
    desk_of,
    frame,
    heavy_ai_day,
    lopsided_day,
    placed,
)


def test_changing_the_desk_cap_changes_the_order_with_no_source_edit() -> None:
    """Guardrail #6's substitution test, run on the frame's own knob."""
    day = lopsided_day()
    tight = [item.item_id for item in placed(day, config=frame(max_desk_in_head=5))]
    loose = [item.item_id for item in placed(day, config=frame(max_desk_in_head=8))]

    assert tight != loose
    assert sorted(tight) == sorted(loose)


def test_changing_the_no_repeat_window_changes_the_order() -> None:
    day = lopsided_day()
    narrow = [item.item_id for item in placed(day, config=frame(head_no_repeat=0))]
    wide = [item.item_id for item in placed(day, config=frame(head_no_repeat=10))]

    assert narrow != wide
    assert sorted(narrow) == sorted(wide)


def test_a_head_of_zero_switches_the_frame_off() -> None:
    """An operator can publish the score's order whole and see what it looks like."""
    day = lopsided_day()
    out = placed(day, config=frame(head_items=0, head_no_repeat=0))

    assert [item.item_id for item in out] == [item.item_id for item in stream_order(day)]


def test_a_no_repeat_window_wider_than_the_head_is_refused() -> None:
    """A rule that governs slots the frame does not reach reads as live and is not."""
    with pytest.raises(ValueError, match="cannot be wider than head_items"):
        PlacementConfig(head_items=10, head_no_repeat=11)


def test_the_frame_counts_the_desk_the_rules_left_the_story_on() -> None:
    """`place` re-files before it frames, and the order between them matters.

    The frame caps how much of the head one desk may hold, and the desk rules
    decide which desk a story is on. A frame that ran first would cap a filing
    that was about to change, so the head would be spread against names the
    finished day no longer uses.
    """
    day = heavy_ai_day()
    config = frame()

    unbounded = placed(day, config=config)[: config.head_items]
    bounded = placed(day, config=config, bounds=BOUNDS)[: config.head_items]

    assert Counter(desk_of(item) for item in unbounded) == {"ai": 20}
    assert max(Counter(desk_of(item) for item in bounded).values()) <= config.max_desk_in_head
    assert len({desk_of(item) for item in bounded}) == 5


def test_the_committed_defaults_are_the_ones_that_were_ruled_on() -> None:
    """A fresh clone runs on these, so they are the numbers that ship."""
    config = PlacementConfig()

    assert (config.head_items, config.max_desk_in_head, config.head_no_repeat) == (20, 5, 10)
