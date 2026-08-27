"""Integration-tier tests for the plan stage - the day, decided before any weights load.

`stage_plan` is the one stage that reads the open web and the one stage nothing
tested. Every rule about freshness, identity and feed health is written into it,
so it keeps a safety net around all of them.

The three seams `cli` exposes are what make this possible. The fetcher is a
callable, so a test drives it from `tests/fixtures/feeds/` - a real function
reading a real captured file, not a mock (Rule #7). The clock is a callable,
so a rule about how old an article is has a fixed `now` and cannot change its
answer at midnight. The state directory is a path, so a test appends its sight
ledgers to a temp directory rather than to the repository's own.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh import cli, config, fetch, ledger
from idhazh.contracts.app_config import RunConfig
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.seen import PublishedRow
from idhazh.contracts.sources import FeedDef, SalienceFeedDef, Sources
from idhazh.contracts.taxonomy import LifecycleStatus, SourceTier, VerticalDef

FEEDS = FIXTURES_DIR / "feeds"

LAB_URL = "https://blog.example-lab.org/feed"
TRADE_URL = "https://trade.example-press.net/feed"
COMMUNITY_URL = "https://community.example.org/feed"
QUIET_URL = "https://quiet.example.org/feed"
NOTICES_URL = "https://notices.example.gov/feed"
FORWARD_URL = "https://forward.example-press.net/feed"
DUPLICATE_URL = "https://energy.example-wire.net/feed"
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
DUPLICATE = FeedDef(
    id="energy-wire",
    vertical="energy",
    title="Example Energy Wire",
    url=DUPLICATE_URL,
    tier=SourceTier.INSTITUTION,
)
FRONT_PAGE = SalienceFeedDef(
    id="front-page",
    title="Example Front Page",
    url=FRONT_PAGE_URL,
)

AI = VerticalDef(id="ai", display_name="AI", min_feeds=3)

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
    DUPLICATE_URL: "cross-vertical-duplicate.xml",
    FRONT_PAGE_URL: "front-page.xml",
}


# --- the harness -------------------------------------------------------------


def served(name: str) -> fetch.FetchResult:
    """A captured feed, answered as a live host would answer it."""
    return fetch.FetchResult(
        outcome=FetchOutcome.OK,
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
    retired: list[FeedDef] | None = None,
) -> config.Settings:
    """The committed config, with the source list and the verticals swapped out.

    Every threshold, weight and cap under test is the real one from `config/`.
    Only the feed list is a fixture, because the feed list is what a test has to
    hold still.
    """
    base = config.load()
    return dataclasses.replace(
        base,
        sources=Sources(
            version=Sources.schema_version(),
            feeds=feeds,
            salience=salience or [],
            retired=retired or [],
        ),
        taxonomy=base.taxonomy.model_copy(update={"verticals": verticals or [AI]}),
    )


def plan(
    feeds: list[FeedDef],
    *,
    salience: list[SalienceFeedDef] | None = None,
    verticals: list[VerticalDef] | None = None,
    retired: list[FeedDef] | None = None,
    fetcher: cli.Fetcher | None = None,
    now: str = NOW,
    run_n: int = 1,
    state: Path | None = None,
    safety_ceiling: int | None = None,
    cap: int | None = None,
) -> RunPlan:
    settings = settings_for(feeds, salience=salience, verticals=verticals, retired=retired)
    if safety_ceiling is not None:
        settings = dataclasses.replace(
            settings,
            app=settings.app.model_copy(
                update={
                    "run": settings.app.run.model_copy(
                        update={"safety_ceiling_per_run": safety_ceiling}
                    )
                }
            ),
        )
    # A retired feed's address is deliberately left out of the fetcher's table,
    # so reading one is an AssertionError rather than something to remember to
    # assert against.
    urls = [feed.url for feed in feeds] + [feed.url for feed in (salience or [])]
    return cli.stage_plan(
        DATE,
        settings=settings,
        fetcher=fetcher or fetcher_over(*urls),
        now=lambda: now,
        run_n=run_n,
        state_dir=state if state is not None else Path(tempfile.mkdtemp()),
        cap=cap,
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
    exactly why the health ledger records every feed's result: you cannot
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
            fetch.FetchResult(outcome=FetchOutcome.TRANSIENT, status=503, detail="503"),
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
            fetch.FetchResult(outcome=FetchOutcome.ROBOTS_DENIED, detail="robots.txt"),
            LAB_URL,
            TRADE_URL,
        ),
    )
    assert (built.feeds_read, built.feeds_failed) == (2, 1)


def test_the_plan_stage_reads_the_feed_list_and_nothing_else() -> None:
    """Every outbound address comes from committed config, never from fetched text.

    `fetcher_over` refuses an uncovered address, so a feed body that talked the
    stage into a request would fail this test by name (Rule #11).
    """
    built = plan([LAB, TRADE, COMMUNITY], salience=[FRONT_PAGE])
    assert built.feeds_read == 3


# --- retired feeds -----------------------------------------------------------


def retire(feed: FeedDef) -> FeedDef:
    return feed.model_copy(update={"status": LifecycleStatus.RETIRED, "retired_on": "2026-08-01"})


def test_a_retired_feed_is_never_fetched_and_never_reaches_a_reader() -> None:
    """Item 2. Retirement is enforced by the shape of the config, not by a filter.

    `stage_plan` loops `sources.feeds`, and a retired entry is no longer in it.
    That is the whole mechanism: there is nothing to remember to filter, and
    nothing that can be forgotten.

    The retired feed's address is absent from the fetcher's table on purpose.
    `fetcher_over` raises on an address no fixture covers, so "the request was
    never made" is the harness rather than an assertion.
    """
    built = plan([TRADE, COMMUNITY, NOTICES], retired=[retire(LAB)])
    assert built.feeds_read == 3, "a retired feed costs no request"
    assert built.verticals[0].live_feeds == 3
    assert built.items, "the live feeds still made a day"
    assert not any(item.source_id == "lab-blog" for item in built.items)


def test_a_retired_feed_does_not_count_toward_the_feed_floor() -> None:
    """A tombstone is not a source, even when the vertical needs one.

    The same feed, live, is the difference between a desk that renders and one
    that goes dark. Retiring it is a decision with a visible cost, not a piece
    of bookkeeping.
    """
    dark = plan([LAB, TRADE], retired=[retire(COMMUNITY)])
    assert dark.verticals[0].live_feeds == 2
    assert dark.verticals[0].below_feed_floor
    assert dark.items == [], "a vertical under its floor plans nothing"

    lit = plan([LAB, TRADE, COMMUNITY])
    assert lit.verticals[0].live_feeds == 3
    assert not lit.verticals[0].below_feed_floor
    assert lit.items, "the same feed, live, is what the floor was waiting for"


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
    energy = VerticalDef(id="energy", display_name="Energy", min_feeds=3)
    built = plan([LAB, TRADE, COMMUNITY], verticals=[AI, energy])
    assert [vertical.id for vertical in built.verticals] == ["ai", "energy"]
    assert built.verticals[1].live_feeds == 0
    assert built.verticals[1].planned == 0


# --- what bounds the size ----------------------------------------------------


def test_supply_decides_the_size_of_the_day() -> None:
    """No per-vertical cap. What the feeds offered is what the day is."""
    built = plan([LAB, TRADE, COMMUNITY])
    assert len(built.items) == built.verticals[0].planned
    assert built.verticals[0].planned > 0


def test_no_single_feed_becomes_the_vertical() -> None:
    """`collect.max_per_source` is 2, and the lab feed alone carries three stories."""
    built = plan([LAB, TRADE, COMMUNITY])
    from_lab = [item for item in built.items if item.source_id == "lab-blog"]
    assert len(from_lab) <= config.load().app.collect.max_per_source


def test_the_safety_ceiling_is_a_crash_guard_not_a_reading_budget() -> None:
    """A mis-parsed feed cannot hand the workers ten thousand articles.

    It drops the weakest items across the whole day rather than truncating one
    vertical, and a normal day never comes near it.
    """
    built = plan([LAB, TRADE, COMMUNITY])
    every = list(built.items)
    trimmed = cli._within_ceiling(every, ceiling=2)
    assert len(trimmed) == 2
    assert [item.item_id for item in trimmed] == [
        item.item_id for item in every if item in trimmed
    ], "the surviving items keep the order the plan gave them"
    weakest = min(every, key=lambda item: item.rank_score)
    assert weakest not in trimmed
    assert cli._within_ceiling(every, ceiling=len(every) + 1) == every


def test_cross_vertical_duplicate_drops_once_before_the_safety_ceiling(caplog: pytest.LogCaptureFixture) -> None:
    """One address may arrive through two desks. It still gets one planned item."""
    energy = VerticalDef(id="energy", display_name="Energy", min_feeds=1)
    caplog.set_level("INFO", logger="idhazh")

    built = plan(
        [LAB, TRADE, COMMUNITY, DUPLICATE],
        verticals=[AI, energy],
        safety_ceiling=2,
    )

    matching = [item for item in built.items if item.canonical_url == MODEL_RELEASE]
    assert len(matching) == 1
    assert matching[0].source_id == "lab-blog", "the highest-ranked duplicate wins"
    assert len(built.items) == 2, "dedupe happens before the ceiling, so a duplicate does not eat a slot"
    assert len({item.url_key for item in built.items}) == len(built.items)
    assert built.verticals[0].planned == 2
    assert built.verticals[1].planned == 0

    key = matching[0].url_key
    assert f"plan duplicates dropped count=1 url_keys={key} source_ids=energy-wire" in caplog.text


def test_the_committed_ceiling_is_far_above_any_real_day() -> None:
    built = plan([LAB, TRADE, COMMUNITY])
    assert len(built.items) < config.load().app.run.safety_ceiling_per_run


def test_a_cap_takes_the_best_of_each_vertical_and_leaves_the_ceiling_alone() -> None:
    """The validation knob, which was parsed and then dropped on the floor.

    It bounds a vertical rather than the day, so it is a different lever from
    `run.safety_ceiling_per_run`, and a run that does not ask for it plans
    exactly what it planned before.
    """
    full = plan([LAB, TRADE, COMMUNITY])
    assert len(full.items) > 1, "the fixture pool has to be big enough to show a trim"

    capped = plan([LAB, TRADE, COMMUNITY], cap=1)
    assert [item.item_id for item in capped.items] == [full.items[0].item_id]
    assert capped.verticals[0].planned == 1
    assert plan([LAB, TRADE, COMMUNITY], cap=None).to_json() == full.to_json()


def test_the_cap_flag_reaches_the_plan_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--cap` was declared, parsed, and read by nothing at all.

    A validation run therefore planned a whole day and could outrun the job it
    was given. The fetcher is the same fixture seam every other test here uses;
    only the way it is reached changes, because `main` builds its own.
    """
    settings = settings_for([LAB, TRADE, COMMUNITY])
    config_dir = tmp_path / "config"
    shutil.copytree(CONFIG_DIR, config_dir)
    (config_dir / "sources.json").write_text(settings.sources.to_json(), encoding="utf-8")
    (config_dir / "taxonomy.json").write_text(settings.taxonomy.to_json(), encoding="utf-8")
    monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(
        cli, "live_fetcher", lambda _settings: fetcher_over(LAB_URL, TRADE_URL, COMMUNITY_URL)
    )

    assert cli.main(["plan", "--date", DATE, "--config", str(config_dir), "--cap", "1"]) == 0

    written = RunPlan.from_json(
        (tmp_path / "run" / DATE / "plan.json").read_text(encoding="utf-8")
    )
    assert len(written.items) == 1
    assert len(plan([LAB, TRADE, COMMUNITY]).items) > 1, "the same day is bigger uncapped"


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
            fetch.FetchResult(outcome=FetchOutcome.TRANSIENT, status=504),
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


# --- freshness, identity, and the two ledgers --------------------------------


def test_a_date_too_far_in_the_future_is_not_a_date() -> None:
    """A feed that stamps tomorrow would otherwise lead its vertical every day.

    The fixture carries all three cases against a 06:00 clock: 20:00 the same
    day (14 hours ahead, impossible), 09:00 (three hours ahead, ordinary clock
    skew), and 05:00 (already published). Only the impossible one is replaced,
    and it is replaced rather than dropped - a bad date is not a reason to lose
    a story. `max_per_source` is 2, so the oldest of the three does not land.
    """
    pair = VerticalDef(id="ai", display_name="AI", min_feeds=2)
    built = plan([FORWARD, TRADE], verticals=[pair])
    dated = {item.title: item.published_at for item in built.items}
    assert dated["Datacentre build announced for the northern corridor"] == NOW, (
        "14 hours ahead is not a date - first sight replaces it"
    )
    assert dated["Quarterly capex guidance raised on accelerator demand"] == (
        "2026-08-22T09:00:00Z"
    ), "three hours ahead is clock skew, and is left alone"
    assert all((at or "") <= "2026-08-22T09:00:00Z" for at in dated.values()), (
        "and no reader is shown a time the run does not believe"
    )


def test_a_small_forward_skew_is_left_alone() -> None:
    """Clocks drift. A feed a few minutes ahead is not lying."""
    built = plan([LAB, TRADE, COMMUNITY], now="2026-08-21T05:55:00Z")
    early = next(item for item in built.items if item.canonical_url == MODEL_RELEASE)
    assert early.published_at == "2026-08-21T06:00:00Z", "five minutes ahead is inside the window"


def test_an_old_article_is_ranked_down_but_never_dropped() -> None:
    """No cutoff. A cutoff throws away a strong old story to keep a weak fresh one."""
    fresh = plan([LAB, TRADE, COMMUNITY], now="2026-08-21T12:00:00Z")
    stale = plan([LAB, TRADE, COMMUNITY], now="2027-01-01T06:00:00Z")
    assert [item.canonical_url for item in stale.items] == [
        item.canonical_url for item in fresh.items
    ], "the same stories are planned four months later"
    assert max(item.rank_score for item in stale.items) < max(
        item.rank_score for item in fresh.items
    ), "but the whole day scores lower"


def test_an_undated_entry_gets_the_age_we_first_saw_it() -> None:
    """First sight is the only honest age an undated article has."""
    state = Path(tempfile.mkdtemp())
    built = plan([LAB, TRADE, NOTICES], state=state)
    from_notices = [item for item in built.items if item.source_id == "notices"]
    assert from_notices, "an undated entry is planned"
    for item in from_notices:
        assert item.published_at == NOW

    recorded = ledger.load_seen(state, today=DATE, within_days=90)
    assert all(recorded[item.url_key] == NOW for item in from_notices)


def test_first_sight_survives_the_run_that_saw_it() -> None:
    """The second run of a later day reads the age the first run wrote down."""
    state = Path(tempfile.mkdtemp())
    plan([LAB, TRADE, NOTICES], now="2026-08-22T06:00:00Z", state=state)
    later = plan([LAB, TRADE, NOTICES], now="2026-08-22T18:00:00Z", state=state)
    undated = [item for item in later.items if item.source_id == "notices"]
    assert undated
    for item in undated:
        assert item.published_at == "2026-08-22T06:00:00Z", "twelve hours old, not brand new"


def test_an_item_id_survives_a_second_run_of_the_same_day() -> None:
    """The id is the address. Run 2 must recognise what run 1 already published."""
    first = plan([LAB, TRADE, COMMUNITY])
    second = plan([LAB, TRADE, COMMUNITY, FORWARD])
    known = {item.canonical_url: item.item_id for item in first.items}
    shared = [item for item in second.items if item.canonical_url in known]
    assert shared, "the two runs overlap"
    for item in shared:
        assert known[item.canonical_url] == item.item_id


def test_a_published_address_is_never_planned_again() -> None:
    """A freshness window cannot do this on its own.

    An article published at 23:00 is seven hours old at 06:00 the next morning,
    so any window wide enough to be useful is wide enough to republish it.
    """
    state = Path(tempfile.mkdtemp())
    first = plan([LAB, TRADE, COMMUNITY], state=state)
    ran = first.items[0]
    ledger.append_published(
        state,
        [
            PublishedRow(
                version=PublishedRow.schema_version(),
                url_key=ran.url_key,
                canonical_url=ran.canonical_url,
                published_on=DATE,
                item_id=ran.item_id,
            )
        ],
    )
    again = plan([LAB, TRADE, COMMUNITY], state=state)
    assert ran.url_key not in {item.url_key for item in again.items}
    assert again.verticals[0].considered == first.verticals[0].considered - 1, (
        "and it is not counted as considered either - it was settled, not weighed"
    )


def test_a_weighted_down_feed_ranks_below_a_full_one_of_the_same_tier() -> None:
    """Weight is soft retirement: drop it, watch what it costs, then decide."""
    full = plan([LAB, TRADE, COMMUNITY])
    halved = plan([LAB.model_copy(update={"weight": 0.2}), TRADE, COMMUNITY])
    strong = next(item for item in full.items if item.source_id == "lab-blog")
    weakened = next(item for item in halved.items if item.source_id == "lab-blog")
    assert weakened.rank_score < strong.rank_score


# --- what every feed did -----------------------------------------------------


def health_after(built_with: Path) -> list[FeedHealthRow]:
    """Whatever the run just wrote about its feeds, read back through the contract."""
    return ledger.load_health(built_with, today=DATE, within_days=1)


def test_every_feed_gets_a_row_whether_it_answered_or_not() -> None:
    """A source is only quarantinable if its silence was written down.

    Recording only the failures would make a feed that has never been tried look
    the same as a feed that has never failed.
    """
    state = Path(tempfile.mkdtemp())
    plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=failing(
            TRADE_URL,
            fetch.FetchResult(outcome=FetchOutcome.TRANSIENT, status=503, detail="HTTP 503"),
            LAB_URL,
            COMMUNITY_URL,
        ),
        state=state,
    )
    rows = health_after(state)
    assert {row.feed_id for row in rows} == {"lab-blog", "trade-press", "community"}
    dead = next(row for row in rows if row.feed_id == "trade-press")
    assert (dead.outcome, dead.status, dead.items) == (FetchOutcome.TRANSIENT, 503, 0)
    assert dead.failing


def test_a_feed_that_answered_with_nothing_is_recorded_as_failing() -> None:
    """200 with an empty body is the failure that killed eight real feeds quietly."""
    state = Path(tempfile.mkdtemp())
    plan([LAB, TRADE, QUIET], state=state)
    quiet = next(row for row in health_after(state) if row.feed_id == "quiet-desk")
    assert (quiet.outcome, quiet.items) == (FetchOutcome.OK, 0)
    assert quiet.failing, "an ok read that parsed to no entries still counts against the feed"


def test_a_working_feed_records_what_it_yielded() -> None:
    state = Path(tempfile.mkdtemp())
    plan([LAB, TRADE, COMMUNITY], state=state)
    rows = health_after(state)
    assert all(row.outcome is FetchOutcome.OK for row in rows)
    assert all(row.items > 0 for row in rows)
    assert not any(row.failing for row in rows)


def test_the_record_never_carries_the_response_body() -> None:
    """A feed is a stranger's text and this row lands on a published page (Rule #11)."""
    state = Path(tempfile.mkdtemp())
    hostile = "<script>alert(1)</script>" * 40
    plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=failing(
            LAB_URL,
            fetch.FetchResult(outcome=FetchOutcome.PERMANENT, status=404, detail=hostile),
            TRADE_URL,
            COMMUNITY_URL,
        ),
        state=state,
    )
    row = next(r for r in health_after(state) if r.feed_id == "lab-blog")
    assert row.detail is not None
    assert len(row.detail) <= 200, "a detail is one line of ours, never an unbounded body"


def test_two_runs_on_one_day_both_leave_a_record() -> None:
    """Quarantine counts runs, so a run that wrote nothing would be a run that never failed."""
    state = Path(tempfile.mkdtemp())
    plan([LAB, TRADE, COMMUNITY], state=state, run_n=1)
    plan([LAB, TRADE, COMMUNITY], state=state, run_n=2)
    rows = health_after(state)
    assert len(rows) == 6
    assert [row.run_id for row in rows[:3]] == ["2026-08-22-1"] * 3, "oldest run first"
    assert [row.run_id for row in rows[3:]] == ["2026-08-22-2"] * 3


def test_reading_a_history_that_was_never_written_is_empty_not_an_error() -> None:
    """A fresh clone has no history, and that is a run where no feed has a record yet."""
    assert ledger.load_health(Path(tempfile.mkdtemp()), today=DATE, within_days=30) == []


def test_a_row_that_no_longer_parses_is_skipped_rather_than_fatal() -> None:
    """This ledger is diagnostic. Losing a stale row costs evidence; refusing to start costs the day."""
    state = Path(tempfile.mkdtemp())
    plan([LAB, TRADE, COMMUNITY], state=state)
    path = ledger.health_path(state, DATE)
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write("1999-01-01,not-a-date,,,,,,\n")
    assert len(health_after(state)) == 3


# --- quarantine --------------------------------------------------------------


def seed_failures(state: Path, feed_id: str, runs: int) -> None:
    """A history of nothing but failed reads, on days before the one under test."""
    ledger.append_health(
        state,
        DATE,
        [
            FeedHealthRow(
                version=FeedHealthRow.schema_version(),
                run_id=f"{DATE}-{n}",
                date=DATE,
                feed_id=feed_id,
                checked_at=f"2026-08-22T0{n}:00:00Z",
                outcome=FetchOutcome.TRANSIENT,
                status=503,
                items=0,
                detail="HTTP 503",
            )
            for n in range(1, runs + 1)
        ],
    )


def failures_to_rest() -> int:
    """The committed threshold, so this test moves when the config does."""
    return config.load().app.collect.quarantine_after_failures


def test_a_feed_that_has_failed_enough_is_not_even_asked() -> None:
    """The saving is the request. `fetcher_over` refuses an address it does not cover,
    so asking a rested feed would fail this test by name rather than by a count."""
    state = Path(tempfile.mkdtemp())
    seed_failures(state, "trade-press", failures_to_rest())
    built = plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=fetcher_over(LAB_URL, COMMUNITY_URL),
        state=state,
        run_n=failures_to_rest() + 1,
    )
    assert (built.feeds_read, built.feeds_failed, built.feeds_skipped) == (2, 0, 1)
    assert built.items, "the run still makes a day out of the feeds that work"


def test_a_rested_feed_still_leaves_a_row_that_run() -> None:
    """A run that left no trace would keep the old failures newest forever."""
    state = Path(tempfile.mkdtemp())
    seed_failures(state, "trade-press", failures_to_rest())
    plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=fetcher_over(LAB_URL, COMMUNITY_URL),
        state=state,
        run_n=failures_to_rest() + 1,
    )
    rows = [row for row in health_after(state) if row.feed_id == "trade-press"]
    assert rows[-1].outcome is FetchOutcome.SKIPPED
    assert not rows[-1].failing, "a question we did not ask is not an answer against the source"


def test_the_rest_ends_and_the_feed_is_asked_again() -> None:
    """Run the plan until the quarantine lifts. It must lift, or this loops forever."""
    state = Path(tempfile.mkdtemp())
    threshold = failures_to_rest()
    seed_failures(state, "trade-press", threshold)
    asked = False
    for run_n in range(threshold + 1, threshold * 3 + 2):
        built = plan([LAB, TRADE, COMMUNITY], state=state, run_n=run_n)
        if built.feeds_skipped == 0:
            asked = True
            break
    assert asked, "a quarantine that never lifts is a retirement no person voted for"


def test_one_sick_feed_never_quarantines_a_healthy_one() -> None:
    state = Path(tempfile.mkdtemp())
    seed_failures(state, "trade-press", failures_to_rest())
    seed_failures(state, "lab-blog", failures_to_rest() - 1)
    built = plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=fetcher_over(LAB_URL, COMMUNITY_URL),
        state=state,
        run_n=failures_to_rest() + 1,
    )
    assert built.feeds_skipped == 1


def test_quarantine_never_touches_the_committed_source_list() -> None:
    """Retiring a feed is a person's decision. A run may rest one, never delete one."""
    state = Path(tempfile.mkdtemp())
    before = read_text(CONFIG_DIR / "sources.json")
    seed_failures(state, "trade-press", failures_to_rest())
    plan(
        [LAB, TRADE, COMMUNITY],
        fetcher=fetcher_over(LAB_URL, COMMUNITY_URL),
        state=state,
        run_n=failures_to_rest() + 1,
    )
    assert read_text(CONFIG_DIR / "sources.json") == before


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


def run_config(**overrides: int) -> RunConfig:
    return config.load().app.run.model_copy(update=overrides)


@pytest.mark.parametrize(
    ("items", "expected"),
    [(0, 1), (1, 1), (5, 1), (6, 2), (10, 2), (11, 3), (15, 3), (16, 4), (149, 4)],
)
def test_the_shard_count_honours_the_configured_shard_size(items: int, expected: int) -> None:
    """`run.shard_size` read as configuration and behaved as decoration.

    Five URLs is what one worker is sized to carry, so a day that needs fewer
    workers must get fewer: every extra job restores the weights again, and that
    restore is the largest fixed cost in the pipeline.
    """
    run = run_config(shard_size=5, max_parallel=4)
    assert cli.shard_count(items, run=run) == expected


def test_the_shard_count_never_exceeds_max_parallel() -> None:
    """The matrix cannot run a job the strategy will not start."""
    run = run_config(shard_size=5, max_parallel=4)
    assert cli.shard_count(10_000, run=run) == run.max_parallel
    assert cli.shard_count(10_000, run=run_config(shard_size=1, max_parallel=2)) == 2


def test_the_shard_count_is_at_least_one_so_an_empty_day_still_runs() -> None:
    """An empty matrix skips every worker, and the run publishes nothing without saying why."""
    assert cli.shard_count(0, run=run_config(shard_size=5, max_parallel=4)) == 1


def test_the_worst_case_day_still_fits_the_configured_fan_out() -> None:
    """The ceiling is what sizes a worker's worst shard, so the two are read together."""
    run = config.load().app.run
    shards = cli.shard_count(run.safety_ceiling_per_run, run=run)
    assert shards == run.max_parallel
    worst_shard = -(-run.safety_ceiling_per_run // shards)
    assert worst_shard == 40, "the worker size run.shard_timeout_minutes is measured against"


# --- the fixtures themselves -------------------------------------------------


@pytest.mark.parametrize("name", sorted(BODIES.values()))
def test_every_feed_fixture_this_module_serves_parses(name: str) -> None:
    """A fixture that silently stopped parsing would make these tests pass for the wrong reason."""
    assert read_text(FEEDS / name).startswith("<?xml")
