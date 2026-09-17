"""Does a day where every story reads one desk still publish five?"""

from __future__ import annotations

from idhazh.placement import DeskBounds, refile, stream_order

from ._days import (
    BOUNDS,
    DESKS,
    filed,
    gated_day,
    heavy_ai_day,
    story,
)


def test_a_day_where_every_story_reads_ai_still_publishes_five_desks() -> None:
    """The ceiling holds, and the day is not one story shorter.

    Forty stories, every one filed on `ai` by whatever read them. The ceiling
    sends the surplus back to the desk whose feed carried the story, and the
    floor tops up anything that lands under six. Five desks, none over its
    ceiling, none under its floor, and exactly forty stories either way.
    """
    day = heavy_ai_day()

    assert filed(day) == {"ai": 40}

    out = refile(stream_order(day), bounds=BOUNDS)
    counted = filed(out)

    assert len(out) == len(day)
    assert {item.item_id for item in out} == {item.item_id for item in day}
    assert set(counted) == set(DESKS)
    for desk, count in counted.items():
        assert count <= int(BOUNDS[desk].ceiling * len(out)), f"{desk} is over its ceiling"
        assert count >= BOUNDS[desk].floor, f"{desk} is under its floor"
    assert counted == {"ai": 14, "energy": 7, "business-economy": 7, "world": 6, "india": 6}


def test_the_floor_never_admits_a_story_a_gate_refused() -> None:
    """The second half, and the half that matters.

    A floor that can promote a rejected story is a floor that publishes what a
    gate refused. Two gates stand here and they fail differently. `world` is
    below its feed floor, so this run planned nothing for it and it must receive
    nothing - even though five stories in the day would lawfully fall back to it
    and every one of them outscores the day's tail. `business-economy` is thin
    because what would have filled it was too old to be collected, so no story in
    the day names that desk and there is nothing to reach for.

    Three rules give three different answers on this day and only one is right.
    The day as it arrives leaves `energy` at 1. A rule that filled a floor from
    whatever was left would take the `world` stories first and publish them under
    a name this day says planned nothing. The rule that ships moves the five
    lowest-scoring `energy` stories and stops.
    """
    day = gated_day()
    closed = frozenset({"world"})

    assert filed(day) == {"ai": 21, "energy": 1, "business-economy": 2}

    out = refile(stream_order(day), bounds=BOUNDS, closed=closed)
    counted = filed(out)

    assert len(out) == len(day)
    assert counted == {"ai": 16, "energy": 6, "business-economy": 2}
    assert "world" not in counted, "a desk this run refused to render published stories"
    assert counted["business-economy"] < BOUNDS["business-economy"].floor, (
        "the desk whose stories were all too old must publish thin rather than be filled"
    )
    moved = {item.item_id for item in out if item.desk == "energy"} - {"energy-own-00"}
    assert moved == {f"energy-relabelled-{index:02d}" for index in range(1, 6)}, (
        "the ceiling gives up a desk's lowest-scoring stories, not its best"
    )


def test_a_ceiling_with_nowhere_to_send_the_overflow_does_not_shorten_the_day() -> None:
    """A story with no second desk stays where it is, however crowded the desk.

    Every story's only desk is the desk its own feed declares, so none of them
    has a second desk to fall back to. `india` is over its ceiling and stays
    over it. The one thing that may not happen is the day getting shorter, and
    that is what this asserts.
    """
    day = [
        story(f"india-solo-{index:02d}", vertical="india", source_id=f"feed-{index}",
              rank_score=100.0 - index)
        for index in range(30)
    ]
    out = refile(stream_order(day), bounds=BOUNDS)

    assert len(out) == 30
    assert filed(out) == {"india": 30}
    assert [item.item_id for item in out] == [item.item_id for item in stream_order(day)]


def test_no_committed_day_moves_because_no_story_has_a_second_desk() -> None:
    """Nothing read an article yet, so `desk` is null and the rules are inert.

    Measured 2026-09-13 over the committed archive: 0 of 9,353 items carry a
    read desk. This is that fact as a property rather than as a count, driven
    from a built day so it cannot go stale or grow more expensive.
    """
    day = [
        story(f"{DESKS[index % 5]}-null-{index:02d}", vertical=DESKS[index % 5],
              source_id=f"feed-{index}", rank_score=100.0 - index)
        for index in range(40)
    ]
    out = refile(stream_order(day), bounds=BOUNDS)

    assert all(item.desk is None for item in out)
    assert filed(out) == filed(day)


def test_a_desk_never_dips_under_its_own_floor_to_lift_another_one() -> None:
    """Robbing one desk to open another is two thin desks, not one full one.

    Six `energy` stories read onto `ai`, and two `ai` stories of its own. `ai`
    may give up two before it hits its own floor of six, which would leave
    `energy` at two and `ai` at six - both thin, where one was full. So the
    floor does not start a move it cannot finish and nothing moves at all.
    """
    day = [
        story(f"energy-give-{index:02d}", vertical="energy", desk="ai", source_id=f"feed-e{index}",
              rank_score=100.0 - index)
        for index in range(6)
    ] + [
        story(f"ai-own-{index:02d}", vertical="ai", desk="ai", source_id=f"feed-a{index}",
              rank_score=50.0 - index)
        for index in range(2)
    ]
    out = refile(stream_order(day), bounds={"ai": DeskBounds(floor=6, ceiling=1.0),
                                            "energy": DeskBounds(floor=6, ceiling=1.0)})

    assert len(out) == 8
    assert filed(out) == {"ai": 8}


def test_a_thin_day_is_spread_rather_than_drained() -> None:
    """The floor and the ceiling cannot contradict each other on a small day.

    Five desks at a floor of six need thirty stories, and a quarter of a
    twenty-story day is five. A desk may always hold its floor whatever its
    share says, which is the arithmetic `rank.day_source_ceiling` already uses
    for the per-feed case, and it is what stops the two rules disagreeing.

    Thirty stories, six per desk's feeds, every one read onto `ai`. The ceiling
    brings `ai` down to its share of ten, the floor takes the four desks it
    opened the last story each to six, and the day lands on the only shape that
    satisfies both.
    """
    day = [
        story(f"{DESKS[index % 5]}-thin-{index:02d}", vertical=DESKS[index % 5], desk="ai",
              source_id=f"feed-{index}", rank_score=100.0 - index)
        for index in range(30)
    ]
    out = refile(stream_order(day), bounds=BOUNDS)

    assert len(out) == 30
    assert filed(out) == dict.fromkeys(DESKS, 6)
