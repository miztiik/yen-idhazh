"""What does a run plan record about the feeds a desk could ask and the floor it asked against?"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh import ledger, source_health
from idhazh.contracts.run_manifest import VerticalCount
from idhazh.contracts.run_plan import PUBLISHED_AGE_BANDS, PublishedAgeBand, RunPlan, VerticalPlan
from idhazh.contracts.sources import Sources
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy

from ._fixtures import desk

pytestmark = pytest.mark.contract


def test_every_configured_feed_names_a_declared_vertical() -> None:
    """Retired feeds too - a tombstone still labels published items by vertical."""
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    declared = {vertical.id for vertical in taxonomy.verticals}
    for feed in sources.known_feeds():
        assert feed.vertical in declared, f"feed {feed.id} names an undeclared vertical"


def test_every_vertical_clears_its_own_feed_floor() -> None:
    """A vertical under `min_feeds` plans nothing at all, so this is a live gate.

    `rank.plan_vertical` returns an empty list for a vertical below its floor -
    the desk does not thin out, it goes silent. Nothing else notices: the run
    succeeds, the digest publishes, and one section is simply absent.

    That was one edit away from happening on 2026-08-29. Retiring the 40 feeds
    that had never published anything took `ai` to 28 against a floor of 35 and
    `business-economy` to 12 against 21 - 34 percent of that day's items, gone
    quietly. A throwaway assertion in a migration script caught it; nothing in
    the repository would have. This is that assertion, kept.

    Since 2026-09-02 it counts what a run may lawfully ask rather than what a
    curator left active, which is the count the floor is actually compared
    against - so it reads the committed retirement ledger and the committed
    health record as well as the config. Measured on this checkout 2026-09-02
    the two counts are identical on every desk, because no committed row records
    a permission or a retirement yet.

    It reads the committed config on purpose. The number that decides a run is
    the one in `config/`, not a value a fixture chose.
    """
    taxonomy = Taxonomy.from_json(read_text(CONFIG_DIR / "taxonomy.json"))
    sources = Sources.from_json(read_text(CONFIG_DIR / "sources.json"))
    state = REPO_ROOT / ledger.STATE_DIRNAME
    records = source_health.endpoint_records(
        ledger.load_health(state, today=newest_health_date(state), within_days=400)
    )
    retired = {row.endpoint_key for row in ledger.load_retirements(state)}
    active = Counter(
        feed.vertical for feed in sources.feeds if feed.status is LifecycleStatus.ACTIVE
    )
    for vertical in taxonomy.verticals:
        if vertical.status is not LifecycleStatus.ACTIVE:
            continue
        askable = source_health.eligible(
            sources.feeds, vertical.id, retired_keys=retired, records=records
        )
        assert len(askable) >= vertical.min_feeds, (
            f"{vertical.id} has {len(askable)} feeds it may ask against a floor of "
            f"{vertical.min_feeds}, so it would publish nothing - of "
            f"{active[vertical.id]} a curator left active"
        )


def newest_health_date(state: Path) -> str:
    """The last day the committed record covers, so the read does not move with the clock.

    A window ending at today would make this test's answer depend on when it
    ran, and the question it asks is about committed evidence rather than about
    the hour.

    Three listings - newest year, newest month, newest day - rather than a walk
    of the tree. The ledger files by day, so the newest file's own path IS the
    date, and the cost stays at most twelve plus thirty-one entries however long
    the project runs (`CLAUDE.md` section 13, Guardrail #12). It used to glob the
    month shards and hand back `<stem>-28`, which at day grain names a file the
    ledger may never have held.
    """
    root = state / ledger.HEALTH_DIRNAME
    years = [path for path in root.iterdir() if path.is_dir()] if root.is_dir() else []
    if not years:
        return "1970-01-01"
    year = max(years)
    month = max(path for path in year.iterdir() if path.is_dir())
    day = max(path for path in month.iterdir() if path.suffix == ".csv")
    return f"{year.name}-{month.name}-{day.stem}"


def test_a_plan_that_spells_live_feeds_still_reads() -> None:
    """The rename landed on 2026-09-02 and the model forbids unknown keys.

    Without the read migration a plan an earlier build wrote would be refused
    outright rather than degrade, which is a release blocker by section 11.
    """
    parsed = VerticalPlan.model_validate(desk())
    assert parsed.eligible_feeds == 3


def test_the_real_payload_an_earlier_build_committed_still_opens() -> None:
    """The same migration, against bytes a build actually wrote and committed.

    `tests/fixtures/superseded/run-plan-live-feeds.json` is the run-plan fixture
    exactly as it stood in the tree before the 2026-09-02 rename, recovered from
    git and kept unedited. A migration checked only against a payload this test
    file builds proves the builder, not the migration - and this is the whole
    reason the migration outlived the config knobs renamed beside it.
    """
    raw = read_text(FIXTURES_DIR / "superseded" / "run-plan-live-feeds.json")
    assert '"live_feeds"' in raw and '"eligible_feeds"' not in raw

    plan = RunPlan.from_json(raw)
    assert [(desk.id, desk.eligible_feeds) for desk in plan.verticals] == [("ai", 3), ("energy", 4)]
    assert all(desk.feed_floor is None for desk in plan.verticals), (
        "no floor is invented for a payload that never carried one"
    )


def test_a_plan_that_never_carried_a_floor_is_given_none() -> None:
    """Absent reads as unknown, never as a floor of zero.

    A zero would say the desk had no floor to clear, which on a payload that
    recorded `below_feed_floor` is a claim the payload itself can contradict.
    """
    assert VerticalPlan.model_validate(desk()).feed_floor is None
    assert VerticalPlan.model_validate(desk(below_feed_floor=True, planned=0)).feed_floor is None


def test_a_plan_may_not_spell_the_count_twice() -> None:
    """The migration maps the old name and never merges two answers.

    A payload carrying both is not an old payload; it is a writer nobody has,
    and quietly preferring one of the two is how a count starts disagreeing
    with itself.
    """
    with pytest.raises(ValidationError):
        VerticalPlan.model_validate(desk(eligible_feeds=9))


def bare_plan(**extra: Any) -> dict[str, Any]:
    """The smallest plan payload that validates, for the fields under test."""
    return {
        "date": "2026-08-21",
        "run_id": "2026-08-21-1",
        "generated_at": "2026-08-21T06:00:04Z",
        **extra,
    }


def test_a_plan_written_before_the_guard_was_counted_reads_as_unknown() -> None:
    """Null is unknown, never a run where the guard refused nothing.

    A zero would say this run was offered addresses the ledger held and refused
    none of them, which is a measurement. A payload written before anything
    counted cannot make it, and inventing one is how an unread number turns into
    an argument about how wide the cover should be.
    """
    built = RunPlan.model_validate(bare_plan())
    assert built.dropped_published is None
    assert built.dropped_published_ages is None


def test_the_guard_count_and_its_bands_are_recorded_together() -> None:
    """Either half alone reads as a measurement while being unable to support one."""
    bands = [band.model_dump(mode="json") for band in PublishedAgeBand.histogram([1, 200])]
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=2))
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published_ages=bands))
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=3, dropped_published_ages=bands))


def test_every_declared_band_is_written_and_a_short_histogram_is_refused() -> None:
    """An absent band and a band holding nothing are different answers.

    Dropping the empty ones would shorten the payload and lose the finding.
    Measured 2026-09-08 on an Intel Core i7-1265U, over the ledger as it stood at
    the end of 2026-09-07: its 7,600 rows span 16 published days, 2026-08-23 to
    2026-09-07, so every band from 30 days on is a measured zero on every run
    today - and that zero is why nobody can yet say what a finite cover would
    cost.
    """
    bands = PublishedAgeBand.histogram([0, 1, 200])
    assert [(band.from_days, band.to_days) for band in bands] == list(PUBLISHED_AGE_BANDS)
    assert [band.addresses for band in bands] == [1, 1, 0, 0, 0, 1, 0]

    short = [band.model_dump(mode="json") for band in bands if band.addresses]
    with pytest.raises(ValidationError):
        RunPlan.model_validate(bare_plan(dropped_published=3, dropped_published_ages=short))


#: The thirteen score fields a planned item started carrying on 2026-09-14 -
#: the eight terms rank_score is built from, and five slots with no producer yet.
SELECTION_TERMS: Final = (
    "authority_score",
    "tier_score",
    "feed_weight",
    "feed_reliability",
    "carriage_step",
    "watchlist_bonus",
    "lens_bonus",
    "recency_bonus",
    "label_confidence",
    "relationship_score",
    "fit_weight",
    "dual_score",
    "null_score",
)


def test_a_plan_written_before_the_score_terms_reads_every_one_as_unknown() -> None:
    """Thirteen fields absent, thirteen nulls, and nothing raised.

    Read off the committed run-plan fixture, which was written before any of the
    terms were kept - so this checks the migration against bytes a build wrote
    rather than against a payload the test builds for itself. A zero would say
    the term fired and was worth nothing, which is a claim no old plan can make.
    """
    raw = read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json")
    for name in SELECTION_TERMS:
        assert f'"{name}"' not in raw, f"the fixture is only a migration test while it omits {name}"

    plan = RunPlan.from_json(raw)
    assert plan.items, "the fixture carries planned items"
    for item in plan.items:
        invented = [name for name in SELECTION_TERMS if getattr(item, name) is not None]
        assert not invented, f"{item.item_id} invented {invented}"


def test_a_manifest_written_before_the_floor_was_recorded_reads_as_unknown() -> None:
    """`VerticalCount` never carried either number, so both are null on every
    manifest committed before today - and null is unknown rather than a desk
    with no sources."""
    count = VerticalCount.model_validate({"id": "ai", "planned": 5, "published": 4})
    assert count.eligible_feeds is None
    assert count.feed_floor is None
