"""Turn a fetched page into an article payload, or into a recorded failure.

This is the trust boundary, and it is crossed here exactly once. Everything
below this line has already been sanitized; nothing above it may be trusted
(Guardrail #11).

A failure is a state of the payload rather than an absence of it. A dead link,
a paywall, a robots refusal or an extractor that found nothing degrades its own
item, records why, and lets its siblings finish.
"""

from __future__ import annotations

import json
import re
from typing import Final, NamedTuple
from urllib.parse import urlsplit

import trafilatura
from trafilatura.metadata import extract_metadata

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.article import Article, ArticleStatus, TitleSource, UntrustedLine
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import SourceForm
from idhazh.discover import clean_title
from idhazh.evals.metrics import _SENTENCE_SPLIT
from idhazh.fetch import FetchResult
from idhazh.measured import TOKENS_A_WORD_AT_THE_CUT
from idhazh.sanitize import SANITIZER_VERSION, sanitize

#: Bumped when extraction changes shape. It is a fingerprint input, because a
#: different extractor over the same page is a different input to the model.
EXTRACTOR_VERSION: Final = f"trafilatura-{trafilatura.__version__}-idhazh-3"

#: How long a page's own `<title>` may be and still be a headline. A feed
#: headline is bounded by editorial practice before it reaches us and keeps
#: `discover.TITLE_MAX_CHARS`; a page title is bounded by whoever wrote the
#: page. Past this it is refused rather than cut, because 200 characters of a
#: payload is a nonsense headline and the item is better refused than published
#: under one (Guardrail #11).
PAGE_TITLE_MAX_CHARS: Final = 200

# English averages a little over one token per word. Exact enough to place a
# truncation point deterministically, and it is only a placement: the decoder
# enforces the real budget.
#
# Read off its record rather than written here, so the ratio and its provenance
# cannot drift apart. The record says which vocabulary it belongs to, that it is
# a judgement rather than a measurement, and how to take it properly - none of
# which a bare literal could carry, and all of which a design leaning on it has
# to see (Guardrail #10).
TOKENS_PER_WORD: Final = TOKENS_A_WORD_AT_THE_CUT.value

_DETAIL_MAX: Final = 500
_JSON_LD = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.,-]*")
_PLAYER_INTERFACE_XPATH: Final = (
    "//*[contains(concat(' ', normalize-space(@class), ' '), ' o-em-consent ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' o-em-adblock ')]"
)


def approx_tokens(word_total: int) -> int:
    return int(word_total * TOKENS_PER_WORD)


def truncate_to_tokens(text: str, cap_tokens: int) -> tuple[str, bool, int | None]:
    """Cut on a word boundary, and say so. Never silently drop text."""
    words = text.split()
    allowed = int(cap_tokens / TOKENS_PER_WORD)
    if len(words) <= allowed:
        return text, False, None
    return " ".join(words[:allowed]), True, cap_tokens


def _detail(message: str) -> UntrustedLine:
    return message[:_DETAIL_MAX] or "unspecified failure"


def _failed(
    item: PlannedItem,
    *,
    status: ArticleStatus,
    detail: str,
    fetched_at: str,
    failure_code: FailureCode | None = None,
) -> Article:
    return Article(
        version=Article.schema_version(),
        item_id=item.item_id,
        url_key=item.url_key,
        source_url=item.source_url,
        canonical_url=item.canonical_url,
        source_id=item.source_id,
        tier=item.tier,
        source_form=item.source_form,
        vertical=item.vertical,
        carried_by=item.carried_by,
        rank_score=item.rank_score,
        title=item.title,
        published_at=item.published_at,
        fetched_at=fetched_at,
        status=status,
        failure_code=failure_code,
        failure_detail=_detail(detail),
        extractor_version=EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
    )


_FAILURE_STATUS: Final[dict[FetchOutcome, ArticleStatus]] = {
    FetchOutcome.ROBOTS_DENIED: ArticleStatus.ROBOTS_DENIED,
    FetchOutcome.BLOCKED: ArticleStatus.ROBOTS_DENIED,
    FetchOutcome.PERMANENT: ArticleStatus.FETCH_FAILED,
    FetchOutcome.TRANSIENT: ArticleStatus.FETCH_FAILED,
}


def extract_text(html: str) -> str | None:
    """Boilerplate removal by a mature library, then our own sanitization.

    Comments and tables are excluded: a comment thread is other people's text
    on someone else's page, and it is the part most likely to be hostile.
    Embedded-player consent and error containers are interface text, not prose.
    """
    body = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        prune_xpath=_PLAYER_INTERFACE_XPATH,
    )
    if not body:
        return None
    cleaned = sanitize(body)
    return cleaned or None


def page_headline(html: str) -> str | None:
    """The page's own headline, cleaned by the rule a feed headline is cleaned by.

    The page was already parsed for its body and its title was thrown away, so
    an item whose feed carried no headline was refused beside the very string
    that would have answered it.

    It is read through `clean_title`, so it meets the feed title's rules
    exactly: the same sanitizer, the same whitespace rule, one cleaner rather
    than two (Guardrail #5). **The bound is the caller's, and this caller asks
    for a tighter one.** A feed headline is bounded by editorial practice before
    it reaches us; a page `<title>` is bounded by nothing but whoever wrote the
    page, including a page that exists to be crawled. Past
    `PAGE_TITLE_MAX_CHARS` it is a payload rather than a headline, so it is
    refused and the item lands as `no_title` - cutting it would publish the
    first 200 characters of somebody's instruction and call it a headline.

    It stays a value on the payload and never becomes a file path, a shell
    argument or an outbound URL; identity is recomputed from the address, so no
    filename can be steered by it, and every prompt that carries a title puts it
    inside the untrusted fence (Guardrail #11).

    `extensive=False` is the trust boundary, not a speed knob. The default asks
    htmldate for a publication date, which hands the page's own text to
    `dateparser`, which walks 205 locales compiling about 950 regexes - so a
    title a stranger writes decides how much runner time we spend. Measured
    2026-09-15 on a developer machine / Python 3.14.2, trafilatura 2.2.0, one
    cold call a process: a title of one phrase repeated five times, 121
    characters, costs **8.9 to 36.7 s** on the default and **5.9 ms** with the
    date search off - a thousandfold, from 121 bytes an attacker chooses. The
    title returned is identical either way. We never read the date, so the
    cheapest correct call is the one that does not look for one.

    This is a second parse of the same page and the measurement says it has to
    be. `bare_extraction(with_metadata=True)` returns a title beside a body in
    one pass, but that body is not the one `extract` returns - `extract` runs
    the result through `determine_returnstring`, which normalises it to NFC.
    Over the ten committed page fixtures the two bodies agree byte for byte on
    nine, differ by one trailing space on the tenth, and agree on all ten after
    `sanitize`; no fixture carries decomposed characters, so the normalisation
    gap is unmeasured rather than absent. The body is a model input stamped by
    `EXTRACTOR_VERSION`, so moving it would re-derive every cached summary to
    buy a parse - and the one pass would have paid the same date hunt anyway.
    """
    return clean_title(
        extract_metadata(html, extensive=False).title,
        max_chars=PAGE_TITLE_MAX_CHARS,
        over_bound="refuse",
    )


def _is_pdf(item: PlannedItem) -> bool:
    return urlsplit(item.canonical_url).path.lower().endswith(".pdf")


def _json_ld_values(value: object) -> list[object]:
    if isinstance(value, list):
        found: list[object] = []
        for item in value:
            found.extend(_json_ld_values(item))
        return found
    if isinstance(value, dict):
        found = [value]
        for child in value.values():
            found.extend(_json_ld_values(child))
        return found
    return []


def _is_false(value: object) -> bool:
    return value is False or (isinstance(value, str) and value.strip().lower() == "false")


def _declares_paywall(payload: object) -> bool:
    nodes = [node for node in _json_ld_values(payload) if isinstance(node, dict)]
    for node in nodes:
        if not _is_false(node.get("isAccessibleForFree")):
            continue
        parts = _json_ld_values(node.get("hasPart"))
        for part in parts:
            if isinstance(part, dict) and part.get("cssSelector") and _is_false(
                part.get("isAccessibleForFree")
            ):
                return True
    return False


def declares_paywall(html: str) -> bool:
    """Read publisher-declared JSON-LD paywall markup."""
    for match in _JSON_LD.finditer(html):
        try:
            payload = json.loads(match.group("body"))
        except json.JSONDecodeError:
            continue
        if _declares_paywall(payload):
            return True
    return False


def _marker_paywall(html: str, markers: list[str]) -> bool:
    normalized = re.sub(r"\s+", " ", html).lower()
    compact = re.sub(r"\s+", "", html).lower()
    return any(marker.lower() in normalized or marker.lower() in compact for marker in markers)


def is_paywalled(html: str, config: ExtractConfig) -> bool:
    """Paywall detection is deterministic, with JSON-LD first."""
    return declares_paywall(html) or _marker_paywall(html, config.paywall_markers)


def prose_sentence_count(text: str, *, min_words: int) -> int:
    """Count sentences that have enough words to be prose."""
    return sum(
        1 for sentence in _SENTENCE_SPLIT.split(text) if len(_WORD.findall(sentence)) >= min_words
    )


def is_not_prose(text: str, config: ExtractConfig) -> bool:
    if (
        prose_sentence_count(text, min_words=config.prose_sentence_words_min)
        < config.prose_sentence_min
    ):
        return True
    lines = _lines(text)
    if len(lines) < config.prose_line_count_min:
        return False
    prose_lines = sum(
        1 for line in lines if len(_WORD.findall(line)) >= config.prose_sentence_words_min
    )
    return prose_lines / len(lines) < config.prose_line_ratio_min


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


class Extracted(NamedTuple):
    """The payload, and the body it was cut from.

    `source_text` is the sanitized article before `truncation_cap_tokens` cut
    it. It is never persisted and never republished (Guardrail #1): it exists so the
    work stage can score the summary against the whole article in the same
    process that produced it. Empty whenever there was no body to keep.
    """

    article: Article
    source_text: str


def to_article(
    item: PlannedItem,
    result: FetchResult,
    *,
    config: ExtractConfig,
    fetched_at: str,
    seen_elsewhere: set[str] | None = None,
) -> Article:
    """One planned item plus one fetch outcome becomes exactly one payload."""
    return to_article_with_source(
        item, result, config=config, fetched_at=fetched_at, seen_elsewhere=seen_elsewhere
    ).article


def to_article_with_source(
    item: PlannedItem,
    result: FetchResult,
    *,
    config: ExtractConfig,
    fetched_at: str,
    seen_elsewhere: set[str] | None = None,
) -> Extracted:
    """The payload, plus the untruncated body that only lives in this process."""
    if item.url_key != derive_url_key(item.canonical_url):
        raise ValueError("a planned item arrived with an identity it does not own")

    if not result.ok:
        return Extracted(
            _failed(
                item,
                status=_FAILURE_STATUS[result.outcome],
                detail=result.detail or result.outcome.value,
                fetched_at=fetched_at,
            ),
            "",
        )

    if _is_pdf(item):
        return Extracted(
            _failed(
                item,
                status=ArticleStatus.EXTRACT_FAILED,
                detail="feed item is an unsupported PDF",
                fetched_at=fetched_at,
                failure_code=FailureCode.UNSUPPORTED_FORM,
            ),
            "",
        )

    html = result.body.decode("utf-8", errors="replace")
    if is_paywalled(html, config):
        return Extracted(
            _failed(
                item,
                status=ArticleStatus.EXTRACT_FAILED,
                detail="publisher declared a paywall",
                fetched_at=fetched_at,
                failure_code=FailureCode.PAYWALLED,
            ),
            "",
        )

    body = extract_text(html)
    if body is None:
        return Extracted(
            _failed(
                item,
                status=ArticleStatus.EXTRACT_FAILED,
                detail="extractor found no article text",
                fetched_at=fetched_at,
                failure_code=FailureCode.NO_TEXT,
            ),
            "",
        )

    text, truncated, cut_at = truncate_to_tokens(body, config.truncation_cap_tokens)
    total_words = len(body.split())
    signal_code: FailureCode | None = None
    ratio = boilerplate_ratio(_lines(body), seen_elsewhere or set())
    if ratio > config.boilerplate_ratio_max:
        signal_code = FailureCode.BOILERPLATE
    elif is_not_prose(body, config):
        signal_code = FailureCode.NOT_PROSE
    elif total_words < config.min_source_words:
        signal_code = FailureCode.TOO_SHORT

    if signal_code is FailureCode.BOILERPLATE and config.reject_boilerplate:
        return Extracted(
            _failed(
                item,
                status=ArticleStatus.EXTRACT_FAILED,
                detail="extracted text is mostly sibling boilerplate",
                fetched_at=fetched_at,
                failure_code=FailureCode.BOILERPLATE,
            ),
            "",
        )
    if signal_code is FailureCode.NOT_PROSE and config.reject_not_prose:
        return Extracted(
            _failed(
                item,
                status=ArticleStatus.EXTRACT_FAILED,
                detail="extracted text does not match prose shape",
                fetched_at=fetched_at,
                failure_code=FailureCode.NOT_PROSE,
            ),
            "",
        )

    # Last, because every other reason is the more useful one to record. An item
    # with no body and no headline is a `no_text` item; this is the one that read
    # fine and has nothing to head it with.
    #
    # The feed's headline first, then the page's own. Order is the control here:
    # the page is the more attacker-controlled of the two strings, so it is read
    # only when the source we chose said nothing, and it can never displace a
    # headline we were given (Guardrail #11).
    #
    # `Article` refuses an ok payload with no title, so building one here raised
    # out of the per-item loop and took the whole shard with it. A headline
    # neither the feed nor the page carries is one article's data being thin,
    # which degrades that article and no other (`CLAUDE.md` section 1a).
    title = item.title if (item.title or "").strip() else None
    title_source = TitleSource.FEED if title is not None else None
    if title is None:
        title = page_headline(html)
        title_source = TitleSource.PAGE if title is not None else None
    if title is None:
        return Extracted(
            _failed(
                item,
                status=ArticleStatus.EXTRACT_FAILED,
                detail="neither the feed nor the page carries a headline we will publish",
                fetched_at=fetched_at,
                failure_code=FailureCode.NO_TITLE,
            ),
            "",
        )

    return Extracted(
        Article(
            version=Article.schema_version(),
            item_id=item.item_id,
            url_key=item.url_key,
            source_url=item.source_url,
            canonical_url=item.canonical_url,
            source_id=item.source_id,
            tier=item.tier,
            vertical=item.vertical,
            carried_by=item.carried_by,
            rank_score=item.rank_score,
            title=title,
            title_source=title_source,
            text=text,
            word_count=len(text.split()),
            source_word_count=total_words,
            token_count=approx_tokens(len(text.split())),
            brief=(
                item.source_form is SourceForm.ABSTRACT
                or total_words < config.min_source_words
                or signal_code is not None
            ),
            truncated=truncated,
            truncated_at_tokens=cut_at,
            published_at=item.published_at,
            fetched_at=fetched_at,
            status=ArticleStatus.OK,
            failure_code=signal_code,
            extractor_version=EXTRACTOR_VERSION,
            sanitizer_version=SANITIZER_VERSION,
        ),
        body,
    )


def boilerplate_ratio(lines: list[str], seen_elsewhere: set[str]) -> float:
    """Share of an item's lines that also appear on sibling items from the same host.

    Comparing pages against each other beats any faithfulness score for this
    failure, because a summary of navigation chrome is perfectly faithful to the
    chrome it was given.
    """
    meaningful = [line for line in lines if line.strip()]
    if not meaningful:
        return 0.0
    shared = sum(1 for line in meaningful if line.strip() in seen_elsewhere)
    return shared / len(meaningful)
