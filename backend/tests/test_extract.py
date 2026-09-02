"""Unit-tier tests for fetch policy and extraction.

Every fetch decision worth getting wrong is a pure function over a status code,
a robots file or an address, so all of them are tested and none of them needs a
socket. The function that opens the connection is a thin wrapper; where the
order of two reads is the thing under test, the socket edge is supplied as a
reader over a committed capture rather than mocked (Rule #7).

The extraction tests are about the trust boundary and about the failures that
are supposed to degrade rather than raise.

CI runs this whole file on both ends of the interpreter range `pyproject.toml`
declares, because the robots corpus below has to read the same way on each.
"""

from __future__ import annotations

import hashlib
import json
from typing import NamedTuple

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, read_text

from idhazh import cli, config
from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.article import ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import SourceForm
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
    ROBOTS_REFUSALS,
    FetchResult,
    RobotsRules,
    address_is_dialable,
    backoff_delays,
    classify_status,
    fetch,
    origin,
    read_capped,
    refused,
    robots_rules,
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
        source_form=SourceForm.ABSTRACT if source_id == "nber-new" else SourceForm.ARTICLE,
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

ROBOTS = FIXTURES_DIR / "robots"
AGENT = "yen-idhazh/1.0 (+https://github.com/miztiik/yen-idhazh)"
HOST = "https://x.example"

#: Every path the corpus is asked about, in the order the digest below covers.
ROBOTS_PATHS = (
    "/",
    "/public/a",
    "/private/a",
    "/alpha/x",
    "/beta/x",
    "/gamma/x",
    "/docs/public/a",
    "/docs/private/a",
    "/ledger",
    "/a/b.pdf",
    "/a/b.pdf?x=1",
    "/tmp/1/cache/z",
    "/tmp/1/keep/z",
    "/~archive/x",
    "/%7Earchive/x",
    "/reports/a%2Fb",
    "/reports/a/b",
    "/orphan/a",
    "/nocolon/a",
)

#: What the whole corpus answers, as one value. Recorded 2026-09-02 against
#: protego 0.6.2 over 10 files and 19 paths, on CPython 3.14.2. CI runs this
#: file on 3.12 and 3.14, so an interpreter that reads one rule differently
#: moves this digest and fails.
ROBOTS_GRID_DIGEST = "2fe013ae24d46ba4ac7fb6b276dbca15c9d3f792597d5c74834ca000b132a3eb"


class RobotsCase(NamedTuple):
    """One committed file, what it is here to cover, and both of its answers."""

    fixture: str
    covers: str
    allowed: tuple[str, ...]
    denied: tuple[str, ...]


ROBOTS_CASES = (
    RobotsCase(
        "crawler-specific-group.txt",
        "a group naming this crawler beats the wildcard group",
        ("/", "/public/a"),
        ("/private/a",),
    ),
    RobotsCase(
        "another-crawlers-group.txt",
        "a group naming somebody else does not bind us, and the wildcard group does",
        ("/", "/public/a"),
        ("/private/a",),
    ),
    RobotsCase(
        "repeated-groups.txt",
        "two groups for one agent are one group",
        ("/gamma/x",),
        ("/alpha/x", "/beta/x"),
    ),
    RobotsCase(
        "longest-match.txt",
        "the longest matching rule wins, whichever order the two are written in",
        ("/docs/public/a",),
        ("/docs/private/a",),
    ),
    RobotsCase(
        "wildcards.txt",
        "a star spans anything and a dollar pins the end of the path",
        ("/a/b.pdf?x=1", "/tmp/1/keep/z"),
        ("/a/b.pdf", "/tmp/1/cache/z"),
    ),
    RobotsCase(
        "percent-encoding.txt",
        "an unreserved character survives encoding, and a reserved one is a different path",
        ("/reports/a/b",),
        ("/~archive/x", "/%7Earchive/x", "/reports/a%2Fb"),
    ),
    RobotsCase(
        "malformed.txt",
        "a rule before any group, a line with no colon, and a field nobody defined",
        ("/orphan/a", "/nocolon/a"),
        ("/private/a",),
    ),
)


def rules_for(fixture: str) -> RobotsRules:
    """Read a committed file the way a run reads a served one."""
    return robots_rules(FetchResult(FetchOutcome.OK, status=200, body=(ROBOTS / fixture).read_bytes()))


@pytest.mark.parametrize("case", ROBOTS_CASES, ids=lambda case: case.fixture)
def test_a_committed_robots_file_permits_and_refuses_exactly_what_it_says(
    case: RobotsCase,
) -> None:
    """One file, both answers, so a swapped call cannot pass.

    `Protego.can_fetch` takes the URL first and the agent second, the opposite
    order to the standard library's `RobotFileParser.can_fetch`. A swap is
    silent: it answers every question the same way, so a case that only ever
    expected a refusal would pass with the arguments the wrong way round. Every
    case here carries at least one of each.
    """
    assert case.allowed and case.denied, f"{case.fixture} must cover both answers"
    rules = rules_for(case.fixture)
    for path in case.allowed:
        assert rules.permits(AGENT, HOST + path) is RobotsOutcome.ALLOWED, case.covers
    for path in case.denied:
        assert rules.permits(AGENT, HOST + path) is RobotsOutcome.DENIED, case.covers


def test_an_allowance_wins_a_tie_and_a_blanket_refusal_still_refuses() -> None:
    """RFC 9309 section 2.2.2, with its control beside it.

    One path and two files, so a call that answered every question the same way
    fails here whichever constant it returned.
    """
    assert rules_for("allow-on-tie.txt").permits(AGENT, f"{HOST}/ledger") is RobotsOutcome.ALLOWED
    assert (
        rules_for("blanket-disallow.txt").permits(AGENT, f"{HOST}/ledger") is RobotsOutcome.DENIED
    )


def test_a_file_that_publishes_no_rules_permits_every_path() -> None:
    rules = rules_for("no-rules.txt")
    for path in ROBOTS_PATHS:
        assert rules.permits(AGENT, HOST + path) is RobotsOutcome.ALLOWED


def test_a_group_naming_another_crawler_does_not_bind_us() -> None:
    """Our identity carries a contact address, and it is what we are judged as.

    The same file refuses a crawler with no group of its own, which is what
    says the wildcard group is being read rather than ignored.
    """
    rules = rules_for("crawler-specific-group.txt")
    assert rules.permits(AGENT, f"{HOST}/") is RobotsOutcome.ALLOWED
    assert rules.permits("GPTBot", f"{HOST}/") is RobotsOutcome.DENIED


def test_the_whole_corpus_reads_the_same_way_on_every_supported_python() -> None:
    """The oracle CI runs twice: one digest over every file and every path.

    `robots.txt` is a permission, and until 2026-09-02 the standard library
    read one file two ways across the range `pyproject.toml` declares - 3.12
    takes the first matching group and the first matching rule, 3.14 merges
    repeated groups and applies longest-match. Which pages this crawler may
    read is not allowed to depend on which runner picked up the job.
    """
    names = sorted(path.name for path in ROBOTS.glob("*.txt"))
    assert len(names) == len(ROBOTS_CASES) + 3, "every fixture is named by a case or its own test"
    grid = "\n".join(
        f"{name} {path} {rules_for(name).permits(AGENT, HOST + path).value}"
        for name in names
        for path in ROBOTS_PATHS
    )
    assert len(grid.splitlines()) == len(names) * len(ROBOTS_PATHS)
    assert hashlib.sha256(grid.encode("utf-8")).hexdigest() == ROBOTS_GRID_DIGEST


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://x.example/deep/path?q=1", "https://x.example"),
        ("HTTPS://X.Example/a", "https://x.example"),
        ("https://x.example:443/a", "https://x.example"),
        ("http://x.example:80/a", "http://x.example"),
        ("https://x.example:8443/a", "https://x.example:8443"),
        ("http://[2606:4700:4700::1111]/a", "http://[2606:4700:4700::1111]"),
    ],
)
def test_one_host_is_one_document_however_its_address_is_spelled(
    url: str, expected: str
) -> None:
    """RFC 9309 section 2.3 scopes a robots file to its own authority."""
    assert origin(url) == expected


def test_robots_is_looked_for_at_the_host_root() -> None:
    assert robots_url("https://X.example/deep/path?q=1") == "https://x.example/robots.txt"


# --- What one robots.txt response means (RFC 9309 section 2.3.1) ------------


def test_a_served_robots_file_is_the_rules() -> None:
    body = b"User-agent: *\nDisallow: /private/\n"
    rules = robots_rules(FetchResult(FetchOutcome.OK, status=200, body=body))
    assert rules.permits(AGENT, f"{HOST}/private/a") is RobotsOutcome.DENIED
    assert rules.permits(AGENT, f"{HOST}/public/a") is RobotsOutcome.ALLOWED


@pytest.mark.parametrize("status", [401, 403, 404, 410, 451])
def test_a_host_that_publishes_no_rules_permits_the_target(status: int) -> None:
    """RFC 9309 sec 2.3.1.3: a 4xx other than 429 means the crawler may access anything.

    Ten of our feeds sit on hosts that serve no robots.txt at all. Reading that
    as a refusal was us inventing a rule the host never wrote.
    """
    rules = robots_rules(FetchResult(classify_status(status), status=status))
    assert rules.permits(AGENT, f"{HOST}/a") is RobotsOutcome.ALLOWED


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_a_host_that_did_not_answer_leaves_permission_unknown(status: int) -> None:
    """RFC 9309 sec 2.3.1.4: unreachable means the rules are unknown, so nothing is asked."""
    rules = robots_rules(FetchResult(classify_status(status), status=status))
    assert rules.permits(AGENT, f"{HOST}/a") is RobotsOutcome.UNREACHABLE


@pytest.mark.parametrize("failure", ["TimeoutError", "ConnectionResetError", "URLError"])
def test_a_transport_failure_leaves_permission_unknown(failure: str) -> None:
    rules = robots_rules(FetchResult(FetchOutcome.TRANSIENT, detail=failure))
    assert rules.permits(AGENT, f"{HOST}/a") is RobotsOutcome.UNREACHABLE


def test_a_blocked_address_leaves_permission_unknown() -> None:
    rules = robots_rules(FetchResult(FetchOutcome.BLOCKED, detail="address resolves inward"))
    assert rules.permits(AGENT, f"{HOST}/a") is RobotsOutcome.UNREACHABLE


# --- What a permission costs the target -------------------------------------


@pytest.mark.parametrize("permission", [RobotsOutcome.DENIED, RobotsOutcome.UNREACHABLE])
def test_a_target_without_permission_reaches_no_socket(permission: RobotsOutcome) -> None:
    """Assuming consent from silence is how a polite crawler becomes an impolite one.

    A refusal and an unestablished permission are different facts, and the
    result says which as a value rather than only as a sentence.
    """
    result = fetch("https://example.org/a", config=ExtractConfig(), permission=permission)
    assert result.outcome is FetchOutcome.ROBOTS_DENIED
    assert result.robots is permission
    assert result.detail == ROBOTS_REFUSALS[permission]
    assert result == refused(permission)


def served(body: str) -> FetchResult:
    return FetchResult(FetchOutcome.OK, status=200, body=body.encode("utf-8"))


class Recorder:
    """The socket edge, standing in for a real one and remembering what it was asked.

    This is not a mock of our own logic: it is one implementation of the same
    `Fetcher` signature every stage already takes, answering from a committed
    capture. The order of the two reads is the policy under test, and policy is
    what a test has to be able to get wrong (Rule #7).
    """

    def __init__(self, answer: FetchResult) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def __call__(self, url: str) -> FetchResult:
        self.asked.append(url)
        if url.endswith("/robots.txt"):
            return self.answer
        return served("<html><body><p>the article body</p></body></html>")


def test_a_refused_target_is_never_asked_and_the_next_run_asks_again() -> None:
    """The whole order, in the two runs it takes to see it.

    Nothing about a refusal is persisted and the cache lives inside one
    `live_fetcher`, so the next run starts with an empty one and asks the host
    again. That is `collect.robots_denied_recheck_runs` at its configured value
    of one run, and it costs no stored state to honour.
    """
    settings = config.load(CONFIG_DIR)
    target = f"{HOST}/private/a"

    refusing = Recorder(served(read_text(ROBOTS / "crawler-specific-group.txt")))
    refusal = cli.live_fetcher(settings, read_address=refusing)(target)
    assert refusing.asked == [f"{HOST}/robots.txt"]
    assert refusal.outcome is FetchOutcome.ROBOTS_DENIED
    assert refusal.robots is RobotsOutcome.DENIED

    permitting = Recorder(served(read_text(ROBOTS / "no-rules.txt")))
    allowed = cli.live_fetcher(settings, read_address=permitting)(target)
    assert permitting.asked == [f"{HOST}/robots.txt", target]
    assert allowed.outcome is FetchOutcome.OK


def test_a_target_whose_rules_nobody_answered_for_is_never_asked() -> None:
    settings = config.load(CONFIG_DIR)
    silent = Recorder(FetchResult(FetchOutcome.TRANSIENT, status=503, detail="HTTP 503"))
    result = cli.live_fetcher(settings, read_address=silent)(f"{HOST}/a")
    assert silent.asked == [f"{HOST}/robots.txt"]
    assert result.outcome is FetchOutcome.ROBOTS_DENIED
    assert result.robots is RobotsOutcome.UNREACHABLE


def test_one_host_is_asked_for_its_rules_once_a_run() -> None:
    """However many of its pages a run reads, and however the addresses are spelled."""
    settings = config.load(CONFIG_DIR)
    recorder = Recorder(served(read_text(ROBOTS / "no-rules.txt")))
    read = cli.live_fetcher(settings, read_address=recorder)
    read(f"{HOST}/one")
    read("HTTPS://X.Example:443/two")
    assert recorder.asked == [
        f"{HOST}/robots.txt",
        f"{HOST}/one",
        "HTTPS://X.Example:443/two",
    ]


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
