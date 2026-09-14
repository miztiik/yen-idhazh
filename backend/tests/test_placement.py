"""The day's one order, the frame a person set over its head, and the desk rules.

Unit tier (CLAUDE.md section 13). Nothing here is mocked, no test touches the
network, and nothing reads the committed archive: every day below is built in
the test, including the day this plan needs and the archive has never produced -
one desk holding 18 of the top 20, one feed holding 9 of the top 10, and a day
whose every story reads AI (Guardrail #12).

What every test here defends is one sentence: **the frame moves a story and
never removes one.** A cap that drops rather than displaces shortens the day,
and a reader cannot see what was left out. The desk floor and the desk ceiling
obey the same sentence - they change which desk a story is filed under and
nothing else.
"""

from __future__ import annotations

from collections import Counter

import pytest

from idhazh.contracts.app_config import PlacementConfig
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy, VerticalDef
from idhazh.placement import (
    DeskBounds,
    desk_bounds,
    place,
    refile,
    secondary_desk_of,
    stream_order,
)

#: The five desks the taxonomy declares today.
DESKS = ("india", "world", "ai", "energy", "business-economy")

#: The floor and the ceiling the Editor ruled on 2026-09-13, as
#: `config/taxonomy.json` carries them. Repeated here rather than read off the
#: file, so a test that fails says which of the two moved.
BOUNDS = {
    "ai": DeskBounds(floor=6, ceiling=0.35),
    "energy": DeskBounds(floor=6, ceiling=0.25),
    "business-economy": DeskBounds(floor=6, ceiling=0.25),
    "world": DeskBounds(floor=6, ceiling=0.4),
    "india": DeskBounds(floor=6, ceiling=0.4),
}


def story(
    item_id: str,
    *,
    vertical: str,
    source_id: str,
    rank_score: float | None,
    desk: str | None = None,
    secondary_desk: str | None = None,
    published_at: str | None = "2026-09-13T09:00:00Z",
    introduced_by_run: int = 1,
) -> DigestItem:
    """One published story, with every field the frame reads set explicitly."""
    return DigestItem(
        item_id=item_id,
        vertical=vertical,
        desk=desk,
        secondary_desk=secondary_desk,
        title="Something happened",
        source_url=f"https://example.test/{item_id}",
        source_id=source_id,
        source_name=source_id,
        summary="A summary.",
        key_points=["A point."],
        band=ConfidenceBand.HIGH,
        introduced_by_run=introduced_by_run,
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


def heavy_ai_day() -> list[DigestItem]:
    """Forty stories, every one of which reads AI, carried by five desks' feeds.

    The day plan 23 row #6 makes possible and the archive has never produced: a
    model reads every article onto one desk while the feeds that carried them
    are spread across five. Without the ceiling this is a one-desk digest with
    four empty rails, on exactly the day a reader most needs the other four.
    """
    return [
        story(
            f"{DESKS[index % 5]}-heavy-{index:02d}",
            vertical=DESKS[index % 5],
            desk="ai",
            source_id=f"feed-{index}",
            rank_score=100.0 - index,
        )
        for index in range(40)
    ]


def gated_day() -> list[DigestItem]:
    """A day where two thin desks can only be filled from something refused.

    `world` is thin because this run found fewer live feeds than its floor, so
    it planned nothing and will render nothing - five stories its feeds carried
    on an earlier run are in the day, relabelled onto `ai`, and sending them back
    would publish under a name this day's own payload says planned nothing.
    `business-economy` is thin because what would have filled it was past
    `collect.max_age_hours`, so it never became a story at all and nothing in the
    day names that desk.

    The only lawful supply is the six `energy` stories relabelled onto `ai`. A
    naive rule that filled a floor from whatever was left would reach the five
    `world` stories first, because they outscore the day's tail.
    """
    day = [
        story(f"ai-bulk-{index:02d}", vertical="ai", desk="ai", source_id=f"feed-a{index}",
              rank_score=100.0 - index)
        for index in range(10)
    ]
    day += [
        story(f"energy-relabelled-{index:02d}", vertical="energy", desk="ai",
              source_id=f"feed-e{index}", rank_score=90.0 - index)
        for index in range(6)
    ]
    day += [
        story(f"world-relabelled-{index:02d}", vertical="world", desk="ai",
              source_id=f"feed-w{index}", rank_score=84.0 - index)
        for index in range(5)
    ]
    day.append(
        story("energy-own-00", vertical="energy", desk="energy", source_id="feed-e9",
              rank_score=79.0)
    )
    day += [
        story(f"business-economy-own-{index:02d}", vertical="business-economy",
              desk="business-economy", source_id=f"feed-b{index}", rank_score=78.0 - index)
        for index in range(2)
    ]
    return day


def filed(items: list[DigestItem]) -> Counter[str]:
    return Counter(desk_of(item) for item in items)


def placed(
    day: list[DigestItem],
    *,
    config: PlacementConfig,
    bounds: dict[str, DeskBounds] | None = None,
) -> list[DigestItem]:
    """`place`, with the four promises its own docstring makes checked every call.

    Call this rather than `place` directly. The promises hold whatever the config
    says and whatever the day looks like, so a test about the desk ceiling checks
    them as cheaply as a test about the head - and a test written next year for
    some other reason inherits every one of them without knowing they exist.

    That is the difference between a rule and a control. All four were written
    down before 2026-09-13 and the one about a later run was written in three
    places; what was missing was somewhere they went red.
    """
    out = place(day, config=config, bounds=bounds)

    assert len(out) == len(day), "a cap shortened the day, and a reader cannot see what is missing"
    assert {item.item_id for item in out} == {item.item_id for item in day}, (
        "the day came back holding stories it was not handed"
    )
    runs = [item.introduced_by_run for item in out]
    assert runs == sorted(runs), "a later run's story moved above one a reader had already read"
    assert filed(out) == filed(refile(stream_order(day), bounds=bounds or {})), (
        "the desk rules were applied to one run's block rather than to the day"
    )
    return out


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


# --- What the frame may never do -------------------------------------------


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


# --- A later run appends ----------------------------------------------------


def day_over_two_runs(first: int = 24, second: int = 12) -> list[DigestItem]:
    """A day whose second run published every story worth reading, on a crowded desk.

    Run 2 outscores every story run 1 published, which is the case one sort over
    the whole day gets wrong and the case the committed archive cannot supply -
    the archive was written before this file existed.

    Every story reads `ai` while the feeds that carried them span five desks, so
    the desk floor and the desk ceiling have real work to do here and not only in
    `heavy_ai_day`. That is deliberate: `place` is the only thing that decides
    whether those rules see the whole day or one run's block, and a two-run day
    with nothing for them to do cannot tell the difference. Distinct feeds
    throughout, so the no-repeat window is never what binds.
    """
    return [
        *(
            story(
                f"{DESKS[index % len(DESKS)]}-first-{index:02d}",
                vertical=DESKS[index % len(DESKS)],
                desk="ai",
                source_id=f"feed-first-{index}",
                rank_score=10.0 - index * 0.1,
                introduced_by_run=1,
            )
            for index in range(first)
        ),
        *(
            story(
                f"{DESKS[index % len(DESKS)]}-second-{index:02d}",
                vertical=DESKS[index % len(DESKS)],
                desk="ai",
                source_id=f"feed-second-{index}",
                rank_score=100.0 - index * 0.1,
                introduced_by_run=2,
            )
            for index in range(second)
        ),
    ]


def test_a_later_run_appends_however_well_it_scored() -> None:
    """The rule `DigestDay` refuses a payload for breaking, held here first.

    Every story run 2 published outscores every story run 1 did, so one sort
    over the whole day would put twelve stories a reader has never seen above
    twenty-four they may have read at breakfast. `introduced_by_run` never
    decreasing down the list is that refusal made mechanical
    (`docs/architecture/contracts/schemas.md`).
    """
    day = day_over_two_runs()
    out = placed(day, config=frame(), bounds=BOUNDS)

    introduced = [item.introduced_by_run for item in out]
    assert introduced == sorted(introduced), "a later run's story moved above one already read"
    assert len(out) == len(day)
    assert {item.item_id for item in out} == {item.item_id for item in day}


def test_the_desk_rules_see_the_whole_day_and_not_one_runs_block() -> None:
    """A ceiling is a share of the day, so a day split in two is still one day.

    `refile` over the whole day is the answer, and `place` is the only caller
    that could get it wrong - it is the file that knows about blocks at all. Run
    the rules per block and `ai` is measured against 24 stories and then against
    12 rather than against 36, so the day publishes a filing nobody ruled on.

    `placed` already refuses that on every call. This names the day it happens on
    and the numbers it lands, so a failure says which rule moved.
    """
    day = day_over_two_runs()
    out = placed(day, config=frame(), bounds=BOUNDS)
    counted = filed(out)

    assert counted["ai"] <= int(BOUNDS["ai"].ceiling * len(day)), "ai is over the day's ceiling"
    assert set(counted) == set(DESKS), "the ceiling did not reach every desk it opened"
    assert counted == filed(refile(stream_order(day), bounds=BOUNDS))


def test_the_day_validates_as_a_payload_after_the_frame_has_run() -> None:
    """The contract itself is the oracle, because the contract is what broke.

    `DigestDay` refuses an order that is not append-only, so building one out of
    the placed items fails on any implementation that sorts the whole day.
    """
    day = day_over_two_runs()
    out = placed(day, config=frame(), bounds=BOUNDS)

    built = DigestDay(
        version=DigestDay.schema_version(),
        date="2026-09-13",
        generated_at="2026-09-13T19:00:00Z",
        partial=False,
        items_planned=len(out),
        items_failed=0,
        runs=[
            DigestRunRef(n=1, at="2026-09-13T09:00:00Z", items_added=24),
            DigestRunRef(n=2, at="2026-09-13T19:00:00Z", items_added=12),
        ],
        verticals=[
            DigestVerticalRef(
                id=desk,
                display_name=desk.replace("-", " ").title(),
                count=sum(1 for item in out if item.vertical == desk),
            )
            for desk in sorted({item.vertical for item in out})
        ],
        items=out,
    )

    assert [item.item_id for item in built.items] == [item.item_id for item in out]


def test_the_head_is_the_pages_head_and_not_each_blocks() -> None:
    """One framed head a day, at the top, filled by whoever got there first.

    A second framed head four hundred stories down is a rule applied where
    nobody meets it. Run 1 published more than `head_items`, so it takes every
    slot and run 2 is published in the score's own order.
    """
    day = day_over_two_runs()
    config = frame()
    out = placed(day, config=config, bounds=BOUNDS)

    assert all(item.introduced_by_run == 1 for item in out[: config.head_items])

    second = [item for item in out if item.introduced_by_run == 2]
    expected = stream_order([item for item in day if item.introduced_by_run == 2])
    assert [item.item_id for item in second] == [item.item_id for item in expected]


def test_a_thin_first_run_leaves_the_rest_of_the_head_to_the_second() -> None:
    """The head is a count of the day's slots, so a short first block does not waste them.

    Run 1 published five stories. The head is twenty, so fifteen slots are still
    open when run 2 lands and the frame goes on filling them - and the five run 1
    published still come first.
    """
    day = day_over_two_runs(first=5, second=30)
    config = frame()
    out = placed(day, config=config, bounds=BOUNDS)

    head = out[: config.head_items]
    assert [item.introduced_by_run for item in head] == [1] * 5 + [2] * 15
    assert max(Counter(desk_of(item) for item in head).values()) <= config.max_desk_in_head


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
    head = placed(day, config=config)[: config.head_items]

    assert Counter(desk_of(item) for item in head)["ai"] == 5


# --- The knobs are knobs ----------------------------------------------------


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


# --- The oracle: the desk floor and the desk ceiling -------------------------


def test_a_day_where_every_story_reads_ai_still_publishes_five_desks() -> None:
    """The first half of row #7's oracle, and the day is not one story shorter.

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


# --- The oracle: a story cross-files to a second desk ------------------------


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


# --- The desk knobs are knobs -----------------------------------------------


def test_changing_a_ceiling_changes_the_filing_with_no_source_edit() -> None:
    """Guardrail #6's substitution test, run on the desk ceiling."""
    day = heavy_ai_day()
    ruled = filed(refile(stream_order(day), bounds=BOUNDS))
    tighter = filed(
        refile(stream_order(day), bounds={**BOUNDS, "ai": DeskBounds(floor=6, ceiling=0.2)})
    )

    assert ruled["ai"] == 14
    assert tighter["ai"] == 8
    assert sum(ruled.values()) == sum(tighter.values()) == 40


def test_changing_a_floor_changes_the_filing_with_no_source_edit() -> None:
    day = gated_day()
    ruled = filed(refile(stream_order(day), bounds=BOUNDS, closed=frozenset({"world"})))
    raised = filed(
        refile(
            stream_order(day),
            bounds={**BOUNDS, "energy": DeskBounds(floor=3, ceiling=0.25)},
            closed=frozenset({"world"}),
        )
    )

    assert ruled["energy"] == 6
    assert raised["energy"] == 6, "the ceiling still admits six, and a lower floor asks for fewer"
    assert sum(ruled.values()) == sum(raised.values()) == 24


def test_a_desk_with_no_rule_may_hold_the_whole_day() -> None:
    """An absent rule is no rule, so the defaults are the two identity values."""
    default = VerticalDef(id="ai", display_name="AI", definition="A desk.", min_feeds=21)

    assert (default.floor, default.ceiling) == (0, 1.0)

    day = heavy_ai_day()
    out = refile(stream_order(day), bounds={})

    assert filed(out) == {"ai": 40}


def test_the_bounds_come_off_the_taxonomy_including_a_retired_desk() -> None:
    """A day published last month can still hold a desk this file has retired.

    Leaving it out would hand that desk no rule rather than the rule it had,
    which on a heavy day is the difference between a ceiling and none.
    """
    taxonomy = Taxonomy(
        version=Taxonomy.schema_version(),
        verticals=[
            VerticalDef(id="ai", display_name="AI", definition="A desk.", min_feeds=21,
                        floor=6, ceiling=0.35),
            VerticalDef(id="legacy", display_name="Legacy", min_feeds=21, floor=4, ceiling=0.1,
                        status=LifecycleStatus.RETIRED, retired_on="2026-04-12"),
        ],
        lenses=[],
        events=[],
    )

    assert desk_bounds(taxonomy) == {
        "ai": DeskBounds(floor=6, ceiling=0.35),
        "legacy": DeskBounds(floor=4, ceiling=0.1),
    }
