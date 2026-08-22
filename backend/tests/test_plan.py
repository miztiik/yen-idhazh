"""Integration-tier tests for the plan stage - the day, decided before any weights load.

`stage_plan` is the one stage that reads the open web and the one stage nothing
tested. Every rule about freshness, identity and feed health is about to be
written into it, so it gets its safety net first.

The two seams `cli` exposes are what make this possible. The fetcher is a
callable, so a test drives it from `tests/fixtures/feeds/` - a real function
reading a real captured file, not a mock (Holy Law #7). The clock is a callable,
so a rule about how old an article is has a fixed `now` and cannot change its
answer at midnight.

Several tests here record behaviour that is wrong and about to change. Each says
so, and names the item that changes it. A characterization test is how you prove
the net can see the bug before you fix it.
"""

from __future__ import annotations

import dataclasses
import json

import pytest
from conftest import FIXTURES_DIR, read_text

from idhazh import cli, config, fetch
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.sources import FeedDef, SalienceFeedDef, Sources
from idhazh.contracts.taxonomy import LifecycleStatus, SourceTier, VerticalDef

FEEDS = FIXTURES_DIR / "feeds"

LAB_URL = "https://blog.example-lab.org/feed"
TRADE_URL = "https://trade.example-press.net/feed"
COMMUNITY_URL = "https://community.example.org/feed"
QUIET_URL = "https://quiet.example.org/feed"
NOTICES_URL = "https://notices.example.gov/feed"
FORWARD_URL = "https://forward.example-press.net/feed"
FRONT_PAGE_URL = "https://salience.example.org/feed"

MODEL_RELEASE = "https://blog.example-lab.org/2026/08/model-release"

LAB = FeedDef(
    id="lab-blog",
    vertical="ai",
    title="Example Lab",
    url=LAB_URL,
    tier=SourceTier.INSTITUTION,
)
TRADE = FeedDef(
    id="trade-press",
    vertical="ai",
    title="Example Trade Press",
    url=TRADE_URL,
    tier=SourceTier.TRADE_PRESS,
)
COMMUNITY = FeedDef(
    id="community",
    vertical="ai",
    title="Example Community",
    url=COMMUNITY_URL,
    tier=SourceTier.COMMUNITY,
)
QUIET = FeedDef(
    id="quiet-desk",
    vertical="ai",
    title="Example Quiet Desk",
    url=QUIET_URL,
    tier=SourceTier.TRADE_PRESS,
)
NOTICES = FeedDef(
    id="notices",
    vertical="ai",
    title="Example Undated Notices",
    url=NOTICES_URL,
    tier=SourceTier.INSTITUTION,
)
FORWARD = FeedDef(
    id="forward",
    vertical="ai",
    title="Example Forward Dating",
    url=FORWARD_URL,
    tier=SourceTier.TRADE_PRESS,
)
FRONT_PAGE = SalienceFeedDef(
    id="front-page",
    title="Example Front Page",
    url=FRONT_PAGE_URL,
)

AI = VerticalDef(id="ai", display_name="AI", daily_cap=5, min_feeds=3)

#: A fixed morning. Every date in the fixtures is placed relative to it.
NOW = "2026-08-22T06:00:00Z"
DATE = "2026-08-22"

BODIES = {
    LAB_URL: "lab-blog.xml",
    TRADE_URL: "trade-press.xml",
    COMMUNITY_URL: "community.atom",
    QUIET_URL: "empty.xml",
    NOTICES_URL: "undated.xml",
    FORWARD_URL: "future-dated.xml",
    FRONT_PAGE_URL: "front-page.xml",
}


# --- the harness -------------------------------------------------------------


def served(name: str) -> fetch.FetchResult:
    """A captured feed, answered as a live host would answer it."""
    return fetch.FetchResult(
        outcome=fetch.FetchOutcome.OK,
        status=200,
        body=(FEEDS / name).read_bytes(),
    )


def fetcher_over(*urls: str) -> cli.Fetcher:
    """Serve exactly these addresses from the fixtures, and refuse every other one.

    Refusing rather than returning empty is deliberate. The plan stage must read
    the feed list and nothing else; an address that shows up here uncovered is a
    request nobody authorized, and the test says so by name.
    """
    table = {url: served(BODIES[url]) for url in urls}

    def read(url: str) -> fetch.FetchResult:
        if url not in table:
            raise AssertionError(f"the plan stage read an address no fixture covers: {url}")
        return table[url]

    return read


def failing(url: str, result: fetch.FetchResult, *serve: str) -> cli.Fetcher:
    """One address that answers badly, the rest served from the fixtures."""
    healthy = fetcher_over(*serve)

    def read(target: str) -> fetch.FetchResult:
        return result if target == url else healthy(target)

    return read


def settings_for(
    feeds: list[FeedDef],
    *,
    salience: list[SalienceFeedDef] | None = None,
    verticals: list[VerticalDef] | None = None,
) -> config.Settings:
    """The committed config, with the source list and the verticals swapped out.

    Every threshold, weight and cap under test is the real one from `config/`.
    Only the feed list is a fixture, because the feed list is what a test has to
    hold still.
    """
    base = config.load()
    return dataclasses.replace(
        base,
        sources=Sources(version=Sources.schema_version(), feeds=feeds, salience=salience or []),
        taxonomy=base.taxonomy.model_copy(update={"verticals": verticals or [AI]}),
    )


def plan(
    feeds: list[FeedDef],
    *,
    salience: list[SalienceFeedDef] | None = None,
    verticals: list[VerticalDef] | None = None,
    fetcher: cli.Fetcher | None = None,
    now: str = NOW,
    cap_override: int | None = None,
) -> RunPlan:
    settings = settings_for(feeds, salience=salience, verticals=verticals)
    urls = [feed.url for feed in feeds] + [feed.url for feed in (salience or [])]
    return cli.stage_plan(
        DATE,
        settings=settings,
        cap_override=cap_override,
        fetcher=fetcher or fetcher_over(*urls),
        now=lambda: now,
    )


def titles(built: RunPlan) -> list[str | None]:
    """Every planned headline, for the assertions that care about which story landed."""
    return [item.title for item in built.items]


# --- what the stage counts ---------------------------------------------------


def test_a_healthy_feed_is_read_and_its_entries_are_planned() -> None:
    built = plan([LAB, TRADE, COMMUNITY])
    assert (built.feeds_read, built.feeds_failed) == (3, 0)
    assert built.verticals[0].id == "ai"
    assert titles(built)[0] == "Example Lab releases a smaller model", (
        "the story three feeds carried leads the day"
    )


def test_a_feed_that_answers_two_hundred_with_nothing_in_it_counts_as_read() -> None:
    """The failure HTTP cannot see, and the one that killed eight real feeds.

    `feeds_read` counts a reply, not an article. A desk that has been silent for
    a month is indistinguishable here from a desk that is working, which is
    exactly why item 10 records every feed's result to a file: you cannot
    quarantine what you never measured.
    """
    built = plan([LAB, TRADE, QUIET])
    assert (built.feeds_read, built.feeds_failed) == (3, 0)
    assert not any(item.source_id == "quiet-desk" for item in built.items)


def test_an_unreachable_feed_is_counted_as_failed_and_never_stops_the_run() -> None:
    """Degrade, do not fail. One dead host must not cost the day its other sources."""
    built = plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=failing(
            TRADE_URL,
            fetch.FetchResult(outcome=fetch.FetchOutcome.TRANSIENT, status=503, detail="503"),
            LAB_URL,
            COMMUNITY_URL,
        ),
    )
    assert (built.feeds_read, built.feeds_failed) == (2, 1)
    assert built.items, "the surviving feeds still made a day"
    assert not any(item.source_id == "trade-press" for item in built.items)


def test_a_feed_that_robots_refuses_is_a_failure_not_a_silent_skip() -> None:
    """A refusal is a measurement. Counting it as read would hide a source we may never fetch."""
    built = plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=failing(
            COMMUNITY_URL,
            fetch.FetchResult(outcome=fetch.FetchOutcome.ROBOTS_DENIED, detail="robots.txt"),
            LAB_URL,
            TRADE_URL,
        ),
    )
    assert (built.feeds_read, built.feeds_failed) == (2, 1)


def test_the_plan_stage_reads_the_feed_list_and_nothing_else() -> None:
    """Every outbound address comes from committed config, never from fetched text.

    `fetcher_over` refuses an uncovered address, so a feed body that talked the
    stage into a request would fail this test by name (Holy Law #11).
    """
    built = plan([LAB, TRADE, COMMUNITY], salience=[FRONT_PAGE])
    assert built.feeds_read == 3


# --- retired feeds, as they behave today -------------------------------------


def test_a_retired_feed_is_still_fetched_and_still_planned() -> None:
    """Today's behaviour, and the defect item 2 fixes.

    `stage_plan` loops `sources.feeds`, which carries every entry ever added.
    `discover.live` - the only thing that honours `retired_on` - is consulted
    separately, and only for the feed floor. So a retired feed costs a request
    every run AND its articles reach a reader. Item 2 moves retired entries to
    their own key, which makes the live list lean and the filtering unnecessary.

    Three live feeds keep the vertical over its floor, so what this measures is
    the retired feed and nothing else.
    """
    retired = LAB.model_copy(update={"status": LifecycleStatus.RETIRED, "retired_on": "2026-08-01"})
    built = plan([retired, TRADE, COMMUNITY, NOTICES])
    assert built.feeds_read == 4, "a retired feed still costs a request"
    assert built.verticals[0].live_feeds == 3, "but it is not one of the live three"
    assert any(item.source_id == "lab-blog" for item in built.items), (
        "and a retired feed's article still reaches the page"
    )


def test_a_retired_feed_does_not_count_toward_the_feed_floor() -> None:
    """The other half of the same split: read for its articles, ignored for the floor."""
    retired = COMMUNITY.model_copy(
        update={"status": LifecycleStatus.RETIRED, "retired_on": "2026-08-01"}
    )
    built = plan([LAB, TRADE, retired])
    assert built.verticals[0].live_feeds == 2
    assert built.verticals[0].below_feed_floor, "two live feeds is under the floor of three"
    assert built.items == [], "and a vertical under its floor plans nothing"


# --- the vertical floor ------------------------------------------------------


def test_a_vertical_below_its_feed_floor_is_counted_but_renders_nothing() -> None:
    built = plan([LAB, TRADE])
    vertical = built.verticals[0]
    assert vertical.live_feeds == 2
    assert vertical.below_feed_floor
    assert vertical.considered > 0, "it is still collected - the desk is built in the open"
    assert vertical.planned == 0
    assert built.items == []


def test_a_second_vertical_with_no_feeds_still_appears_in_the_plan() -> None:
    """A desk that planned nothing is a fact about the day, not an absence."""
    energy = VerticalDef(id="energy", display_name="Energy", daily_cap=5, min_feeds=3)
    built = plan([LAB, TRADE, COMMUNITY], verticals=[AI, energy])
    assert [vertical.id for vertical in built.verticals] == ["ai", "energy"]
    assert built.verticals[1].live_feeds == 0
    assert built.verticals[1].planned == 0


# --- the caps ----------------------------------------------------------------


def test_the_daily_cap_bounds_what_a_vertical_contributes() -> None:
    capped = VerticalDef(id="ai", display_name="AI", daily_cap=2, min_feeds=3)
    built = plan([LAB, TRADE, COMMUNITY], verticals=[capped])
    assert len(built.items) == 2
    assert built.verticals[0].planned == 2
    assert built.verticals[0].considered > 2


def test_no_single_feed_becomes_the_vertical() -> None:
    """`collect.max_per_source` is 2, and the lab feed alone carries three stories."""
    built = plan([LAB, TRADE, COMMUNITY])
    from_lab = [item for item in built.items if item.source_id == "lab-blog"]
    assert len(from_lab) <= config.load().app.collect.max_per_source


def test_the_cap_override_raises_the_ceiling_for_validation_only() -> None:
    """A measurement corpus has no reason to obey a reading budget."""
    capped = VerticalDef(id="ai", display_name="AI", daily_cap=1, min_feeds=3)
    normal = plan([LAB, TRADE, COMMUNITY], verticals=[capped])
    raised = plan([LAB, TRADE, COMMUNITY], verticals=[capped], cap_override=10)
    assert len(normal.items) == 1
    assert len(raised.items) > 1


# --- salience: a vote, never a discovery -------------------------------------


def test_a_salience_feed_lifts_a_story_the_pool_already_had() -> None:
    without = plan([LAB, TRADE, COMMUNITY])
    with_vote = plan([LAB, TRADE, COMMUNITY], salience=[FRONT_PAGE])
    voted = next(item for item in with_vote.items if item.canonical_url == MODEL_RELEASE)
    unvoted = next(item for item in without.items if item.canonical_url == MODEL_RELEASE)
    assert voted.on_front_page
    assert not unvoted.on_front_page
    assert voted.rank_score > unvoted.rank_score


def test_a_salience_feed_never_puts_a_new_address_in_the_pool() -> None:
    """The front page carries a story no feed did. It must not become an item."""
    built = plan([LAB, TRADE, COMMUNITY], salience=[FRONT_PAGE])
    assert not any("elsewhere.example.net" in item.canonical_url for item in built.items)


def test_a_salience_feed_that_fails_costs_the_day_nothing() -> None:
    built = plan(
        [LAB, TRADE, COMMUNITY],
        salience=[FRONT_PAGE],
        fetcher=failing(
            FRONT_PAGE_URL,
            fetch.FetchResult(outcome=fetch.FetchOutcome.TRANSIENT, status=504),
            LAB_URL,
            TRADE_URL,
            COMMUNITY_URL,
        ),
    )
    assert built.items
    assert not any(item.on_front_page for item in built.items)
    assert built.feeds_failed == 0, "a salience feed is not a source, so it is not counted as one"


# --- the same day, twice -----------------------------------------------------


def test_two_runs_over_the_same_feeds_produce_the_identical_plan() -> None:
    """No model, no randomness, and now no clock either - so this is byte equality."""
    first = plan([LAB, TRADE, COMMUNITY], salience=[FRONT_PAGE])
    second = plan([LAB, TRADE, COMMUNITY], salience=[FRONT_PAGE])
    assert first.to_json() == second.to_json()


def test_the_feed_order_in_config_does_not_decide_the_day() -> None:
    forward = plan([LAB, TRADE, COMMUNITY])
    reversed_order = plan([COMMUNITY, TRADE, LAB])
    assert [item.canonical_url for item in forward.items] == [
        item.canonical_url for item in reversed_order.items
    ]


def test_generated_at_comes_from_the_clock_it_was_handed() -> None:
    built = plan([LAB, TRADE, COMMUNITY], now="2026-08-22T06:00:00Z")
    assert built.generated_at == "2026-08-22T06:00:00Z"


def test_a_plan_round_trips_through_its_own_schema() -> None:
    built = plan([LAB, TRADE, COMMUNITY])
    assert RunPlan.from_json(built.to_json()) == built
    assert json.loads(built.to_json())["version"] == RunPlan.schema_version()


# --- what is wrong today, recorded before it is fixed ------------------------


def test_a_future_dated_entry_takes_the_top_slot() -> None:
    """Today's behaviour. Item 5 bounds it.

    Recency is the tie-break, and nothing checks a date against the clock. On a
    day when no story is carried twice - which is most days - every score is
    identical and the tie-break IS the running order. So a feed whose entries
    are dated 14 hours ahead of `now` leads its vertical, and would lead it
    again tomorrow, and the day after.

    Two same-tier feeds, so score cannot mask what recency is doing.
    """
    pair = VerticalDef(id="ai", display_name="AI", daily_cap=5, min_feeds=2)
    built = plan([FORWARD, TRADE], verticals=[pair])
    assert len({item.rank_score for item in built.items}) == 1, "nothing here outscores anything"
    assert built.items[0].published_at == "2026-08-22T20:00:00Z"
    assert built.items[0].published_at > NOW


def test_an_article_four_months_old_is_still_planned() -> None:
    """Today's behaviour. Item 4 bounds it.

    Nothing compares a publish date to `now`, so an old article that reappears
    in a feed - a re-index, a URL change, a backfill - is planned as news.
    """
    built = plan([LAB, TRADE, COMMUNITY], now="2027-01-01T06:00:00Z")
    assert built.items
    assert all((item.published_at or "") < "2026-09-01" for item in built.items)


def test_an_undated_entry_sorts_last_but_is_still_planned() -> None:
    """Today's behaviour. Items 3 and 4 give it a real age instead of an empty string.

    `_ordered` sorts on `published_at or ""`, so no date means bottom of the
    vertical. That is a reasonable accident, not a decision, and it breaks the
    moment an age limit has to ask how old an undated item is.
    """
    built = plan([LAB, TRADE, NOTICES])
    undated = [item for item in built.items if item.published_at is None]
    assert undated, "an undated entry is planned"
    positions = [index for index, item in enumerate(built.items) if item.published_at is None]
    assert min(positions) > 0, "and it sorts below everything that carried a date"


def test_item_ids_restart_at_one_on_every_run() -> None:
    """Today's behaviour. Item 6 gives an item an id that survives a second run.

    The id is a rank position, so run 2 renumbers the day. `build_day` dedupes
    on that id, which means a story that moved one place is published twice.
    """
    first = plan([LAB, TRADE, COMMUNITY])
    second = plan([LAB, TRADE, COMMUNITY, FORWARD])
    assert first.items[0].item_id == "ai-01"
    assert second.items[0].item_id == "ai-01"
    moved = {item.canonical_url: item.item_id for item in first.items}
    changed = [
        url
        for item in second.items
        if (url := item.canonical_url) in moved and moved[url] != item.item_id
    ]
    assert changed, "the same story carries a different id once the pool changes"


# --- sharding ----------------------------------------------------------------


def built_plan() -> RunPlan:
    return plan([LAB, TRADE, COMMUNITY], verticals=[AI])


def test_a_single_shard_takes_the_whole_plan() -> None:
    built = built_plan()
    assert cli.shard_of(built, shard=0, shards=1) == list(built.items)


@pytest.mark.parametrize("shards", [2, 3, 4, 8])
def test_every_item_lands_in_exactly_one_shard(shards: int) -> None:
    """A lost item is a missing summary; a duplicated one is two runs of the model."""
    built = built_plan()
    landed = [
        item.item_id
        for shard in range(shards)
        for item in cli.shard_of(built, shard=shard, shards=shards)
    ]
    assert sorted(landed) == sorted(item.item_id for item in built.items)


def test_shards_are_round_robin_so_the_long_articles_spread() -> None:
    """Contiguous blocks would hand one worker a whole vertical, and its timeout."""
    built = built_plan()
    if len(built.items) < 2:
        pytest.skip("the fixture pool is too small to interleave")
    assert cli.shard_of(built, shard=0, shards=2)[0] == built.items[0]
    assert cli.shard_of(built, shard=1, shards=2)[0] == built.items[1]


def test_a_shard_beyond_the_item_count_is_empty_rather_than_an_error() -> None:
    """Four workers on a two-item day is normal, and two of them must exit cleanly."""
    built = built_plan()
    assert cli.shard_of(built, shard=len(built.items) + 1, shards=len(built.items) + 2) == []


# --- the fixtures themselves -------------------------------------------------


@pytest.mark.parametrize("name", sorted(BODIES.values()))
def test_every_feed_fixture_this_module_serves_parses(name: str) -> None:
    """A fixture that silently stopped parsing would make these tests pass for the wrong reason."""
    assert read_text(FEEDS / name).startswith("<?xml")
