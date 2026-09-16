"""What was one item's terminal state, in the single row a day keeps for it?

A log line and a span are evidence that something happened; the item-health row
is the record of it. This builds that row for every planned item, including the
ones nothing ever reached, so a day's count and its denominator come off one
pass over one plan.
"""

from __future__ import annotations

import re
from typing import Any, Final

from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import fit_cell
from idhazh.contracts.call_cost import COST_FIELDS, CallCost
from idhazh.contracts.feed_health import RobotsOutcome
from idhazh.contracts.item_health import (
    CALL_SLOTS,
    UNSPECIFIED,
    FailureCode,
    ItemHealthDetail,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.elements import ExtractionHealth
from idhazh.fetch import BLOCKED_REASONS, ROBOTS_REFUSALS
from idhazh.sanitize import sanitize

_FORMULA_PREFIXES: Final = ("=", "+", "-", "@", "\t", "\r")
_HTTP_DETAIL = re.compile(r"^HTTP (?P<status>[0-9]{3})$")

#: Which typed failure each robots refusal is. The reasons are `fetch`'s own
#: strings rather than copies, so a reworded one cannot quietly become
#: `unknown` here while every gate stays green.
_ROBOTS_FAILURE: Final[dict[str, FailureCode]] = {
    ROBOTS_REFUSALS[RobotsOutcome.DENIED]: FailureCode.ROBOTS_DENIED,
    ROBOTS_REFUSALS[RobotsOutcome.UNREACHABLE]: FailureCode.ROBOTS_UNREACHABLE,
}


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
    """Sanitize an unknown-failure detail for a CSV cell.

    Two controls, composed, and they answer different questions (Guardrail #11).
    `sanitize` is the trust boundary: this text can be a stranger's page, and it
    reaches here whenever a failure quotes what failed - a Pydantic
    `ValidationError` embeds `input_value=...`, so a page title with a curly
    quote in it arrives inside the message that says the title was refused.
    `fit_cell` is the column: it reads the class and the length off
    `ItemHealthDetail` itself, so the cut is the column's own 2,000 rather than a
    number restated here, and the result is a value the column accepts.

    **A failure that cannot be printed is still a failure that happened.** A
    detail that folds away to nothing becomes `UNSPECIFIED`, never an empty
    string: the column has `min_length=1`, so an empty cell would raise and lose
    the row that was reporting the fault.
    """
    cleaned = sanitize(text)
    while cleaned.startswith(_FORMULA_PREFIXES):
        cleaned = cleaned[1:].lstrip()
    return fit_cell(cleaned, column=ItemHealthDetail, absent=UNSPECIFIED)


def classify_item(
    *,
    planned: PlannedItem,
    article: Article | None,
    summary: Summary | None,
    date: str,
    run_id: str,
    shard: int | None = None,
    extraction: ExtractionHealth | None = None,
    recovered: bool | None = None,
) -> ItemHealthRow:
    """Return the one terminal row for this planned item in this run.

    `shard` is the worker that produced the payloads, and it is optional because
    only one of the two callers has one. A worker knows its own number; assemble
    runs once for the whole day and cannot know which machine an item was for, so
    the rows it adds leave the cell empty rather than naming a shard that may
    never have started.

    `extraction` arrives already computed, because it needs two config sections
    this module has no other reason to read. It rides on every branch: an article
    the summarizer never reached still had text a pattern could read, and a class
    recorded only for the items that published would make the extractor look
    healthiest on the days it failed most.

    `recovered` says whether a cut reply had to be repaired before it parsed, and
    it arrives as an argument for the same reason: the fact is recorded on the
    visual decision, which is a third payload this function is not handed. It
    rides every branch that could carry one, because a recovery that saved the
    summary and a recovery that saved nothing are both readings of the same
    budget - and only the caller knows which payload it opened.
    """
    if article is None:
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            extraction=extraction,
            recovered=recovered,
            stage=ItemStage.PLAN,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.NOT_ATTEMPTED,
        )

    if article.status is not ArticleStatus.OK:
        code, stage, status, detail = classify_article(article)
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            extraction=extraction,
            recovered=recovered,
            stage=stage,
            outcome=ItemOutcome.FAILED,
            code=code,
            http_status=status,
            source_chars=len(article.text or "") if article.text is not None else None,
            source_words=article.word_count or None,
            source_words_before_cap=article.source_word_count,
            truncation_cap_tokens=article.truncated_at_tokens,
            detail=detail,
        )

    if summary is None:
        if article.failure_code in DEGRADED_BUT_DONE:
            return _row(
                planned=planned,
                date=date,
                run_id=run_id,
                shard=shard,
                extraction=extraction,
                recovered=recovered,
                stage=ItemStage.PUBLISH,
                outcome=ItemOutcome.OK,
                code=article.failure_code,
                source_chars=len(article.text or ""),
                source_words=article.word_count,
                source_words_before_cap=article.source_word_count,
                truncation_cap_tokens=article.truncated_at_tokens,
            )
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            extraction=extraction,
            recovered=recovered,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=FailureCode.UNKNOWN,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            source_words_before_cap=article.source_word_count,
            truncation_cap_tokens=article.truncated_at_tokens,
            detail=detail_cell("summary payload missing"),
        )

    if summary.status is not SummaryStatus.OK:
        code = summary.failure_code or FailureCode.UNKNOWN
        # A reply the stage refused was still read and still written, so this row
        # carries the same five cells an ok row does. They are null only where no
        # call returned, which is what `reconcile_prefill` skips rather than pools.
        return _row(
            planned=planned,
            date=date,
            run_id=run_id,
            shard=shard,
            extraction=extraction,
            recovered=recovered,
            stage=ItemStage.SUMMARIZE,
            outcome=ItemOutcome.FAILED,
            code=code,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            source_words_before_cap=article.source_word_count,
            truncation_cap_tokens=article.truncated_at_tokens,
            fetch_ms=summary.fetch_ms,
            extract_ms=summary.extract_ms,
            summarize_ms=summary.summarize_ms,
            prefill_ms=summary.prefill_ms if summary.call_1 is not None else None,
            decode_ms=summary.decode_ms if summary.call_1 is not None else None,
            input_tokens=summary.input_tokens if summary.call_1 is not None else None,
            output_tokens=summary.output_tokens if summary.call_1 is not None else None,
            cached_tokens=summary.cached_tokens if summary.call_1 is not None else None,
            calls=(summary.call_1, summary.call_2),
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
        extraction=extraction,
        recovered=recovered,
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
        code=article.failure_code,
        source_chars=len(article.text or ""),
        source_words=article.word_count,
        source_words_before_cap=article.source_word_count,
        truncation_cap_tokens=article.truncated_at_tokens,
        summary_words=len((summary.summary or "").split()),
        fetch_ms=summary.fetch_ms,
        extract_ms=summary.extract_ms,
        summarize_ms=summary.summarize_ms,
        prefill_ms=summary.prefill_ms,
        decode_ms=summary.decode_ms,
        input_tokens=summary.input_tokens,
        output_tokens=summary.output_tokens,
        cached_tokens=summary.cached_tokens,
        calls=(summary.call_1, summary.call_2),
    )


def _flatten_calls(calls: tuple[CallCost | None, CallCost | None]) -> dict[str, Any]:
    """The nested per-call costs as the ledger's flat cells.

    One translator between the two spellings. A ledger row is a CSV line and
    cannot nest, and `Summary` describes the five numbers once - so this is the
    single place the two shapes meet, rather than a second copy of the
    vocabulary in the writer.
    """
    cells: dict[str, Any] = {"model_calls": None}
    recorded = 0
    for slot, call in zip(CALL_SLOTS, calls, strict=True):
        cells[f"{slot}_kind"] = None if call is None else call.kind
        for field in COST_FIELDS:
            cells[f"{slot}_{field}"] = None if call is None else getattr(call, field)
        recorded += call is not None
    if recorded:
        cells["model_calls"] = recorded
    return cells


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
    truncation_cap_tokens: int | None = None,
    extraction: ExtractionHealth | None = None,
    recovered: bool | None = None,
    calls: tuple[CallCost | None, CallCost | None] = (None, None),
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
        truncation_cap_tokens=truncation_cap_tokens,
        shard=shard,
        span_integrity=extraction.span_integrity if extraction is not None else None,
        elements_found=extraction.elements_found if extraction is not None else None,
        element_class=extraction.element_class if extraction is not None else None,
        recovered=recovered,
        **_flatten_calls(calls),
    )


def classify_article(article: Article) -> tuple[FailureCode, ItemStage, int | None, str | None]:
    """Which failure ended this article, at which stage, and what says so.

    Public because the work stage records the same verdict on the item's own
    record while the run is going, and a second derivation there named `extract`
    for every article whatever had really failed - so a fetch code landed on an
    extract row, a pairing `ItemHealthRow` refuses.

    The fourth value is a detail to use only where the failure is untyped: a
    row carrying `unknown` has to say something, and the caller's own text is
    the better sentence wherever there is one.
    """
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
        refusal = _ROBOTS_FAILURE.get(detail)
        if refusal is not None:
            return refusal, ItemStage.FETCH, None, None
        if detail in BLOCKED_REASONS or detail.startswith("scheme "):
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
