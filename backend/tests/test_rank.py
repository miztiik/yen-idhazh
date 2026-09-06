"""How a feed's recent record scales its authority.

The reliability factor is derived from the committed feed-health ledger and
applied multiplicatively inside `authority`. These tests pin the two promises
the factor makes: it never rises above 1.0, so it can only ever reduce a score,
and it never falls below the configured floor, so it can never remove a feed.

Every health row here is built in memory. No test reads state/, so the archive
is never the input and the cost of these tests does not grow with it (CLAUDE.md
Rule #12 and the section 13 test policy).
"""

from __future__ import annotations

import pytest

from idhazh.contracts.app_config import CollectConfig
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import SourceTier
from idhazh.discover import Candidate
from idhazh.ledger import feed_reliability
from idhazh.rank import authority, score, tier_weight

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
        on_front_page=False,
        appeared=None,
        now=STAMP,
    )
    reduced = score(
        carried,
        config=CONFIG,
        watchlist_hit=False,
        on_front_page=False,
        appeared=None,
        now=STAMP,
        reliability={"a-feed": 0.5},
    )
    assert reduced == pytest.approx(full * 0.5)
    assert reduced < full
