"""Unit checks for the feed admission utility."""

from __future__ import annotations

from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.sources import Sources
from utilities import probe_feeds


def article_probe(
    verdict: str,
    *,
    evidence: probe_feeds.ArticlePaywallEvidence = "none",
) -> probe_feeds.ArticleProbe:
    return probe_feeds.ArticleProbe(
        url="https://example.org/article",
        fetch_ms=1,
        extract_ms=1,
        http_status=200,
        outcome="ok",
        words=1 if verdict == ArticleStatus.OK.value else 0,
        verdict=verdict,
        detail=None,
        paywall_evidence=evidence,
    )


def source_catalog(feed_url: str, feed_id: str) -> Sources:
    return Sources.model_validate(
        {
            "publishers": [],
            "feeds": [
                {
                    "added_on": "2026-10-26",
                    "form": "article",
                    "kind": "analysis",
                    "publisher_id": None,
                    "retirement_reason": None,
                    "retired_on": None,
                    "status": "active",
                    "tier": 3,
                    "vertical": "business-economy",
                    "weight": 1.0,
                    "id": feed_id,
                    "title": "Sample Feed",
                    "url": feed_url,
                }
            ],
            "salience": [],
            "retired": [],
        }
    )


def test_probe_samples_three_articles_by_default() -> None:
    assert probe_feeds.parse_args([]).articles == 3


def test_one_paywall_sample_is_not_confirmed() -> None:
    passed, verdict = probe_feeds.resolve_probe_verdict(
        [
            article_probe(
                FailureCode.PAYWALLED.value,
                evidence="configured-marker",
            )
        ]
    )

    assert not passed
    assert verdict == probe_feeds.PAYWALL_NOT_CONFIRMED


def test_two_matching_paywall_samples_confirm_paywall() -> None:
    passed, verdict = probe_feeds.resolve_probe_verdict(
        [
            article_probe(
                FailureCode.PAYWALLED.value,
                evidence="json-ld",
            ),
            article_probe(
                FailureCode.PAYWALLED.value,
                evidence="configured-marker",
            ),
        ]
    )

    assert not passed
    assert verdict == FailureCode.PAYWALLED.value


def test_mixed_sample_is_not_confirmed() -> None:
    passed, verdict = probe_feeds.resolve_probe_verdict(
        [
            article_probe(
                FailureCode.PAYWALLED.value,
                evidence="configured-marker",
            ),
            article_probe(FailureCode.NOT_PROSE.value),
        ]
    )

    assert not passed
    assert verdict == probe_feeds.PAYWALL_NOT_CONFIRMED


def test_one_readable_article_still_passes_the_feed() -> None:
    passed, verdict = probe_feeds.resolve_probe_verdict(
        [
            article_probe(
                FailureCode.PAYWALLED.value,
                evidence="configured-marker",
            ),
            article_probe(ArticleStatus.OK.value),
        ]
    )

    assert passed
    assert verdict == ArticleStatus.OK.value


def test_normalized_feed_url_finds_duplicate() -> None:
    sources = source_catalog(
        "https://www.thevccorner.com/feed",
        "the-vc-corner",
    )

    duplicate = probe_feeds.find_source_duplicate(
        "https://thevccorner.com/feed/",
        sources,
    )

    assert duplicate is not None
    assert duplicate.url_matches == ("the-vc-corner",)


def test_derived_source_id_finds_duplicate() -> None:
    sources = source_catalog(
        "https://example.org/feed",
        "thevccorner",
    )

    duplicate = probe_feeds.find_source_duplicate(
        "https://thevccorner.com/rss.xml",
        sources,
    )

    assert duplicate is not None
    assert duplicate.id_matches == ("thevccorner",)


def test_new_feed_url_and_id_have_no_duplicate() -> None:
    sources = source_catalog(
        "https://example.org/feed",
        "example-feed",
    )

    assert (
        probe_feeds.find_source_duplicate(
            "https://new.example.org/feed",
            sources,
        )
        is None
    )
