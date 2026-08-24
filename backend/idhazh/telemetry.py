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
) -> ItemHealthRow:
    """Return the one terminal row for this planned item in this run."""
    if article is None:
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
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
            stage=stage,
            outcome=ItemOutcome.FAILED,
            code=code,
            http_status=status,
            source_chars=len(article.text or "") if article.text is not None else None,
            source_words=article.word_count or None,
            detail=detail,
        )

    if summary is None:
        if article.failure_code in {
            FailureCode.TOO_SHORT,
            FailureCode.NOT_PROSE,
            FailureCode.BOILERPLATE,
        }:
            return _row(
                planned=planned,
                date=date,
                run_id=run_id,
                stage=ItemStage.PUBLISH,
                outcome=ItemOutcome.OK,
                code=article.failure_code,
                source_chars=len(article.text or ""),
                source_words=article.word_count,
            )
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.UNKNOWN,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            detail=detail_cell("summary payload missing"),
        )

    if summary.status is not SummaryStatus.OK:
        code = summary.failure_code or FailureCode.UNKNOWN
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=code,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
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
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
        code=article.failure_code,
        source_chars=len(article.text or ""),
        source_words=article.word_count,
        summary_words=len((summary.summary or "").split()),
        fetch_ms=summary.fetch_ms,
        extract_ms=summary.extract_ms,
        summarize_ms=summary.summarize_ms,
    )


def _row(
    *,
    planned: PlannedItem,
    date: str,
    run_id: str,
    stage: ItemStage,
    outcome: ItemOutcome,
    code: FailureCode | None = None,
    http_status: int | None = None,
    source_chars: int | None = None,
    source_words: int | None = None,
    summary_words: int | None = None,
    detail: str | None = None,
    fetch_ms: int | None = None,
    extract_ms: int | None = None,
    summarize_ms: int | None = None,
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
