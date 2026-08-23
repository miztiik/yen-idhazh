"""Turn a fetched page into an article payload, or into a recorded failure.

This is the trust boundary, and it is crossed here exactly once. Everything
below this line has already been sanitized; nothing above it may be trusted
(Holy Law #11).

A failure is a state of the payload rather than an absence of it. A dead link,
a paywall, a robots refusal or an extractor that found nothing degrades its own
item, records why, and lets its siblings finish.
"""

from __future__ import annotations

from typing import Final

import trafilatura

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.article import Article, ArticleStatus, UntrustedLine
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.run_plan import PlannedItem
from idhazh.fetch import FetchResult
from idhazh.sanitize import SANITIZER_VERSION, sanitize

#: Bumped when extraction changes shape. It is a fingerprint input, because a
#: different extractor over the same page is a different input to the model.
EXTRACTOR_VERSION: Final = f"trafilatura-{trafilatura.__version__}-idhazh-1"

# English averages a little over one token per word. Exact enough to place a
# truncation point deterministically, and it is only a placement: the decoder
# enforces the real budget. Recorded here so nobody mistakes it for a count.
TOKENS_PER_WORD: Final = 1.3

_DETAIL_MAX: Final = 500


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


def _failed(item: PlannedItem, *, status: ArticleStatus, detail: str, fetched_at: str) -> Article:
    return Article(
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
        title=item.title,
        published_at=item.published_at,
        fetched_at=fetched_at,
        status=status,
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
    """
    body = trafilatura.extract(
        html, include_comments=False, include_tables=False, favor_precision=True
    )
    if not body:
        return None
    cleaned = sanitize(body)
    return cleaned or None


def to_article(
    item: PlannedItem,
    result: FetchResult,
    *,
    config: ExtractConfig,
    fetched_at: str,
) -> Article:
    """One planned item plus one fetch outcome becomes exactly one payload."""
    if item.url_key != derive_url_key(item.canonical_url):
        raise ValueError("a planned item arrived with an identity it does not own")

    if not result.ok:
        return _failed(
            item,
            status=_FAILURE_STATUS[result.outcome],
            detail=result.detail or result.outcome.value,
            fetched_at=fetched_at,
        )

    html = result.body.decode("utf-8", errors="replace")
    body = extract_text(html)
    if body is None:
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail="extractor found no article text",
            fetched_at=fetched_at,
        )

    text, truncated, cut_at = truncate_to_tokens(body, config.truncation_cap_tokens)
    total_words = len(body.split())
    if total_words < config.min_source_words:
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail=f"only {total_words} words extracted; page furniture is short",
            fetched_at=fetched_at,
        )

    return Article(
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
        title=item.title,
        text=text,
        word_count=len(text.split()),
        token_count=approx_tokens(len(text.split())),
        truncated=truncated,
        truncated_at_tokens=cut_at,
        published_at=item.published_at,
        fetched_at=fetched_at,
        status=ArticleStatus.OK,
        extractor_version=EXTRACTOR_VERSION,
        sanitizer_version=SANITIZER_VERSION,
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
