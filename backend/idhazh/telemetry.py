"""Classify one planned item's terminal state for the item-health ledger."""

from __future__ import annotations

import re
from typing import Final

from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.sanitize import sanitize

_FORMULA_PREFIXES: Final = ("=", "+", "-", "@", "\t", "\r")
_HTTP_DETAIL = re.compile(r"^HTTP (?P<status>[0-9]{3})$")

#: Extract signals that end an item without failing it. The article is kept, the
#: model is never asked, and the row publishes as `ok` carrying the signal.
DEGRADED_BUT_DONE: Final = frozenset(
    {FailureCode.TOO_SHORT, FailureCode.NOT_PROSE, FailureCode.BOILERPLATE}
)


def is_final(article: Article | None, summary: Summary | None) -> bool:
    """Has this item stopped, or is a payload simply not written yet?

    `classify_item` answers for every planned item, including ones nothing ever
    touched, because assemble needs the denominator in the same file as the
    count. A worker recording rows while the run is still going needs the
    narrower question. It writes an article payload for every item it reaches and
    a summary payload for every item that got as far as the model, so an article
    the extractor accepted with no summary beside it means the shard stopped
    mid-item - and a row filed then would record an interruption as a failure
    that no later run can correct.
    """
    if article is None:
        return False
    if article.status is not ArticleStatus.OK:
        return True
    if article.failure_code in DEGRADED_BUT_DONE:
        return True
    return summary is not None


def detail_cell(text: str) -> str:
    """Sanitize an unknown-failure detail for a CSV cell."""
    cleaned = sanitize(text)
    while cleaned.startswith(_FORMULA_PREFIXES):
        cleaned = cleaned[1:].lstrip()
    collapsed = " ".join(cleaned.split())
    return collapsed[:200] or "unspecified failure"


def classify_item(
    *,
    planned: PlannedItem,
    article: Article | None,
    summary: Summary | None,
    date: str,
    run_id: str,
    shard: int | None = None,
) -> ItemHealthRow:
    """Return the one terminal row for this planned item in this run.

    `shard` is the worker that produced the payloads, and it is optional because
    only one of the two callers has one. A worker knows its own number; assemble
    runs once for the whole day and cannot know which machine an item was for, so
    the rows it adds leave the cell empty rather than naming a shard that may
    never have started.
    """
    if article is None:
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=ItemStage.PLAN,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.NOT_ATTEMPTED,
        )

    if article.status is not ArticleStatus.OK:
        code, stage, status, detail = _classify_article(article)
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=stage,
            outcome=ItemOutcome.FAILED,
            code=code,
            http_status=status,
            source_chars=len(article.text or "") if article.text is not None else None,
            source_words=article.word_count or None,
            source_words_before_cap=article.source_word_count,
            detail=detail,
        )

    if summary is None:
        if article.failure_code in DEGRADED_BUT_DONE:
            return _row(
                planned=planned,
                date=date,
                run_id=run_id,
                shard=shard,
                stage=ItemStage.PUBLISH,
                outcome=ItemOutcome.OK,
                code=article.failure_code,
                source_chars=len(article.text or ""),
                source_words=article.word_count,
                source_words_before_cap=article.source_word_count,
            )
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.UNKNOWN,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            source_words_before_cap=article.source_word_count,
            detail=detail_cell("summary payload missing"),
        )

    if summary.status is not SummaryStatus.OK:
        code = summary.failure_code or FailureCode.UNKNOWN
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=code,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            source_words_before_cap=article.source_word_count,
            fetch_ms=summary.fetch_ms,
            extract_ms=summary.extract_ms,
            summarize_ms=summary.summarize_ms,
            detail=(
                detail_cell("summary failure was not typed")
                if code is FailureCode.UNKNOWN
                else None
            ),
        )

    return _row(
        planned=planned,
        date=date,
        run_id=run_id,
        shard=shard,
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
        code=article.failure_code,
        source_chars=len(article.text or ""),
        source_words=article.word_count,
        source_words_before_cap=article.source_word_count,
        summary_words=len((summary.summary or "").split()),
        fetch_ms=summary.fetch_ms,
        extract_ms=summary.extract_ms,
        summarize_ms=summary.summarize_ms,
        prefill_ms=summary.prefill_ms,
        decode_ms=summary.decode_ms,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        cached_tokens=summary.cached_tokens,
    )


def _row(
    *,
    planned: PlannedItem,
    date: str,
    run_id: str,
    stage: ItemStage,
    outcome: ItemOutcome,
    shard: int | None = None,
    code: FailureCode | None = None,
    http_status: int | None = None,
    source_chars: int | None = None,
    source_words: int | None = None,
    summary_words: int | None = None,
    detail: str | None = None,
    fetch_ms: int | None = None,
    extract_ms: int | None = None,
    summarize_ms: int | None = None,
    prefill_ms: int | None = None,
    decode_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cached_tokens: int | None = None,
    source_words_before_cap: int | None = None,
) -> ItemHealthRow:
    return ItemHealthRow(
        version=ItemHealthRow.schema_version(),
        date=date,
        run_id=run_id,
        item_id=planned.item_id,
        url_key=planned.url_key,
        canonical_url=planned.canonical_url,
        vertical=planned.vertical,
        source_id=planned.source_id,
        stage=stage,
        outcome=outcome,
        code=code,
        http_status=http_status,
        source_chars=source_chars,
        source_words=source_words,
        summary_words=summary_words,
        detail=detail,
        fetch_ms=fetch_ms,
        extract_ms=extract_ms,
        summarize_ms=summarize_ms,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        source_words_before_cap=source_words_before_cap,
        shard=shard,
    )


def _classify_article(article: Article) -> tuple[FailureCode, ItemStage, int | None, str | None]:
    detail = article.failure_detail or ""
    if article.status is ArticleStatus.EXTRACT_FAILED:
        if article.failure_code is not None:
            return article.failure_code, ItemStage.EXTRACT, None, None
        if detail == "extractor found no article text":
            return FailureCode.NO_TEXT, ItemStage.EXTRACT, None, None
        if detail.startswith("only ") and detail.endswith(
            " words extracted; page furniture is short"
        ):
            return FailureCode.TOO_SHORT, ItemStage.EXTRACT, None, None
        return (
            FailureCode.UNKNOWN,
            ItemStage.EXTRACT,
            None,
            detail_cell("extract failed for an untyped reason"),
        )

    if article.status is ArticleStatus.ROBOTS_DENIED:
        if detail == "robots.txt disallows this path":
            return FailureCode.ROBOTS_DENIED, ItemStage.FETCH, None, None
        if detail == "robots.txt could not be reached":
            return FailureCode.ROBOTS_UNREACHABLE, ItemStage.FETCH, None, None
        if detail in {
            "address resolves inward",
            "address is not on the public internet",
            "no host in address",
        } or detail.startswith("scheme "):
            return FailureCode.BLOCKED_ADDRESS, ItemStage.FETCH, None, None
        return (
            FailureCode.UNKNOWN,
            ItemStage.FETCH,
            None,
            detail_cell("fetch failed for an untyped reason"),
        )

    match = _HTTP_DETAIL.match(detail)
    if match is not None:
        status = int(match.group("status"))
        if status == 429:
            return FailureCode.HTTP_RATE_LIMITED, ItemStage.FETCH, status, None
        if 400 <= status < 500:
            return FailureCode.HTTP_CLIENT_ERROR, ItemStage.FETCH, status, None
        if 500 <= status < 600:
            return FailureCode.HTTP_SERVER_ERROR, ItemStage.FETCH, status, None

    if detail in {"URLError", "TimeoutError", "OSError"}:
        return FailureCode.NETWORK_ERROR, ItemStage.FETCH, None, None

    return (
        FailureCode.UNKNOWN,
        ItemStage.FETCH,
        None,
        detail_cell("fetch failed for an untyped reason"),
    )
