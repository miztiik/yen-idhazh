"""Unit-tier tests for fetch policy and extraction.

Every fetch decision worth getting wrong is a pure function over a status code,
a robots file or an address, so all of them are tested and none of them needs a
socket. The one function that opens a connection is a thin wrapper and is not
exercised here - there is no mock standing in for it (Rule #7).

The extraction tests are about the trust boundary and about the failures that
are supposed to degrade rather than raise.
"""

from __future__ import annotations

import json

import pytest
from conftest import FIXTURES_DIR, read_text

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.taxonomy import SourceTier
from idhazh.extract import (
    EXTRACTOR_VERSION,
    boilerplate_ratio,
    declares_paywall,
    extract_text,
    to_article,
    truncate_to_tokens,
)
from idhazh.fetch import (
    FetchResult,
    address_is_dialable,
    backoff_delays,
    classify_status,
    read_capped,
    robots_allows,
    robots_from_result,
    robots_url,
)

PAGES = FIXTURES_DIR / "pages"
SHORT_SOURCES = FIXTURES_DIR / "short-sources"
FETCHED_AT = "2026-08-21T06:03:11Z"
CANONICAL = "https://newsroom.example-grid.com/2026/08/reactor-order"

ITEM = PlannedItem(
    item_id="energy-01",
    url_key=derive_url_key(CANONICAL),
    source_url=CANONICAL,
    canonical_url=CANONICAL,
    source_id="grid-newsroom",
    tier=SourceTier.INSTITUTION,
    vertical="energy",
    title="Example Grid orders four small modular reactors",
    rank_score=1.4,
)


def page(name: str) -> str:
    return read_text(PAGES / name)


def ok(name: str) -> FetchResult:
    return FetchResult(FetchOutcome.OK, status=200, body=page(name).encode("utf-8"))


def fixture_item(source_id: str, url: str, index: int = 1) -> PlannedItem:
    return PlannedItem(
        item_id=f"energy-{index:02d}",
        url_key=derive_url_key(url),
        source_url=url,
        canonical_url=url,
        source_id=source_id,
        tier=SourceTier.INSTITUTION,
        vertical="energy",
        title=f"{source_id} fixture",
        rank_score=1.0,
    )


def disposition(article_status: ArticleStatus, brief: bool, code: FailureCode | None) -> str:
    if article_status is ArticleStatus.OK:
        return "publish_brief" if brief else "publish_full"
    if code is FailureCode.PAYWALLED:
        return "reject_paywalled"
    if code in {FailureCode.NOT_PROSE, FailureCode.BOILERPLATE}:
        return "reject_listing"
    return "reject_listing"


# --- Where a request may be sent --------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8080/admin",
        "http://localhost/",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://build.internal/secrets",
        "file:///etc/passwd",
        "gopher://example.org/",
    ],
)
def test_a_hostile_feed_cannot_aim_the_fetcher_inward(url: str) -> None:
    """A feed is a stranger's list of addresses to request from inside CI."""
    dialable, why = address_is_dialable(url)
    assert not dialable
    assert why


@pytest.mark.parametrize("url", ["https://newsroom.example-grid.com/a", "http://example.org/b?c=1"])
def test_an_ordinary_public_address_is_dialable(url: str) -> None:
    assert address_is_dialable(url) == (True, None)


# --- Asking the host -------------------------------------------------------


def test_a_disallowed_path_is_refused() -> None:
    robots = "User-agent: *\nDisallow: /private/\n"
    assert not robots_allows(robots, "yen-idhazh/1.0", "https://x.example/private/a")
    assert robots_allows(robots, "yen-idhazh/1.0", "https://x.example/public/a")


def test_a_blanket_disallow_is_refused() -> None:
    assert not robots_allows(
        "User-agent: *\nDisallow: /\n", "yen-idhazh/1.0", "https://x.example/a"
    )


def test_an_unreachable_robots_file_is_a_refusal_not_a_permission() -> None:
    """Assuming consent from silence is how a polite crawler becomes an impolite one."""
    result = fetch_without_network()
    assert result.outcome is FetchOutcome.ROBOTS_DENIED


def fetch_without_network() -> FetchResult:
    from idhazh.fetch import fetch

    return fetch("https://example.org/a", config=ExtractConfig(), robots_txt=None)


# --- What one robots.txt response means (RFC 9309 section 2.3.1) ------------


def test_a_served_robots_file_is_the_rules() -> None:
    body = b"User-agent: *\nDisallow: /private/\n"
    assert robots_from_result(FetchResult(FetchOutcome.OK, status=200, body=body)) == body.decode()


@pytest.mark.parametrize("status", [401, 403, 404, 410, 451])
def test_a_host_that_publishes_no_rules_is_allow_all(status: int) -> None:
    """RFC 9309 sec 2.3.1.3: a 4xx other than 429 means the crawler may access anything.

    Ten of our feeds sit on hosts that serve no robots.txt at all. Reading that
    as a refusal was us inventing a rule the host never wrote.
    """
    rules = robots_from_result(FetchResult(classify_status(status), status=status))
    assert rules == ""
    assert robots_allows(rules or "", "yen-idhazh/1.0", "https://x.example/a")


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_a_host_that_did_not_answer_stays_a_refusal(status: int) -> None:
    """RFC 9309 sec 2.3.1.4: unreachable means the rules are unknown, so assume disallow."""
    assert robots_from_result(FetchResult(classify_status(status), status=status)) is None


def test_a_network_failure_stays_a_refusal() -> None:
    assert robots_from_result(FetchResult(FetchOutcome.TRANSIENT, detail="TimeoutError")) is None


def test_a_blocked_address_stays_a_refusal() -> None:
    assert robots_from_result(FetchResult(FetchOutcome.BLOCKED, detail="resolves inward")) is None


def test_robots_is_looked_for_at_the_host_root() -> None:
    assert robots_url("https://x.example/deep/path?q=1") == "https://x.example/robots.txt"


# --- Retry budget -----------------------------------------------------------


@pytest.mark.parametrize("status", [200, 204])
def test_a_success_is_a_success(status: int) -> None:
    assert classify_status(status) is FetchOutcome.OK


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504, 408])
def test_a_transient_status_is_worth_retrying(status: int) -> None:
    assert classify_status(status) is FetchOutcome.TRANSIENT


@pytest.mark.parametrize("status", [401, 403, 404, 410, 451])
def test_a_permanent_status_is_recorded_and_skipped(status: int) -> None:
    """Retrying a 404 burns the budget the transient failures need."""
    assert classify_status(status) is FetchOutcome.PERMANENT


def test_the_retry_budget_is_finite_and_config_driven() -> None:
    delays = backoff_delays(ExtractConfig())
    assert len(delays) == ExtractConfig().max_retries
    assert delays == sorted(delays), "backoff grows"
    assert delays != sorted(delays, reverse=True)


def test_a_zero_retry_budget_is_honoured() -> None:
    assert backoff_delays(ExtractConfig(max_retries=0)) == []


# --- Bodies -----------------------------------------------------------------


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, size: int) -> bytes:
        return self._payload[:size]


def test_an_oversized_body_is_capped_and_says_so() -> None:
    body, truncated = read_capped(_Response(b"x" * 500), 100)
    assert len(body) == 100
    assert truncated


def test_a_body_inside_the_cap_is_not_flagged() -> None:
    body, truncated = read_capped(_Response(b"x" * 50), 100)
    assert body == b"x" * 50
    assert not truncated


# --- Extraction: the trust boundary -----------------------------------------


def test_the_article_survives_and_the_furniture_does_not() -> None:
    text = extract_text(page("article.html"))
    assert text is not None
    assert "four small modular reactors" in text
    for furniture in ("Subscribe", "Sign up for our daily briefing", "All rights reserved"):
        assert furniture not in text


def test_a_hostile_page_crosses_the_boundary_sanitized() -> None:
    text = extract_text(page("hostile.html"))
    assert text is not None
    assert "collect.canary.example" not in text
    assert "<|im_start|>" not in text
    assert "ignore the article" not in text.lower(), "an HTML comment is a hiding place"
    assert "1.4 gigawatts" in text


def test_a_page_with_no_article_extracts_to_nothing() -> None:
    empty = FetchResult(FetchOutcome.OK, status=200, body=b"<html><body></body></html>")
    article = to_article(
        ITEM, empty, config=ExtractConfig(), fetched_at=FETCHED_AT
    )
    assert article.status is ArticleStatus.EXTRACT_FAILED
    assert article.failure_detail
    assert article.text is None


def test_a_real_page_becomes_an_ok_payload() -> None:
    article = to_article(ITEM, ok("article.html"), config=ExtractConfig(), fetched_at=FETCHED_AT)
    assert article.status is ArticleStatus.OK
    assert article.text
    assert article.word_count > 0
    assert article.extractor_version == EXTRACTOR_VERSION
    assert article.url_key == derive_url_key(CANONICAL)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (FetchOutcome.ROBOTS_DENIED, ArticleStatus.ROBOTS_DENIED),
        (FetchOutcome.BLOCKED, ArticleStatus.ROBOTS_DENIED),
        (FetchOutcome.PERMANENT, ArticleStatus.FETCH_FAILED),
        (FetchOutcome.TRANSIENT, ArticleStatus.FETCH_FAILED),
    ],
)
def test_every_failure_is_a_state_of_the_payload(
    outcome: FetchOutcome, expected: ArticleStatus
) -> None:
    """Degrade, do not fail: a dead link never takes a sibling down with it."""
    article = to_article(
        ITEM,
        FetchResult(outcome, detail="recorded reason"),
        config=ExtractConfig(),
        fetched_at=FETCHED_AT,
    )
    assert article.status is expected
    assert article.failure_detail == "recorded reason"


def test_a_short_extraction_publishes_as_brief() -> None:
    """Length is not an editorial test."""
    thin = FetchResult(
        FetchOutcome.OK, status=200, body=b"<html><body><p>Two words.</p></body></html>"
    )
    article = to_article(ITEM, thin, config=ExtractConfig(), fetched_at=FETCHED_AT)
    assert article.status is ArticleStatus.OK
    assert article.brief
    assert article.failure_code in {FailureCode.TOO_SHORT, FailureCode.NOT_PROSE}


def test_not_prose_can_be_rejected_when_the_operator_sets_the_knob() -> None:
    thin = FetchResult(
        FetchOutcome.OK, status=200, body=b"<html><body><p>Two words.</p></body></html>"
    )
    article = to_article(
        ITEM,
        thin,
        config=ExtractConfig(reject_not_prose=True),
        fetched_at=FETCHED_AT,
    )
    assert article.status is ArticleStatus.EXTRACT_FAILED
    assert article.failure_code is FailureCode.NOT_PROSE


def test_a_declared_paywall_is_rejected_before_extraction() -> None:
    html = read_text(SHORT_SOURCES / "japan-times-01.html")
    article = to_article(
        fixture_item("japan-times", "https://www.japantimes.co.jp/news/example/", 1),
        FetchResult(FetchOutcome.OK, status=200, body=html.encode("utf-8")),
        config=ExtractConfig(),
        fetched_at=FETCHED_AT,
    )

    assert declares_paywall(html)
    assert article.status is ArticleStatus.EXTRACT_FAILED
    assert article.failure_code is FailureCode.PAYWALLED


def test_a_pdf_feed_item_has_a_typed_unsupported_form() -> None:
    pdf_url = "https://example.org/research/paper.pdf"
    item = fixture_item("example", pdf_url, 1)
    article = to_article(
        item,
        FetchResult(FetchOutcome.OK, status=200, body=b"%PDF-1.7"),
        config=ExtractConfig(),
        fetched_at=FETCHED_AT,
    )

    assert article.status is ArticleStatus.EXTRACT_FAILED
    assert article.failure_code is FailureCode.UNSUPPORTED_FORM


# --- Truncation is flagged, never silent -------------------------------------


def test_text_inside_the_cap_is_untouched() -> None:
    text, truncated, cut = truncate_to_tokens("one two three", 2500)
    assert (text, truncated, cut) == ("one two three", False, None)


def test_text_over_the_cap_is_cut_and_flagged() -> None:
    long_text = " ".join(["word"] * 5000)
    text, truncated, cut = truncate_to_tokens(long_text, 100)
    assert truncated
    assert cut == 100
    assert len(text.split()) < 5000


def test_truncation_is_deterministic() -> None:
    long_text = " ".join(f"w{n}" for n in range(5000))
    assert truncate_to_tokens(long_text, 100) == truncate_to_tokens(long_text, 100)


def test_a_truncated_article_records_where_it_was_cut() -> None:
    article = to_article(
        ITEM,
        ok("article.html"),
        config=ExtractConfig(truncation_cap_tokens=256),
        fetched_at=FETCHED_AT,
    )
    assert article.truncated
    assert article.truncated_at_tokens == 256


# --- Chrome detection --------------------------------------------------------


def test_lines_shared_across_sibling_pages_read_as_chrome() -> None:
    """Comparing pages against each other beats any score computed from one page."""
    seen = {"Subscribe", "All rights reserved", "Related stories"}
    assert boilerplate_ratio(["Subscribe", "All rights reserved", "Real sentence."], seen) > 0.6


def test_an_article_is_not_mostly_chrome() -> None:
    seen = {"Subscribe"}
    lines = ["Subscribe", "A real sentence.", "Another real sentence.", "A third one."]
    assert boilerplate_ratio(lines, seen) < 0.3


def test_an_empty_page_is_not_reported_as_chrome() -> None:
    assert boilerplate_ratio([], {"Subscribe"}) == 0.0


def test_boilerplate_signal_publishes_by_default_and_can_reject() -> None:
    html = (
        "<html><body><article>"
        "<p>Shared navigation</p>"
        "<p>This sentence has enough words to count as article prose today.</p>"
        "<p>Another sentence has enough words to count as article prose today.</p>"
        "<p>A third sentence has enough words to count as article prose today.</p>"
        "</article></body></html>"
    )
    seen = {
        "Shared navigation",
        "This sentence has enough words to count as article prose today.",
        "Another sentence has enough words to count as article prose today.",
    }
    article = to_article(
        ITEM,
        FetchResult(FetchOutcome.OK, status=200, body=html.encode("utf-8")),
        config=ExtractConfig(boilerplate_ratio_max=0.4),
        fetched_at=FETCHED_AT,
        seen_elsewhere=seen,
    )
    rejected = to_article(
        ITEM,
        FetchResult(FetchOutcome.OK, status=200, body=html.encode("utf-8")),
        config=ExtractConfig(boilerplate_ratio_max=0.4, reject_boilerplate=True),
        fetched_at=FETCHED_AT,
        seen_elsewhere=seen,
    )

    assert article.status is ArticleStatus.OK
    assert article.failure_code is FailureCode.BOILERPLATE
    assert rejected.status is ArticleStatus.EXTRACT_FAILED
    assert rejected.failure_code is FailureCode.BOILERPLATE


def test_the_labelled_short_source_oracle_matches_disposition_and_reason() -> None:
    for meta_path in sorted(SHORT_SOURCES.glob("*.json")):
        meta = json.loads(read_text(meta_path))
        html_path = meta_path.with_suffix(".html")
        item = fixture_item(meta["source_id"], meta["source_url"], 1)
        article = to_article(
            item,
            FetchResult(FetchOutcome.OK, status=200, body=html_path.read_bytes()),
            config=ExtractConfig(),
            fetched_at=FETCHED_AT,
        )
        expected_reason = meta["expected_reason"]
        observed_reason = article.failure_code.value if article.failure_code is not None else None

        assert disposition(article.status, article.brief, article.failure_code) == meta["label"]
        assert observed_reason == expected_reason
