"""How a feed's recent record scales its authority.

The reliability factor is derived from the committed feed-health ledger and
applied multiplicatively inside `authority`. These tests pin the two promises
the factor makes: it never rises above 1.0, so it can only ever reduce a score,
and it never falls below the configured floor, so it can never remove a feed.

Every health row here is built in memory. No test reads state/, so the archive
is never the input and the cost of these tests does not grow with it (CLAUDE.md
Guardrail #12 and the section 13 test policy).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace
from itertools import pairwise
from typing import Any, Final

import pytest
from conftest import FIXTURES_DIR, read_text

from idhazh.config import REPO_ROOT, load
from idhazh.contracts.base import ITEM_ID_PATTERN, derive_url_key
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.item_health import TimeSource
from idhazh.contracts.knobs.assist import AssistConfig
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.run_plan import PlannedItem, VerticalPlan
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceTier, VerticalDef
from idhazh.discover import Candidate
from idhazh.embed import Embedder
from idhazh.ledger import feed_reliability
from idhazh.rank import (
    CROCKFORD_ALPHABET,
    ITEM_ID_BYTES,
    ITEM_ID_SYMBOLS,
    DeskPlan,
    Ranked,
    ScoreTerms,
    authority,
    dedup_text,
    desk_of,
    desks_below_floor,
    duplicates_within_plan,
    item_id,
    plan_vertical,
    score,
    tier_weight,
)
from idhazh.stages.plan import _counterfactual_rows, _record_plan_duplicates

DATE = "2026-08-23"
RUN = "2026-08-23-1"
STAMP = "2026-08-23T06:00:00Z"

CONFIG = CollectConfig()


def _row(outcome: FetchOutcome, *, items: int = 1, feed_id: str = "a-feed") -> FeedHealthRow:
    """One health row, built in memory. `items` matters only for an ok outcome."""
    return FeedHealthRow(
        version=FeedHealthRow.schema_version(),
        run_id=RUN,
        date=DATE,
        feed_id=feed_id,
        checked_at=STAMP,
        outcome=outcome,
        items=items,
    )


def _candidate(
    *,
    source_id: str = "a-feed",
    tier: SourceTier = SourceTier.INSTITUTION,
    weight: float = 1.0,
) -> Candidate:
    return Candidate(
        canonical_url="https://example.org/a",
        source_url="https://example.org/a",
        url_key="example.org/a",
        source_id=source_id,
        vertical="ai",
        tier=tier,
        source_form=SourceForm.ARTICLE,
        title="A story",
        published_at=None,
        weight=weight,
    )


# --- feed_reliability: the clamp bounds --------------------------------------


def test_every_read_that_carried_entries_scores_one() -> None:
    rows = [_row(FetchOutcome.OK, items=3) for _ in range(4)]
    assert feed_reliability(rows, floor=0.5) == 1.0


def test_no_read_carried_entries_falls_to_the_floor_and_no_lower() -> None:
    """Four dead reads is a raw reliability of zero, clamped up to the floor.

    The clamp is the factor's promise: it reduces a score, it never removes a
    feed. At a floor of 0.5 the worst a record can do is a two-to-one cut.
    """
    rows = [_row(FetchOutcome.OK, items=0) for _ in range(4)]  # ok-with-zero is a bad read
    assert feed_reliability(rows, floor=0.5) == 0.5


def test_a_ratio_above_the_floor_is_that_ratio_unclamped() -> None:
    """Three of four evidence-bearing reads carried entries: 0.75, left alone."""
    rows = [_row(FetchOutcome.OK, items=1) for _ in range(3)] + [_row(FetchOutcome.OK, items=0)]
    assert feed_reliability(rows, floor=0.5) == pytest.approx(0.75)


def test_a_ratio_below_the_floor_clamps_up_to_the_floor() -> None:
    """One of four carried entries: 0.25 raw, clamped up to the floor of 0.5."""
    rows = [_row(FetchOutcome.OK, items=1)] + [_row(FetchOutcome.OK, items=0) for _ in range(3)]
    assert feed_reliability(rows, floor=0.5) == 0.5


def test_a_rest_and_a_robots_answer_carry_no_evidence_either_way() -> None:
    """A skipped run and a robots refusal drop out of the denominator.

    Neither asked the feed whether it works, so one good fetch beside them scores
    the same 1.0 as one good fetch alone.
    """
    rows = [
        _row(FetchOutcome.OK, items=2),
        _row(FetchOutcome.SKIPPED, items=0),
        _row(FetchOutcome.ROBOTS_DENIED, items=0),
    ]
    assert feed_reliability(rows, floor=0.5) == 1.0


def test_a_feed_with_only_preserving_rows_is_unknown_not_bad() -> None:
    """No evidence-bearing read at all scores 1.0, so an untested feed is unpunished."""
    rows = [_row(FetchOutcome.SKIPPED, items=0), _row(FetchOutcome.ROBOTS_DENIED, items=0)]
    assert feed_reliability(rows, floor=0.5) == 1.0


def test_no_rows_at_all_scores_one() -> None:
    assert feed_reliability([], floor=0.5) == 1.0


def test_a_failed_read_is_evidence_and_counts_against_the_feed() -> None:
    """A failed fetch did not preserve the streak, so it sits in the denominator.
    Three good fetches and one failed read is 0.75, not the 1.0 it would be if the
    failed read were set aside like a rest.
    """
    rows = [_row(FetchOutcome.OK, items=1) for _ in range(3)] + [_row(FetchOutcome.TRANSIENT, items=0)]
    assert feed_reliability(rows, floor=0.5) == pytest.approx(0.75)


def test_the_floor_comes_from_the_argument() -> None:
    """A lower floor moves the clamp: at 0.2, four dead reads score 0.2."""
    rows = [_row(FetchOutcome.OK, items=0) for _ in range(4)]
    assert feed_reliability(rows, floor=0.2) == 0.2


# --- authority: the factor is multiplicative ---------------------------------


def test_authority_without_a_map_is_tier_times_weight() -> None:
    cand = _candidate(tier=SourceTier.INSTITUTION, weight=1.0)
    assert authority(cand, CONFIG) == pytest.approx(tier_weight(SourceTier.INSTITUTION, CONFIG))


def test_reliability_scales_authority_multiplicatively() -> None:
    """The factor multiplies the authority; it is not added and not a re-rank."""
    cand = _candidate(source_id="a-feed", tier=SourceTier.INSTITUTION, weight=1.0)
    base = authority(cand, CONFIG)
    assert authority(cand, CONFIG, {"a-feed": 0.5}) == pytest.approx(base * 0.5)
    assert authority(cand, CONFIG, {"a-feed": 0.8}) == pytest.approx(base * 0.8)
    assert authority(cand, CONFIG, {"a-feed": 1.0}) == pytest.approx(base)


def test_the_factor_scales_a_hand_set_weight_too() -> None:
    """Reliability and the hand-set weight both multiply, so they compose."""
    cand = _candidate(source_id="a-feed", tier=SourceTier.INSTITUTION, weight=0.5)
    tier = tier_weight(SourceTier.INSTITUTION, CONFIG)
    assert authority(cand, CONFIG, {"a-feed": 0.5}) == pytest.approx(tier * 0.5 * 0.5)


def test_a_feed_absent_from_the_map_is_unscaled() -> None:
    """A miss reads 1.0: a feed we have no evidence on is never punished."""
    cand = _candidate(source_id="a-feed")
    assert authority(cand, CONFIG, {"other-feed": 0.5}) == pytest.approx(authority(cand, CONFIG))


def test_an_empty_map_is_unscaled() -> None:
    cand = _candidate(source_id="a-feed")
    assert authority(cand, CONFIG, {}) == pytest.approx(authority(cand, CONFIG))


def test_the_factor_only_ever_reduces() -> None:
    """Every value the ledger can hand authority lives in [floor, 1.0], and none
    of them lifts a score above its unscaled base.
    """
    cand = _candidate(tier=SourceTier.INSTITUTION, weight=1.0)
    base = authority(cand, CONFIG)
    for factor in (CONFIG.reliability_floor, 0.7, 1.0):
        assert authority(cand, CONFIG, {"a-feed": factor}) <= base + 1e-9


def test_a_dependable_feed_outranks_an_unreliable_peer_of_the_same_tier() -> None:
    """The whole point of the row: a feed that published badly stops scoring as
    though it did not, and drops below a feed of the same tier and weight that
    did.
    """
    good = _candidate(source_id="good", tier=SourceTier.INSTITUTION, weight=1.0)
    bad = _candidate(source_id="bad", tier=SourceTier.INSTITUTION, weight=1.0)
    factors = {"good": 1.0, "bad": 0.5}
    assert authority(good, CONFIG, factors) > authority(bad, CONFIG, factors)


# --- the reduction propagates through score() --------------------------------


def test_a_reduced_feed_scores_below_the_same_story_at_full_reliability() -> None:
    """A single-carrier story with no bonuses is exactly its authority, so a 0.5
    factor halves the score and changes nothing else.
    """
    carried = [_candidate(source_id="a-feed", tier=SourceTier.INSTITUTION)]
    full = score(
        carried,
        config=CONFIG,
        watchlist_hit=False,
        appeared=None,
        now=STAMP,
    )
    reduced = score(
        carried,
        config=CONFIG,
        watchlist_hit=False,
        appeared=None,
        now=STAMP,
        reliability={"a-feed": 0.5},
    )
    assert reduced == pytest.approx(full * 0.5)
    assert reduced < full


# --- the terms the order is built from, and what may never move it -----------

#: A fixed clock. Recency is a term of the order, so a real one would make every
#: assertion below answer differently tomorrow.
ORDER_NOW: Final = "2026-09-13T12:00:00Z"

AI: Final = VerticalDef(id="ai", display_name="AI", min_feeds=1)


def _story(
    name: str,
    *,
    tier: SourceTier = SourceTier.TRADE_PRESS,
    weight: float = 1.0,
    carriers: int = 1,
    watchlist_hit: bool = False,
    lens_bonus: float = 0.0,
    appeared: str | None = "2026-09-13T11:00:00Z",
    reliability: float = 1.0,
    source_form: SourceForm = SourceForm.ARTICLE,
    title: str = "A story",
) -> float:
    """One story's score, built from nothing but these arguments.

    Built rather than sampled. The point of the pairs below is two stories
    identical but for one term, and the committed archive has never held such a
    pair - it could not, because every real story differs in several at once.
    """
    url = f"https://{name}.example.org/story"
    carried = [
        Candidate(
            canonical_url=url,
            source_url=url,
            url_key=derive_url_key(url),
            source_id=f"{name}-{index}",
            vertical="ai",
            tier=tier,
            source_form=source_form,
            title=title,
            published_at=appeared,
            weight=weight,
        )
        for index in range(carriers)
    ]
    return score(
        carried,
        config=CONFIG,
        watchlist_hit=watchlist_hit,
        lens_bonus=lens_bonus,
        appeared=appeared,
        now=ORDER_NOW,
        reliability={candidate.source_id: reliability for candidate in carried},
    )


def test_every_term_the_order_names_moves_it_on_its_own() -> None:
    """Four terms, four pairs identical but for one of them, four flips.

    A term that cannot be shown to move the order on its own is a term nobody
    can attribute a move to, and the front-page vote was exactly that until
    2026-09-13.
    """
    assert _story("a", tier=SourceTier.INSTITUTION) > _story("b", tier=SourceTier.TRADE_PRESS)
    assert _story("c", weight=1.0) > _story("d", weight=0.5)
    assert _story("e", appeared="2026-09-13T11:00:00Z") > _story(
        "f", appeared="2026-09-12T16:00:00Z"
    )
    assert _story("g", reliability=1.0) > _story("h", reliability=CONFIG.reliability_floor)
    assert _story("i", watchlist_hit=True) > _story("j", watchlist_hit=False)


def test_a_field_the_order_does_not_read_never_moves_it() -> None:
    """The half a sampled test cannot do, and the half that catches an undeclared
    term: two stories differing only in something the score never reads.
    """
    assert _story("a", source_form=SourceForm.ARTICLE) == _story(
        "a", source_form=SourceForm.ABSTRACT
    )
    assert _story("a", title="A story") == _story("a", title="A story " * 40)


def _addressed(name: str, *, tier: SourceTier = SourceTier.TRADE_PRESS) -> Candidate:
    """A candidate whose `url_key` is a real digest, so `item_id` can read it.

    `_candidate` above spells a readable `url_key` because nothing it drives
    derives an id from one. `plan_vertical` does.
    """
    url = f"https://{name}.example.org/story"
    return Candidate(
        canonical_url=url,
        source_url=url,
        url_key=derive_url_key(url),
        source_id=name,
        vertical="ai",
        tier=tier,
        source_form=SourceForm.ARTICLE,
        title="A story",
        published_at="2026-09-13T11:00:00Z",
        weight=1.0,
    )


def test_an_aggregators_front_page_no_longer_moves_the_order() -> None:
    """The term this row removed, asserted end to end through the plan stage.

    Driven through `plan_vertical` rather than `score` because that is where a
    front-page vote reaches the arithmetic at all, and because `score` no longer
    takes an argument the assertion could pass. It fails against the base tree,
    where the vote was worth `collect.front_page_bonus` - 0.4, more than the
    step between the community and trade-press tiers.
    """
    voted = _addressed("voted")
    unvoted = _addressed("unvoted")
    items = plan_vertical(
        AI,
        [voted, unvoted],
        config=CONFIG,
        eligible_feeds=2,
        now=ORDER_NOW,
        front_page_keys=frozenset({voted.canonical_url}),
    ).items
    by_source = {item.source_id: item for item in items}
    assert by_source["voted"].on_front_page is True, "the vote must still be published"
    assert by_source["unvoted"].on_front_page is False
    assert by_source["voted"].rank_score == by_source["unvoted"].rank_score, (
        "an aggregator's vote is a published fact about the item and not a term of "
        "the order. It fired on 8 of 5,682 published stories, measured 2026-09-13."
    )


def test_the_terms_rank_in_the_order_the_editor_set() -> None:
    """Authority, then recency, then reliability, then a watchlist subject.

    Read off `config/` rather than spelled, so a weight edit moves the bound
    with it instead of leaving this assertion true about numbers nobody uses.
    Each bound is the most that term can move one story, which is the only
    comparison available between a multiplier and an addition.

    The last comparison allows a tie because today there is one: reliability's
    ceiling on the best tier is 0.5 and `watchlist_bonus` is 0.5. A tie is not
    an inversion, so it passes - and raising the watchlist weight one step
    fails it, which is the bite.
    """
    config = load().app.collect
    tiers = sorted(
        (
            config.tier_weights.community,
            config.tier_weights.trade_press,
            config.tier_weights.institution,
        )
    )
    authority_span = tiers[-1] - tiers[0]
    reliability_ceiling = (1.0 - config.reliability_floor) * tiers[-1]

    assert authority_span > config.recency_weight, (
        f"authority spans {authority_span} and recency may move a story "
        f"{config.recency_weight}. Recency is the second term, not the first."
    )
    assert config.recency_weight > reliability_ceiling, (
        f"recency may move a story {config.recency_weight} and reliability "
        f"{reliability_ceiling}. Reliability is the third term, not the second."
    )
    assert reliability_ceiling >= config.watchlist_bonus, (
        f"reliability may move a story {reliability_ceiling} and a watchlist subject "
        f"{config.watchlist_bonus}. A watchlist subject is the fourth term, not the third."
    )


def test_the_carriage_step_cannot_outrank_one_tier_step() -> None:
    """The window `collect.carriage_step` has to sit in, read off `config/`.

    Both walls, in one test, because a number bounded on one side reads like a
    number with one rule. The ceiling is the smallest gap between two tier
    weights: at or above it, carriage promotes a community story past a
    trade-press one, and a tie-break that can jump a tier is a term. The floor
    is `ui.lead_shared_subject_weight`: at or below it, a subject that recurs
    across a week outranks a story two independent feeds carried today, which
    inverts the rule `discovery.md` already holds that weight under.

    Both bounds are other people's config values and both are estimates, so the
    step is set to the middle of what they leave rather than pressed against
    either. Measured 2026-09-13 over the 13 committed days that carry
    `rank_score`: across the whole of that window 6 of 260 head slots move and
    no lead does, so nothing inside it is measurable and the margin is the only
    thing worth buying.
    """
    config = load().app
    tiers = sorted(
        (
            config.collect.tier_weights.community,
            config.collect.tier_weights.trade_press,
            config.collect.tier_weights.institution,
        )
    )
    smallest_tier_step = min(high - low for low, high in pairwise(tiers))
    step = config.collect.carriage_step

    assert step < smallest_tier_step, (
        f"carriage is worth {step} and the smallest step between two tiers is "
        f"{smallest_tier_step}. A tie-break may not promote a story past a tier."
    )
    assert step > config.ui.lead_shared_subject_weight, (
        f"carriage is worth {step} and a shared subject {config.ui.lead_shared_subject_weight}. "
        "A subject that recurs across a week may not outrank a story two feeds carried today."
    )


def test_one_feed_from_the_source_beats_the_wire_copy_that_repeated_it() -> None:
    """The case the step exists for, built rather than sampled.

    Measured 2026-09-13 over the 13 committed days that carry `rank_score`: the
    lead changes on 8 of them and every one of the eight is this swap - wire
    copy three of our feeds repeated, replaced by one feed carrying the story
    from the organisation it is about. `carried_by` counts feeds carrying ONE
    address, so it measures syndication and not agreement, and the third copy
    adds no fact to the first.

    **The first assertion fails against the base tree and the second does not.**
    There the multiplier makes trade press at three carriers worth 0.6 x 3 =
    1.8, which beats an institution's 1.0; here it is 0.6 + 0.25 = 0.85, which
    does not. The community pair is a guard rather than a discriminator - 0.3 x
    2 = 0.6 never beat 1.0 - and this row's own text claimed it was the half
    that fails. Corrected on execution, per the plan's section 0.1.
    """
    institution = _story("primary", tier=SourceTier.INSTITUTION, carriers=1)
    wire = _story("wire", tier=SourceTier.TRADE_PRESS, carriers=3)
    assert institution > wire, (
        f"the source's own account scores {institution} and wire copy three feeds "
        f"repeated scores {wire}. Repetition is our distribution, not the world's "
        "judgement."
    )

    community = _story("forum", tier=SourceTier.COMMUNITY, carriers=2)
    assert institution > community


def test_carriage_is_a_step_and_never_a_count() -> None:
    """Three carriers is not three times the story, and six is not six times.

    It multiplied until 2026-09-13, so this was false: two carriers doubled the
    authority term and the term was uncapped, which is why a story on six feeds
    took the day. Measured over the same 13 days, 24 of 5,682 stories reached
    three carriers or more, so what the count bought was rare and unbounded at
    once - the worst shape a ranking term can have.
    """
    one = _story("solo", carriers=1)
    two = _story("pair", carriers=2)
    six = _story("many", carriers=6)

    assert two == pytest.approx(one + CONFIG.carriage_step)
    assert six == pytest.approx(two), "the step fires once and never grows"


def test_the_step_is_flat_and_does_not_scale_with_the_tier() -> None:
    """The defect a multiplier had: it paid most to whatever already scored best.

    A second feed used to buy 1.0 on an institution and 0.3 on a community feed
    - the same signal worth three times as much to the story that needed it
    least. A tie-break pays the same to both.
    """
    gains = [
        _story(f"t{tier.value}", tier=tier, carriers=2)
        - _story(f"t{tier.value}", tier=tier, carriers=1)
        for tier in (SourceTier.INSTITUTION, SourceTier.TRADE_PRESS, SourceTier.COMMUNITY)
    ]
    assert all(gain == pytest.approx(CONFIG.carriage_step) for gain in gains), (
        f"carriage paid {gains} across the three tiers and a tie-break pays one amount"
    )


def test_no_weight_can_admit_a_story_the_age_gate_refused() -> None:
    """A term may reorder; it may never admit.

    Every bonus at once, on the best tier, against a story past
    `max_age_hours`. The gate runs before the score and a weight cannot reach
    past it - which is what lets the weights above be tuned for an order
    without anybody checking what they let into the day.
    """
    stale = "2026-09-11T12:00:00Z"
    assert CONFIG.max_age_hours < 48.0, "the fixture below is only stale under a day-ish gate"
    old = replace(_addressed("old", tier=SourceTier.INSTITUTION), published_at=stale)
    plan, items, _ = plan_vertical(
        AI,
        [old],
        config=CONFIG,
        eligible_feeds=1,
        now=ORDER_NOW,
        watchlist_keys=frozenset({old.url_key}),
        front_page_keys=frozenset({old.canonical_url}),
        lens_bonuses={old.url_key: 10.0},
    )
    assert items == []
    assert plan.too_old == 1


# --- the terms a planned item carries, and what they add up to ---------------

#: One address two feeds carried at different tiers. A desk whose carriers all
#: sit on one tier cannot tell the winning carrier's factors from a loser's, and
#: no committed day is guaranteed to hold such a pair - so it is built.
CARRIED_URL: Final = "https://carried.example.org/story"

#: One address a single feed carried, so the carriage step reads a real zero.
SOLO_URL: Final = "https://solo.example.org/story"

#: The institution carrier's own weight and reliability. Neither is 1.0 and
#: neither matches the community carrier's, so reading the wrong carrier shows.
WON_WEIGHT: Final = 0.75
WON_RELIABILITY: Final = 0.8

#: The lens weight the solo story earns, so the lens term is non-zero somewhere.
SOLO_LENS: Final = 0.4


def _carrier(url: str, source_id: str, tier: SourceTier, weight: float) -> Candidate:
    return Candidate(
        canonical_url=url,
        source_url=url,
        url_key=derive_url_key(url),
        source_id=source_id,
        vertical="ai",
        tier=tier,
        source_form=SourceForm.ARTICLE,
        title="A story",
        published_at="2026-09-13T11:00:00Z",
        weight=weight,
    )


def _terms_desk() -> list[PlannedItem]:
    """Two stories planned through the real ranker, built from nothing else.

    The carried story is listed weakest-carrier-first and is on the watchlist.
    The solo story matches a lens. Between the two, every one of the eight terms
    is non-zero on at least one item and zero on at least one other.
    """
    return plan_vertical(
        AI,
        [
            _carrier(CARRIED_URL, "community-feed", SourceTier.COMMUNITY, 1.0),
            _carrier(CARRIED_URL, "institution-feed", SourceTier.INSTITUTION, WON_WEIGHT),
            _carrier(SOLO_URL, "trade-feed", SourceTier.TRADE_PRESS, 1.0),
        ],
        config=CONFIG,
        eligible_feeds=3,
        now=ORDER_NOW,
        watchlist_keys=frozenset({derive_url_key(CARRIED_URL)}),
        lens_bonuses={derive_url_key(SOLO_URL): SOLO_LENS},
        reliability={"institution-feed": WON_RELIABILITY},
    ).items


def _terms_of(item: PlannedItem) -> dict[str, float]:
    """The eight terms off one planned item, with a null refused rather than read as zero."""
    named: dict[str, float | None] = {
        name: getattr(item, name)
        for name in (
            "authority_score",
            "tier_score",
            "feed_weight",
            "feed_reliability",
            "carriage_step",
            "watchlist_bonus",
            "lens_bonus",
            "recency_bonus",
        )
    }
    missing = sorted(name for name, value in named.items() if value is None)
    assert not missing, f"{item.item_id} carries no {missing}"
    return {name: value for name, value in named.items() if value is not None}


def test_the_terms_on_a_planned_item_add_up_to_the_score_that_ordered_the_day() -> None:
    """Five addends sum to `rank_score`; three factors multiply to authority.

    It proves the parts sum to the whole, not that any one term is correct.
    """
    items = _terms_desk()
    assert len(items) == 2, "the fixture plans two stories"

    for item in items:
        terms = _terms_of(item)
        summed = (
            terms["authority_score"]
            + terms["carriage_step"]
            + terms["watchlist_bonus"]
            + terms["lens_bonus"]
            + terms["recency_bonus"]
        )
        assert summed == pytest.approx(item.rank_score, abs=1e-6), (
            f"{item.item_id} publishes {item.rank_score} and its terms sum to {summed}"
        )
        assert terms["authority_score"] == pytest.approx(
            terms["tier_score"] * terms["feed_weight"] * terms["feed_reliability"], abs=1e-6
        ), f"{item.item_id} authority is not the product of the three factors it names"


def test_the_authority_factors_come_from_the_carrier_that_won_the_maximum() -> None:
    """Two feeds, one address, and only one of them scored it.

    The community feed is listed first and carries the larger own-weight, so an
    item built from an arbitrary carrier would read its tier score of 0.3 and
    its untested 1.0 reliability. The institution is the one the score took its
    maximum from, and its three factors are the three the item has to publish.
    """
    carried = next(item for item in _terms_desk() if item.url_key == derive_url_key(CARRIED_URL))

    assert carried.carried_by == 2
    assert carried.source_id == "institution-feed"
    assert carried.tier_score == pytest.approx(tier_weight(SourceTier.INSTITUTION, CONFIG))
    assert carried.feed_weight == pytest.approx(WON_WEIGHT)
    assert carried.feed_reliability == pytest.approx(WON_RELIABILITY)
    assert carried.carriage_step == pytest.approx(CONFIG.carriage_step)
    assert carried.watchlist_bonus == pytest.approx(CONFIG.watchlist_bonus)
    assert carried.lens_bonus == 0.0


def test_a_term_that_did_not_fire_is_written_as_zero_and_never_left_absent() -> None:
    """Zero is a measurement here, and null means the plan predates the terms.

    A run that writes these has to write the zeros too, or a reader cannot tell
    a story nothing carried twice from a story written before anybody counted.
    """
    solo = next(item for item in _terms_desk() if item.url_key == derive_url_key(SOLO_URL))
    terms = _terms_of(solo)

    assert terms["carriage_step"] == 0.0, "one feed carried it"
    assert terms["watchlist_bonus"] == 0.0, "no watchlist subject"
    assert terms["lens_bonus"] == pytest.approx(SOLO_LENS)
    assert terms["recency_bonus"] > 0.0, "an hour-old story still earns the recency term"


# --- the counterfactual: what another lens weight would have scored ----------

TWO_CANDIDATES_ONE_SLOT: Final = FIXTURES_DIR / "rank" / "two-candidates-one-slot.json"


def _one_slot_desk() -> tuple[dict[str, Any], list[Candidate]]:
    """The fixture's two candidates, every `url_key` recomputed on read.

    Built rather than sampled, and deliberately not read from a committed day:
    the case this needs is a desk where the story carrying the lens is the story
    that loses, and no archive is guaranteed to hold one (CLAUDE.md section 13).
    """
    fixture = json.loads(read_text(TWO_CANDIDATES_ONE_SLOT))
    built = [
        Candidate(
            canonical_url=entry["canonical_url"],
            source_url=entry["canonical_url"],
            url_key=derive_url_key(entry["canonical_url"]),
            source_id=entry["source_id"],
            vertical=fixture["vertical"],
            tier=SourceTier(entry["tier"]),
            source_form=SourceForm(entry["source_form"]),
            title=entry["title"],
            published_at=entry["published_at"],
        )
        for entry in fixture["candidates"]
    ]
    return fixture, built


def _one_slot_config(fixture: dict[str, Any]) -> CollectConfig:
    return CollectConfig(max_per_source=fixture["max_per_source"])


def _one_slot_plan(*, ask: bool = True) -> tuple[dict[str, Any], DeskPlan]:
    """The desk planned once. `ask` is whether the counterfactual weight is supplied.

    The committed lens weights are supplied either way, so the two cases differ
    in one argument and nothing else - which is what makes "it moved nothing"
    an assertion rather than a claim.
    """
    fixture, built = _one_slot_desk()
    weight = fixture["lens"]["weight"]
    multiplier = fixture["lens"]["multiplier"]
    hits = {
        candidate.url_key: weight
        for candidate, entry in zip(built, fixture["candidates"], strict=True)
        if entry["lens_hit"]
    }
    plan = plan_vertical(
        AI,
        built,
        config=_one_slot_config(fixture),
        eligible_feeds=1,
        now=fixture["now"],
        lens_bonuses=hits,
        counterfactual_lens_bonuses=(
            {key: value * multiplier for key, value in hits.items()} if ask else None
        ),
    )
    return fixture, plan


def _refused_key(fixture: dict[str, Any]) -> str:
    entry = next(one for one in fixture["candidates"] if one["role"] == "refused")
    return derive_url_key(entry["canonical_url"])


def test_a_candidate_the_slot_went_past_is_still_on_the_record() -> None:
    """The whole reason the pool comes back at all.

    A story the run takes leaves a payload, a summary and a published row. A
    story it scores and refuses leaves nothing: the candidate list is rebuilt
    from the feeds every run, and tomorrow's feeds no longer carry today's
    stories. So a question about what a different weight would have done can
    only be answered from what was written down while the day was being
    planned, and the refused half is the half that would be missing.
    """
    fixture, plan = _one_slot_plan()
    refused = _refused_key(fixture)

    assert len(plan.items) == 1, "the fixture is built so one source holds one slot"
    assert refused not in {item.url_key for item in plan.items}
    assert refused in {ranked.candidate.url_key for ranked in plan.pool}
    assert len(plan.pool) == len(fixture["candidates"]), "the pool is everything scored"


def test_the_recorded_score_is_the_one_that_decided_the_day() -> None:
    """Not a number computed beside the ranker - the ranker's own answer.

    Re-derived here from `score` over the same candidate, and checked against
    the `rank_score` the taken item carries onto the page. A recorded score that
    came from anywhere but the call that decided the order would make every
    later comparison meaningless while still reading like an answer.
    """
    fixture, plan = _one_slot_plan()
    config = _one_slot_config(fixture)

    for ranked in plan.pool:
        assert ranked.score == score(
            [ranked.candidate],
            config=config,
            watchlist_hit=ranked.watchlist_hit,
            lens_bonus=ranked.lens_bonus,
            appeared=ranked.appeared_at,
            now=fixture["now"],
        )

    taken = plan.items[0]
    on_the_page = next(r for r in plan.pool if r.candidate.url_key == taken.url_key)
    assert taken.rank_score == on_the_page.score


def test_the_second_score_differs_by_the_lens_term_and_by_nothing_else() -> None:
    """Every other term is identical, so the whole difference is the lens.

    Both cases are asserted, and the second one is the one that catches a real
    mistake: a story matching no lens must come back with the two scores equal
    to the last decimal place. A counterfactual that moved a story it was not
    asking about would make the ledger unreadable - nobody could tell which
    rows a weight change actually explains.
    """
    fixture, plan = _one_slot_plan()
    multiplier = fixture["lens"]["multiplier"]
    unmoved = 0

    for ranked in plan.pool:
        assert ranked.score_counterfactual is not None
        gain = ranked.score_counterfactual - ranked.score
        assert gain == pytest.approx(ranked.lens_bonus * multiplier - ranked.lens_bonus, abs=2e-6)
        unmoved += not ranked.lens_bonus

    assert unmoved == 1, "the fixture holds one story carrying no lens at all"
    assert [r.score_counterfactual for r in plan.pool if not r.lens_bonus] == [
        r.score for r in plan.pool if not r.lens_bonus
    ], "a story matching no lens is not moved by a lens weight"


def test_a_run_that_asks_no_counterfactual_records_none() -> None:
    """No stand-in number. `None` says the question was not asked.

    A zero here would read as "the weight would have changed nothing", which is
    a finding, and a run that asked nothing has no finding to report.
    """
    _, plan = _one_slot_plan(ask=False)

    assert plan.pool, "the desk still scores its candidates"
    assert [ranked.score_counterfactual for ranked in plan.pool] == [None] * len(plan.pool)


def test_the_counterfactual_moves_no_item_and_no_order() -> None:
    """The row's whole promise: it records, and it changes nothing.

    The same desk planned twice, differing in one argument. Every published
    field of every planned item has to match, because a counterfactual that
    could move a story would be a second ranker nobody agreed to ship.
    """
    _, plain = _one_slot_plan(ask=False)
    _, asked = _one_slot_plan()

    assert [item.model_dump() for item in asked.items] == [
        item.model_dump() for item in plain.items
    ]
    assert [r.score for r in asked.pool] == [r.score for r in plain.pool]
    assert asked.summary.model_dump() == plain.summary.model_dump()


def _flat_terms(at: float) -> ScoreTerms:
    """A breakdown that adds up, for a pool entry whose score is handed in.

    Authority carries the whole of it, at a full-weight feed with no evidence
    against it. That is the one shape that stays self-consistent whatever `at`
    is, so the entry can name a score without also inventing a story about it.
    """
    return ScoreTerms(
        total=at,
        authority_score=at,
        tier_score=at,
        feed_weight=1.0,
        feed_reliability=1.0,
        carriage_step=0.0,
        watchlist_bonus=0.0,
        lens_bonus=0.0,
        recency_bonus=0.0,
    )


def _scored(name: str, *, at: float = 1.0) -> Ranked:
    """One entry of a desk's pool, built in memory."""
    return Ranked(
        score=at,
        terms=_flat_terms(at),
        candidate=_addressed(name),
        appeared_at=None,
        time_source=TimeSource.FIRST_SEEN,
        carried_by=1,
        watchlist_hit=False,
        on_front_page=False,
        score_counterfactual=at,
    )


def _rows(
    pools: dict[str, list[Ranked]], items: list[PlannedItem], *, per_desk: int = 20
) -> list[CounterfactualScoreRow]:
    return _counterfactual_rows(
        pools,
        items,
        date=DATE,
        run_id=RUN,
        lens_hits={},
        multiplier=1.25,
        refused_per_desk=per_desk,
    )


def test_one_address_on_two_desks_is_taken_only_on_the_desk_that_took_it() -> None:
    """An address two desks carry is scored twice and planned once.

    Matching the `taken` cell on the address alone marks both rows taken, and
    the ledger then claims a longer day than the run published: measured on a
    real run on 2026-09-14, 87 rows said taken over a day of 80 items. The
    desk has to be half of the match, which is also why it is half of the
    ledger's key.
    """
    ranked = _scored("shared")
    item = PlannedItem(
        item_id=item_id("ai", ranked.candidate.url_key),
        url_key=ranked.candidate.url_key,
        source_url=ranked.candidate.source_url,
        canonical_url=ranked.candidate.canonical_url,
        source_id=ranked.candidate.source_id,
        tier=ranked.candidate.tier,
        vertical="ai",
        title=ranked.candidate.title,
        rank_score=ranked.score,
    )

    rows = _rows({"ai": [ranked], "world": [ranked]}, [item])

    assert [(row.vertical, row.taken) for row in rows] == [("ai", True), ("world", False)]


def test_a_desk_records_only_its_highest_scoring_refused_candidates() -> None:
    """The bound, and the reason a run's cost does not grow with the archive.

    The pool arrives in the order the take read it, so the refused candidates a
    desk keeps are the first it meets - the band around the cut, where a bonus
    decides. A candidate further down would not cross under any weight the
    probe asks about.
    """
    pool = [_scored(f"feed{n}", at=10.0 - n) for n in range(5)]

    rows = _rows({"ai": pool}, [], per_desk=2)

    assert [row.url_key for row in rows] == [item.candidate.url_key for item in pool[:2]]
    assert not any(row.taken for row in rows)
    assert _rows({"ai": pool}, [], per_desk=0) == []


# --- the plan-stage duplicate pass: same story, two addresses ----------------

#: Two orthogonal unit vectors, so a pair sharing one has cosine 1.0 and a pair
#: split across the two has cosine 0.0 - the extremes the threshold sits between.
_SAME = [1.0, 0.0]
_OTHER = [0.0, 1.0]


def _planned(
    vertical: str,
    number: int,
    *,
    source_id: str,
    rank_score: float,
    title: str | None = "A story",
) -> PlannedItem:
    """One planned item with a real url_key and a well-formed id, built in memory."""
    url = f"https://{source_id}.example.org/{vertical}/{number}"
    return PlannedItem(
        item_id=f"{vertical}-{number:02d}",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id=source_id,
        tier=SourceTier.INSTITUTION,
        vertical=vertical,
        title=title,
        rank_score=rank_score,
    )


def test_the_alphabet_is_crockford_base32() -> None:
    """Thirty-two distinct symbols, and the four that can be misread are not among them."""
    assert len(CROCKFORD_ALPHABET) == len(set(CROCKFORD_ALPHABET)) == 32
    assert not set(CROCKFORD_ALPHABET) & set("ilou")
    assert set(CROCKFORD_ALPHABET) <= set("abcdefghijklmnopqrstuvwxyz0123456789")


def test_an_item_id_carries_the_address_bytes_with_nothing_padded() -> None:
    """Sixteen symbols hold exactly eighty bits, so the id is the ten bytes and not a lossy print.

    That is the whole reason for those two numbers together. A width that did not
    divide would pad, and padding is a character that says nothing - which is how
    an id gets longer without getting harder to collide.
    """
    key = derive_url_key("https://lab.example.org/a-story")
    address = item_id("ai", key)
    symbols = address.removeprefix("ai-")

    assert len(symbols) == ITEM_ID_SYMBOLS == 16
    assert re.fullmatch(ITEM_ID_PATTERN, address)
    read_back = 0
    for symbol in symbols:
        read_back = read_back * 32 + CROCKFORD_ALPHABET.index(symbol)
    assert read_back.to_bytes(ITEM_ID_BYTES, "big") == bytes.fromhex(key)[:ITEM_ID_BYTES]


def test_an_item_id_is_a_function_of_the_address_and_the_desk() -> None:
    """Same address twice is one id; a different address is a different id."""
    one = derive_url_key("https://lab.example.org/one")
    two = derive_url_key("https://lab.example.org/two")
    assert item_id("ai", one) == item_id("ai", one)
    assert item_id("ai", one) != item_id("ai", two)
    assert item_id("energy", one) != item_id("ai", one)
    assert item_id("business-economy", one).startswith("business-economy-")


def test_dedup_text_joins_the_headline_and_the_lead() -> None:
    assert dedup_text("Grid outage", "Power back by dawn") == "Grid outage Power back by dawn"


def test_dedup_text_is_the_headline_alone_when_there_is_no_lead() -> None:
    assert dedup_text("Grid outage", None) == "Grid outage"


def test_a_story_with_no_headline_earns_no_text() -> None:
    """No title, nothing to compare: the item is never a would-cut duplicate."""
    assert dedup_text(None, "a lead with no headline") is None


def test_the_weaker_telling_of_a_cross_source_pair_is_recorded() -> None:
    strong = _planned("ai", 1, source_id="alpha", rank_score=10.0)
    weak = _planned("ai", 2, source_id="beta", rank_score=5.0)
    vectors = {strong.item_id: _SAME, weak.item_id: _SAME}
    findings = duplicates_within_plan([strong, weak], vectors, similarity_min=0.94)
    assert len(findings) == 1
    assert findings[0].item is weak, "the lower-ranked telling is the one that would be cut"
    assert findings[0].duplicate_of is strong, "it is recorded against the stronger telling"
    assert findings[0].similarity == pytest.approx(1.0)


def test_a_same_source_pair_is_never_a_duplicate() -> None:
    """max_per_source already bounds a feed's own repeats; this pass is about two sources."""
    first = _planned("ai", 1, source_id="alpha", rank_score=10.0)
    second = _planned("ai", 2, source_id="alpha", rank_score=5.0)
    vectors = {first.item_id: _SAME, second.item_id: _SAME}
    assert duplicates_within_plan([first, second], vectors, similarity_min=0.94) == []


def test_a_desks_only_story_is_never_recorded() -> None:
    """A single-carrier story scores lowest, so a naive cut would take the exclusive one.

    `ai` carries one story that repeats `ml`'s top story exactly. The guard is the
    desk's item count, so the lone `ai` story is kept and never recorded (row 52).
    """
    lone = _planned("ai", 1, source_id="alpha", rank_score=5.0)
    strong = _planned("ml", 1, source_id="beta", rank_score=10.0)
    filler = _planned("ml", 2, source_id="gamma", rank_score=2.0)
    vectors = {lone.item_id: _SAME, strong.item_id: _SAME, filler.item_id: _OTHER}
    assert duplicates_within_plan([lone, strong, filler], vectors, similarity_min=0.94) == []


def test_the_same_story_on_a_busy_desk_is_recorded() -> None:
    """The contrast to the guard: when the repeat's desk has more than one story,
    the weaker telling is recorded rather than protected.
    """
    strong = _planned("ai", 1, source_id="alpha", rank_score=10.0)
    weak = _planned("ai", 2, source_id="beta", rank_score=5.0)
    keeps_desk_busy = _planned("ai", 3, source_id="gamma", rank_score=1.0)
    vectors = {strong.item_id: _SAME, weak.item_id: _SAME, keeps_desk_busy.item_id: _OTHER}
    findings = duplicates_within_plan([strong, weak, keeps_desk_busy], vectors, similarity_min=0.94)
    assert [finding.item.item_id for finding in findings] == [weak.item_id]


def test_below_the_threshold_is_not_a_duplicate() -> None:
    one = _planned("ai", 1, source_id="alpha", rank_score=10.0)
    two = _planned("ai", 2, source_id="beta", rank_score=5.0)
    vectors = {one.item_id: _SAME, two.item_id: _OTHER}  # cosine 0.0, below 0.94
    assert duplicates_within_plan([one, two], vectors, similarity_min=0.94) == []


def test_an_item_with_no_vector_is_never_a_duplicate() -> None:
    """A titleless item earns no text and so no vector; it cannot be a would-cut."""
    strong = _planned("ai", 1, source_id="alpha", rank_score=10.0)
    untitled = _planned("ai", 2, source_id="beta", rank_score=5.0, title=None)
    vectors = {strong.item_id: _SAME}  # untitled has no entry
    assert duplicates_within_plan([strong, untitled], vectors, similarity_min=0.94) == []


def test_a_cluster_of_three_keeps_only_the_strongest_telling() -> None:
    """Three tellings from three sources: the two weaker are recorded, and both
    against the top telling - a would-cut is never itself a match for a later one,
    so the count is what enforcing would actually remove.
    """
    top = _planned("ai", 1, source_id="alpha", rank_score=10.0)
    middle = _planned("ai", 2, source_id="beta", rank_score=6.0)
    bottom = _planned("ai", 3, source_id="gamma", rank_score=4.0)
    vectors = {top.item_id: _SAME, middle.item_id: _SAME, bottom.item_id: _SAME}
    findings = duplicates_within_plan([top, middle, bottom], vectors, similarity_min=0.94)
    assert {finding.item.item_id for finding in findings} == {middle.item_id, bottom.item_id}
    assert all(finding.duplicate_of.item_id == top.item_id for finding in findings)


# --- the real encoder, on the committed weights, reaching no network ---------


def test_the_encoder_finds_a_repeat_and_reaches_no_network() -> None:
    """The pass over the committed ONNX encoder: two sources spelling one headline
    embed to the same vector and the weaker telling is recorded. The encoder is a
    local file, so this reaches no network (Guardrail #7).
    """
    embedder = Embedder(REPO_ROOT, AssistConfig())
    assert embedder.available, "the committed ONNX encoder must be present for this test"
    embedder.load()
    headline = "Grid restored after a day-long outage"
    strong = _planned("ai", 1, source_id="alpha", rank_score=10.0, title=headline)
    weak = _planned("ai", 2, source_id="beta", rank_score=5.0, title=headline)
    text_strong = dedup_text(strong.title, None)
    text_weak = dedup_text(weak.title, None)
    assert text_strong is not None and text_weak is not None
    vectors = dict(
        zip(
            [strong.item_id, weak.item_id],
            embedder.encode([text_strong, text_weak]),
            strict=True,
        )
    )
    findings = duplicates_within_plan([strong, weak], vectors, similarity_min=0.94)
    assert [finding.item.item_id for finding in findings] == [weak.item_id]
    assert findings[0].similarity == pytest.approx(1.0, abs=1e-6)


# --- the record-only wiring: what it writes down, and what it never cuts ------


def test_record_only_logs_the_would_cut_pair_and_removes_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The row's promise: on the shipping config the pass records and cuts nothing."""
    headline = "Grid restored after a day-long outage"
    strong = _planned("ai", 1, source_id="alpha", rank_score=10.0, title=headline)
    weak = _planned("ai", 2, source_id="beta", rank_score=5.0, title=headline)
    collect = CollectConfig()
    assert collect.dedup_enforce is False, "the shipping default is record-only"
    embedder = Embedder(REPO_ROOT, AssistConfig())
    with caplog.at_level(logging.INFO):
        kept = _record_plan_duplicates(
            [strong, weak], embedder=embedder, leads={}, collect=collect
        )
    assert kept == [strong, weak], "record-only removes nothing"
    assert any(
        "would-collapse" in message and weak.item_id in message for message in caplog.messages
    )
    assert any("plan duplicates recorded count=1" in message for message in caplog.messages)


def test_enforcing_cuts_the_weaker_telling() -> None:
    """The same pass with the flag flipped: the lower-ranked telling is removed."""
    headline = "Grid restored after a day-long outage"
    strong = _planned("ai", 1, source_id="alpha", rank_score=10.0, title=headline)
    weak = _planned("ai", 2, source_id="beta", rank_score=5.0, title=headline)
    embedder = Embedder(REPO_ROOT, AssistConfig())
    kept = _record_plan_duplicates(
        [strong, weak], embedder=embedder, leads={}, collect=CollectConfig(dedup_enforce=True)
    )
    assert kept == [strong], "enforcing keeps the stronger telling and drops the weaker"


# --- Where a story publishes -----------------------------------------------
#
# `desk_of` is the whole rule in one function: the feed floor counts feeds, a
# feed declares a vertical, and a story relabelled onto a name this run will not
# render falls back to the word its feed declared.
# Every case here is built in memory; nothing reads the plan tree.


def _vertical_plan(vertical_id: str, *, below_floor: bool) -> VerticalPlan:
    # A vertical under its floor plans nothing, and `VerticalPlan` refuses a row
    # that says otherwise - so the flag and the count move together here too.
    return VerticalPlan(
        id=vertical_id,
        considered=4,
        planned=0 if below_floor else 1,
        eligible_feeds=1 if below_floor else 40,
        feed_floor=21,
        below_feed_floor=below_floor,
    )


def test_an_unlabelled_story_names_no_desk_at_all() -> None:
    """The ordinary case, and the only one on every day published so far.

    Null is not a quiet way of writing the vertical. Nothing reads an article
    yet, so writing the feed's word here would make every item claim a reading
    of itself that never happened. The page falls back; the payload does not.
    """
    assert desk_of("energy", None, below_floor=frozenset()) is None
    assert desk_of("energy", None, below_floor=frozenset({"energy"})) is None


def test_a_relabelled_story_publishes_under_its_desk() -> None:
    """The case the whole row exists for: an energy feed carrying an AI story."""
    assert desk_of("energy", "ai", below_floor=frozenset()) == "ai"


def test_a_desk_below_its_own_floor_falls_back_to_the_feeds_word() -> None:
    """Decision 8, stated as the contradiction it prevents.

    A vertical under its floor is collected and never rendered, and the day
    payload says so in `below_feed_floor`. Without this fallback an above-floor
    vertical's stories would land under that name and render - so the reading
    page would draw a topic the operator surface says planned nothing, and both
    would be reading the same day.
    """
    assert desk_of("energy", "ai", below_floor=frozenset({"ai"})) == "energy"


def test_a_story_already_on_its_own_below_floor_vertical_is_left_alone() -> None:
    """The floor is about supply, and it never moves a story off its own feed.

    An `ai` feed's story stays `ai` whatever the floor says. The fallback exists
    to stop a story ARRIVING on a name that will not render; a story whose feed
    declares that name was never going to render either way, and rewriting it
    here would put it on a topic no feed carried it under.
    """
    assert desk_of("ai", "ai", below_floor=frozenset({"ai"})) == "ai"


def test_the_below_floor_set_is_read_off_this_runs_own_plan() -> None:
    """Which names are under their floor is a fact about a run, not about config.

    It depends on how many of each vertical's addresses were lawfully askable
    today, so it is read from the plan this run wrote rather than recomputed
    from `config/taxonomy.json` - which cannot know what today's robots.txt
    said.
    """
    plans = [
        _vertical_plan("ai", below_floor=True),
        _vertical_plan("energy", below_floor=False),
        _vertical_plan("world", below_floor=True),
    ]
    assert desks_below_floor(plans) == frozenset({"ai", "world"})
    assert desks_below_floor([]) == frozenset()
