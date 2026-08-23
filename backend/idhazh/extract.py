"""Turn a fetched page into an article payload, or into a recorded failure.

This is the trust boundary, and it is crossed here exactly once. Everything
below this line has already been sanitized; nothing above it may be trusted
(Rule #11).

A failure is a state of the payload rather than an absence of it. A dead link,
a paywall, a robots refusal or an extractor that found nothing degrades its own
item, records why, and lets its siblings finish.
"""

from __future__ import annotations

import json
import re
from typing import Final
from urllib.parse import urlsplit

import trafilatura

from idhazh.contracts.app_config import ExtractConfig
from idhazh.contracts.article import Article, ArticleStatus, UntrustedLine
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.sources import SourceForm
from idhazh.evals.metrics import _SENTENCE_SPLIT
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
_JSON_LD = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.,-]*")


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
    """
    body = trafilatura.extract(
        html, include_comments=False, include_tables=False, favor_precision=True
    )
    if not body:
        return None
    cleaned = sanitize(body)
    return cleaned or None


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


def to_article(
    item: PlannedItem,
    result: FetchResult,
    *,
    config: ExtractConfig,
    fetched_at: str,
    seen_elsewhere: set[str] | None = None,
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

    if _is_pdf(item):
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail="feed item is an unsupported PDF",
            fetched_at=fetched_at,
            failure_code=FailureCode.UNSUPPORTED_FORM,
        )

    html = result.body.decode("utf-8", errors="replace")
    if is_paywalled(html, config):
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail="publisher declared a paywall",
            fetched_at=fetched_at,
            failure_code=FailureCode.PAYWALLED,
        )

    body = extract_text(html)
    if body is None:
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail="extractor found no article text",
            fetched_at=fetched_at,
            failure_code=FailureCode.NO_TEXT,
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
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail="extracted text is mostly sibling boilerplate",
            fetched_at=fetched_at,
            failure_code=FailureCode.BOILERPLATE,
        )
    if signal_code is FailureCode.NOT_PROSE and config.reject_not_prose:
        return _failed(
            item,
            status=ArticleStatus.EXTRACT_FAILED,
            detail="extracted text does not match prose shape",
            fetched_at=fetched_at,
            failure_code=FailureCode.NOT_PROSE,
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
