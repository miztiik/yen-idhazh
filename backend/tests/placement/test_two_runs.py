"""When a later run appends, what may move and what may never?"""

from __future__ import annotations

from collections import Counter

from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.placement import refile, stream_order

from ._days import (
    BOUNDS,
    DESKS,
    desk_of,
    filed,
    frame,
    placed,
    story,
)


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
