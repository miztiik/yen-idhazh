"""The day's leading stories: what leads, what a cap costs, and what the block says.

Unit and integration tier (CLAUDE.md section 13). Nothing here is mocked and no
test touches the network: the arithmetic runs over stories built in the test,
and the invariants run over the committed days on disk.

The one thing every test here is defending is the promise in
`docs/concepts/digest.md`: the block adds a way into the day and removes
nothing. Every story a rule turns away is still in `items`, in the published
order, marked exactly as it was.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, REPO_ROOT, read_text

from idhazh.assemble import leading_stories, subject_clusters
from idhazh.contracts.app_config import UiConfig
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.run_plan import TimeSource
from idhazh.contracts.taxonomy import SourceKind
from idhazh.contracts.watchlist import EntityDef, Watchlist

DIGEST_ROOT = REPO_ROOT / "frontend" / "public" / "digest"

DESKS = {
    "ai": "AI",
    "energy": "Energy",
    "world": "World",
    "india": "India",
    "business-economy": "Business",
}


def watchlist(*entries: tuple[str, str, list[str]]) -> Watchlist:
    return Watchlist(
        version=Watchlist.schema_version(),
        entities=[
            EntityDef(id=slug, display_name=name, aliases=aliases)
            for slug, name, aliases in entries
        ],
    )


REGISTRY = watchlist(
    ("nvidia", "Nvidia", ["nvidia"]),
    ("openai", "OpenAI", ["openai"]),
    ("apple", "Apple", ["apple"]),
)

EMPTY = watchlist()


def story(
    item_id: str,
    *,
    vertical: str = "ai",
    source_id: str = "feed-a",
    title: str = "Something happened",
    rank_score: float | None = 1.0,
    carried_by: int | None = 1,
    band: ConfidenceBand = ConfidenceBand.HIGH,
    truncated: bool = False,
    published_at: str | None = "2026-08-31T09:00:00Z",
    time_source: TimeSource | None = TimeSource.FEED,
    source_kind: SourceKind = SourceKind.REPORTING,
) -> DigestItem:
    """One published story, with every field the block reads set explicitly."""
    return DigestItem(
        item_id=item_id,
        vertical=vertical,
        title=title,
        source_url=f"https://example.test/{item_id}",
        source_id=source_id,
        source_name=source_id,
        source_kind=source_kind,
        published_at=published_at,
        time_source=time_source,
        summary="A summary.",
        key_points=["A point."],
        band=band,
        truncated=truncated,
        introduced_by_run=1,
        carried_by=carried_by,
        rank_score=rank_score,
    )


def five_desks(**overrides: object) -> list[DigestItem]:
    """One eligible story on each of five desks, descending by score.

    Every one of them is the lead story of its own desk, so every one carries
    the desk sentence and the block fills without any subject at all.
    """
    return [
        story(
            f"{desk}-{index:010d}",
            vertical=desk,
            source_id=f"feed-{desk}",
            title=f"A story on {desk}",
            rank_score=2.0 - index / 10,
            **overrides,  # type: ignore[arg-type]
        )
        for index, desk in enumerate(DESKS)
    ]


def choose(items: list[DigestItem], *, wl: Watchlist = EMPTY, **knobs: object) -> list[str]:
    leads = leading_stories(
        items,
        date="2026-08-31",
        watchlist=wl,
        ui=UiConfig(**knobs),  # type: ignore[arg-type]
        desk_names=DESKS,
    )
    return [lead.item_id for lead in leads]


def reasons(items: list[DigestItem], *, wl: Watchlist = EMPTY, **knobs: object) -> dict[str, str]:
    leads = leading_stories(
        items,
        date="2026-08-31",
        watchlist=wl,
        ui=UiConfig(**knobs),  # type: ignore[arg-type]
        desk_names=DESKS,
    )
    return {lead.item_id: lead.reason for lead in leads}


# --- the block's shape ------------------------------------------------------


def test_the_block_holds_the_configured_count_and_never_more() -> None:
    """Ten eligible stories, two on each of five desks, and five leads."""
    items = [
        story(
            f"{desk}-{index * 10 + rank:010d}",
            vertical=desk,
            source_id=f"feed-{desk}-{rank}",
            rank_score=2.0 - index / 10 - rank / 100,
            carried_by=2,
        )
        for index, desk in enumerate(DESKS)
        for rank in range(2)
    ]
    assert len(choose(items)) == UiConfig().leading_stories


def test_the_block_takes_the_strongest_stories_and_not_the_head_of_the_order() -> None:
    """Finding 1: the published order opens on whichever desk sorted first.

    The list handed in is deliberately in the worst order the payload can be
    in - the weakest desk first - and the block still opens on the strongest
    story.
    """
    items = list(reversed(five_desks()))
    assert choose(items)[0] == "ai-0000000000"


def test_below_the_minimum_the_block_does_not_render() -> None:
    """Four real leads beat five with one filler, and two beat three."""
    assert choose(five_desks()[:2]) == []
    assert len(choose(five_desks()[:3])) == 3


def test_a_desk_may_not_hold_more_than_its_share() -> None:
    items = [
        story(
            f"ai-{index:010d}",
            source_id=f"feed-{index}",
            rank_score=2.0 - index / 10,
            carried_by=2,
        )
        for index in range(4)
    ] + five_desks()[1:]
    chosen = choose(items)
    assert sum(1 for item_id in chosen if item_id.startswith("ai-")) == UiConfig().leading_per_desk


def test_one_publication_may_hold_one_lead() -> None:
    """Otherwise a busy newsroom is the whole first screen."""
    items = [
        story(
            f"{desk}-{index:010d}",
            vertical=desk,
            source_id="one-newsroom",
            rank_score=2.0 - index / 10,
        )
        for index, desk in enumerate(DESKS)
    ]
    assert len(choose(items)) == 0, "one source cannot fill a block on its own"


def test_one_subject_may_hold_one_lead_however_many_desks_it_crosses() -> None:
    """The fourth cap, and the reason it is a cap rather than a decay.

    A running story crosses desks and sources, so the first three caps do not
    bound it: three of five would clear all of them.
    """
    items = [
        story(
            f"{desk}-{index:010d}",
            vertical=desk,
            source_id=f"feed-{index}",
            title="Nvidia does something",
            rank_score=2.0 - index / 10,
        )
        for index, desk in enumerate(DESKS)
    ]
    assert len(choose(items, wl=REGISTRY)) == 0, "one subject cannot fill a block"


def test_a_second_story_dated_yesterday_is_refused() -> None:
    """One late arrival is a catch-up; five are yesterday's page.

    With every story dated yesterday only one may lead, which puts the block
    under its own minimum - so the day goes straight to the stream.
    """
    items = [
        story(
            f"{desk}-{index:010d}",
            vertical=desk,
            source_id=f"feed-{index}",
            rank_score=2.0 - index / 10,
            published_at="2026-08-30T09:00:00Z",
        )
        for index, desk in enumerate(DESKS)
    ]
    assert choose(items) == []
    assert len(choose(items, lead_max_yesterday=5)) == UiConfig().leading_stories


def test_every_lead_names_a_story_the_day_holds() -> None:
    items = five_desks()
    chosen = set(choose(items))
    assert chosen <= {item.item_id for item in items}


def test_two_builds_of_one_day_choose_the_same_five() -> None:
    """The tie-break is the item id, which is derived from the address."""
    items = five_desks()
    assert choose(items) == choose(list(reversed(items)))


# --- eligibility ------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("band", ConfidenceBand.LOW),
        ("truncated", True),
        ("time_source", TimeSource.FIRST_SEEN),
    ],
)
def test_an_ineligible_story_never_leads_however_it_ranks(field: str, value: object) -> None:
    """Each rule excludes regardless of rank, and the story still publishes."""
    items = five_desks()
    strongest = items[0].model_copy(update={field: value, "rank_score": 99.0})
    items[0] = strongest
    assert strongest.item_id not in choose(items)


def test_a_story_with_no_time_at_all_cannot_lead() -> None:
    """`time_source` and `published_at` move together in the contract."""
    items = five_desks()
    items[0] = items[0].model_copy(
        update={"published_at": None, "time_source": TimeSource.UNKNOWN, "rank_score": 99.0}
    )
    assert items[0].item_id not in choose(items)


def test_an_announcement_leads_only_where_somebody_reported_the_same_subject() -> None:
    items = five_desks()
    items[0] = items[0].model_copy(
        update={"source_kind": SourceKind.ANNOUNCEMENT, "rank_score": 99.0}
    )
    assert items[0].item_id not in choose(items)

    corroborated = items[0].model_copy(update={"title": "Nvidia ships a chip"})
    reporter = story(
        "world-0000000099",
        vertical="world",
        source_id="a-newsroom",
        title="Nvidia ships a chip, say analysts",
        rank_score=0.1,
    )
    assert corroborated.item_id in choose([corroborated, *items[1:], reporter], wl=REGISTRY)


def test_an_excluded_story_is_still_in_the_day() -> None:
    """ESCALATE trigger (a): nothing may be dropped, hidden or unpublished.

    The block is a list of ids over a list the day already holds, so this is
    what the whole design rests on - a rule here can only decide what is at the
    top, never what exists.
    """
    items = five_desks()
    items[0] = items[0].model_copy(update={"band": ConfidenceBand.LOW})
    leads = leading_stories(
        items, date="2026-08-31", watchlist=EMPTY, ui=UiConfig(), desk_names=DESKS
    )
    day = DigestDay(
        version=DigestDay.schema_version(),
        date="2026-08-31",
        generated_at="2026-08-31T10:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at="2026-08-31T10:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=desk, display_name=name, count=1)
            for desk, name in DESKS.items()
        ],
        items=items,
        leads=leads,
    )
    assert items[0].item_id in {item.item_id for item in day.items}
    assert items[0].item_id not in {lead.item_id for lead in day.leads}


# --- the shared-subject term ------------------------------------------------


def carriers(
    entity: str, count: int, *, kind: SourceKind = SourceKind.REPORTING
) -> list[DigestItem]:
    return [
        story(
            f"world-{900 + index:010d}",
            vertical="world",
            source_id=f"carrier-{index}",
            title=f"{entity} in the news",
            rank_score=0.5,
            source_kind=kind,
        )
        for index in range(count)
    ]


def test_a_subject_under_the_floor_earns_nothing() -> None:
    below = subject_clusters(carriers("Nvidia", 2), REGISTRY)
    assert [cluster.qualifies(3) for cluster in below] == [False]
    at_floor = subject_clusters(carriers("Nvidia", 3), REGISTRY)
    assert [cluster.qualifies(3) for cluster in at_floor] == [True]


def test_one_source_filing_four_pieces_is_one_source() -> None:
    """Decision 2: one item per source per entity."""
    filed = [
        story(
            f"world-{index:010d}",
            vertical="world",
            source_id="one-newsroom",
            title="Nvidia in the news",
        )
        for index in range(4)
    ]
    cluster = subject_clusters(filed, REGISTRY)[0]
    assert len(cluster.sources) == 1
    assert len(cluster.item_ids) == 4
    assert cluster.qualifies(3) is False


def test_a_cluster_of_announcements_is_a_press_schedule_and_not_a_story() -> None:
    announced = subject_clusters(carriers("Nvidia", 4, kind=SourceKind.ANNOUNCEMENT), REGISTRY)
    assert [cluster.qualifies(3) for cluster in announced] == [False]


def test_a_story_naming_two_subjects_takes_the_larger_weight_and_never_the_sum() -> None:
    """The rule the lens bonus already follows.

    Two of the day's subjects in one title is not twice the story. The check is
    that one weight is all it can buy: a rival scoring one weight plus a whisker
    higher still leads, which it could not if the two subjects were summed.
    """
    weight = UiConfig().lead_shared_subject_weight
    both = story(
        "ai-0000000000",
        title="Nvidia and OpenAI announce a deal",
        rank_score=1.0,
        source_id="lead-feed",
    )
    rival = story(
        "energy-0000000000",
        vertical="energy",
        title="A reactor is ordered",
        rank_score=1.0 + weight + 0.01,
        source_id="rival-feed",
        carried_by=2,
    )
    openai_carriers = [
        entry.model_copy(update={"item_id": f"india-{index:010d}", "vertical": "india"})
        for index, entry in enumerate(carriers("OpenAI", 3))
    ]
    chosen = choose(
        [both, rival, *carriers("Nvidia", 3), *openai_carriers], wl=REGISTRY, leading_min=1
    )
    assert chosen[0] == rival.item_id, (
        "a story naming two running subjects outranked a rival worth one weight "
        "more, so the term is being summed rather than taken at its ceiling"
    )
    assert both.item_id in chosen


# --- the why-line -----------------------------------------------------------


def test_the_strongest_true_sentence_wins() -> None:
    """The order Editor set, checked one preference at a time."""
    subject = story(
        "ai-0000000000", title="Nvidia ships a chip", rank_score=3.0, source_id="lead-feed"
    )
    told = reasons([subject, *carriers("Nvidia", 3), *five_desks()[1:]], wl=REGISTRY)
    assert told[subject.item_id] == "Four of today's stories are about Nvidia."


def test_a_watchlist_name_is_the_sentence_when_the_subject_is_not_running() -> None:
    named = story(
        "ai-0000000000", title="Apple does something", rank_score=3.0, source_id="lead-feed"
    )
    told = reasons([named, *five_desks()[1:]], wl=REGISTRY)
    assert told[named.item_id] == "Apple is on our watchlist."


def test_a_carried_address_says_how_it_reached_us_and_never_who_covered_it() -> None:
    """`carried_by` counts syndication of one address, so the sentence says so."""
    carried = story("ai-0000000000", rank_score=3.0, carried_by=3, source_id="lead-feed")
    told = reasons([carried, *five_desks()[1:]])
    assert told[carried.item_id] == "The same report reached us through three of our feeds."


def test_the_desk_sentence_is_only_true_of_the_desks_own_lead() -> None:
    """It is the fallback, and it still has to be true.

    A story that is not the strongest on its desk cannot say it is, so it
    carries no sentence - and a lead with nothing true to say is not a lead.
    """
    strongest = story("ai-0000000000", rank_score=3.0, source_id="feed-one")
    second = story("ai-0000000001", rank_score=2.5, source_id="feed-two")
    told = reasons([strongest, second, *five_desks()[1:]])
    assert told[strongest.item_id] == "The lead story on our AI desk."
    assert second.item_id not in told


def test_a_lead_that_cannot_say_anything_true_is_not_a_lead() -> None:
    weak = story("ai-0000000009", rank_score=0.1, source_id="feed-nine")
    assert weak.item_id not in choose([weak, *five_desks()])


def test_a_count_reads_as_a_word_up_to_twelve_and_as_a_numeral_above_it() -> None:
    subject = story(
        "ai-0000000000", title="OpenAI does something", rank_score=3.0, source_id="lead-feed"
    )
    many = [
        entry.model_copy(update={"item_id": f"india-{index:010d}", "vertical": "india"})
        for index, entry in enumerate(carriers("OpenAI", 13))
    ]
    told = reasons([subject, *many, *five_desks()[1:]], wl=REGISTRY)
    assert told[subject.item_id] == "14 of today's stories are about OpenAI."


def test_no_sentence_is_offered_for_recency_or_for_a_weighted_lens() -> None:
    """Decision 11, as a check on what the block says rather than on a comment.

    The rail already prints the time, and a weighted lens is an editorial
    subsidy for an under-carried theme - a sentence about it would tell the
    reader about our config rather than about the news. So a story whose only
    distinguishing fact is that it is newer says nothing, and does not lead.
    """
    lead = story("ai-0000000000", rank_score=3.0, source_id="feed-one")
    newer = story(
        "ai-0000000001",
        rank_score=2.9,
        source_id="feed-two",
        published_at="2026-08-31T23:00:00Z",
    )
    told = reasons([lead, newer, *five_desks()[1:]])
    assert told[lead.item_id] == "The lead story on our AI desk."
    assert newer.item_id not in told


def test_the_front_page_vote_is_not_a_sentence() -> None:
    """Measured 2026-09-01: `on_front_page` is false on all 490 committed
    stories that record it and absent on the other 3,596.

    It also cannot name its own source. The flag says a salience feed voted,
    and the two active ones are `Hacker News front page` and `Hacker News
    best` - so a sentence naming the front page is false whenever the other
    one voted, which is the falsity the row's own rejected alternative 4 rules
    out. What a reader loses is a line on about one story in 160; the sentence
    below it in the order takes its place.
    """
    voted = story("ai-0000000000", rank_score=3.0, source_id="feed-one")
    told = reasons([voted.model_copy(update={"on_front_page": True}), *five_desks()[1:]])
    assert told[voted.item_id] == "The lead story on our AI desk."


# --- the counters -----------------------------------------------------------


def test_the_block_records_its_line_coverage(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="idhazh"):
        choose(five_desks())
    assert any("coverage=" in record.getMessage() for record in caplog.records)


def test_a_notable_story_left_out_says_which_rule_left_it_out(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Decision 15's omission log.

    No story a reader could see the case for is absent from the block without
    the build log naming the rule.
    """
    notable = story(
        "world-0000000099",
        vertical="world",
        source_id="carrier-0",
        title="Nvidia in the news",
        rank_score=0.01,
        carried_by=4,
    )
    with caplog.at_level(logging.INFO, logger="idhazh"):
        choose([notable, *carriers("Nvidia", 3), *five_desks()], wl=REGISTRY)
    said = " ".join(record.getMessage() for record in caplog.records)
    assert f"omitted item={notable.item_id} because=" in said


# --- the committed days -----------------------------------------------------


def committed_days() -> list[Path]:
    return sorted(DIGEST_ROOT.rglob("digest.json"))


@pytest.mark.parametrize("path", committed_days(), ids=lambda p: p.parent.name)
def test_every_committed_day_yields_a_block_inside_its_own_rules(path: Path) -> None:
    """The Oracle, run over real published days rather than over a mock.

    A day published before the ranking signal existed draws no block at all,
    because every story reads `time_source: null` and a lead may only lead on
    the feed's own clock. That is the null-is-unknown rule working, not a
    failure.
    """
    day = DigestDay.from_json(read_text(path))
    ui = UiConfig()
    registry = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    leads = leading_stories(
        day.items, date=day.date, watchlist=registry, ui=ui, desk_names=DESKS
    )
    by_id = {item.item_id: item for item in day.items}

    assert len(leads) <= ui.leading_stories
    assert len(leads) == 0 or len(leads) >= ui.leading_min, "the block never pads"
    assert {lead.item_id for lead in leads} <= set(by_id), "a lead names a story the day holds"

    chosen = [by_id[lead.item_id] for lead in leads]
    for desk in {item.vertical for item in chosen}:
        assert sum(1 for item in chosen if item.vertical == desk) <= ui.leading_per_desk
    assert len({item.source_id for item in chosen}) == len(chosen), "one lead per publication"

    titles = subject_clusters(day.items, registry)
    per_subject: dict[str, int] = {}
    for cluster in titles:
        held = sum(1 for item in chosen if item.item_id in cluster.item_ids)
        per_subject[cluster.entity] = held
    assert all(held <= 1 for held in per_subject.values()), "one lead per subject"

    assert all(lead.reason.strip() for lead in leads), "every lead says why it leads"


def test_a_committed_day_that_carries_the_signal_fills_the_block() -> None:
    """The row's oracle, on the newest committed day that records a rank score.

    Bound to the data rather than to a date: the pipeline publishes every day,
    and a test naming one of them stops meaning anything the moment that day
    ages out of the retention window.
    """
    scored = [
        day
        for day in (DigestDay.from_json(read_text(path)) for path in committed_days())
        if any(item.rank_score is not None for item in day.items)
    ]
    if not scored:
        pytest.skip("no committed day records a rank score yet")
    day = scored[-1]
    registry = Watchlist.from_json(read_text(CONFIG_DIR / "watchlist.json"))
    leads = leading_stories(
        day.items, date=day.date, watchlist=registry, ui=UiConfig(), desk_names=DESKS
    )
    assert len(leads) == UiConfig().leading_stories, (
        f"{day.date} publishes {len(day.items)} stories and fills only {len(leads)} leads"
    )


def test_no_committed_day_carries_a_block_it_did_not_publish() -> None:
    """A day written before this existed reads as no block, never as a broken one."""
    for path in committed_days():
        payload = json.loads(read_text(path))
        day = DigestDay.from_json(read_text(path))
        assert day.leads == [] or "leads" in payload
