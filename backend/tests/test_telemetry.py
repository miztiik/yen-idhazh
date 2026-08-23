"""Item-health classification tests.

The cases use real contract payloads and real stage conversion functions. No
network and no mocks.
"""

from __future__ import annotations

import json

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import config, extract, summarize, telemetry
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import derive_url_key
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, ItemStage
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary
from idhazh.fetch import FetchResult
from idhazh.llm.server import Completion


def plan() -> RunPlan:
    return RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))


def item() -> PlannedItem:
    return plan().items[0]


def article() -> Article:
    return Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json"))


def summary() -> Summary:
    return Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))


def failed_article(status: ArticleStatus, detail: str) -> Article:
    payload = article().model_dump(mode="json")
    payload.update(
        {
            "title": item().title or "Fixture title",
            "text": None,
            "word_count": 0,
            "token_count": 0,
            "truncated": False,
            "truncated_at_tokens": None,
            "status": status.value,
            "failure_detail": detail,
        }
    )
    return Article.model_validate(payload)


def row_for(code: FailureCode) -> ItemHealthRow:
    settings = config.load(CONFIG_DIR)
    ok_article = article()
    match code:
        case FailureCode.NOT_ATTEMPTED:
            return telemetry.classify_item(
                planned=item(), article=None, summary=None, date=plan().date, run_id="2026-08-21-1"
            )
        case FailureCode.ROBOTS_DENIED:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.ROBOTS_DENIED, detail="robots.txt disallows this path"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.ROBOTS_UNREACHABLE:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.ROBOTS_DENIED, detail="robots.txt could not be reached"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.BLOCKED_ADDRESS:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.BLOCKED, detail="address resolves inward"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.HTTP_CLIENT_ERROR:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.PERMANENT, status=404, detail="HTTP 404"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.HTTP_RATE_LIMITED:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.TRANSIENT, status=429, detail="HTTP 429"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.HTTP_SERVER_ERROR:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.TRANSIENT, status=503, detail="HTTP 503"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.NETWORK_ERROR:
            failed = extract.to_article(
                item(),
                FetchResult(FetchOutcome.TRANSIENT, detail="TimeoutError"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.NO_TEXT:
            failed = failed_article(ArticleStatus.EXTRACT_FAILED, "extractor found no article text")
        case FailureCode.TOO_SHORT:
            failed = failed_article(
                ArticleStatus.EXTRACT_FAILED, "only 12 words extracted; page furniture is short"
            )
        case FailureCode.NOT_PROSE:
            signalled = extract.to_article(
                item(),
                FetchResult(
                    FetchOutcome.OK,
                    status=200,
                    body=b"<html><body><article><p>Two words.</p></article></body></html>",
                ),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=signalled,
                summary=summary(),
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.BOILERPLATE:
            signalled = extract.to_article(
                item(),
                FetchResult(
                    FetchOutcome.OK,
                    status=200,
                    body=(
                        b"<html><body><article><p>Shared navigation</p>"
                        b"<p>This sentence has enough words to count as article prose today.</p>"
                        b"<p>Another sentence has enough words to count as article prose today.</p>"
                        b"<p>A third sentence has enough words to count as article prose today.</p>"
                        b"</article></body></html>"
                    ),
                ),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
                seen_elsewhere={
                    "Shared navigation",
                    "This sentence has enough words to count as article prose today.",
                    "Another sentence has enough words to count as article prose today.",
                },
            )
            return telemetry.classify_item(
                planned=item(),
                article=signalled,
                summary=summary(),
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.PAYWALLED:
            failed = extract.to_article(
                item(),
                FetchResult(
                    FetchOutcome.OK,
                    status=200,
                    body=(
                        b"<html><head><script type=\"application/ld+json\">"
                        b"{\"isAccessibleForFree\": false, \"hasPart\": {"
                        b"\"cssSelector\": \".paywall\", \"isAccessibleForFree\": false}}"
                        b"</script></head><body><p>Subscriber text.</p></body></html>"
                    ),
                ),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.UNSUPPORTED_FORM:
            payload = item().model_dump(mode="json")
            payload["canonical_url"] = "https://newsroom.example-grid.com/paper.pdf"
            payload["source_url"] = payload["canonical_url"]
            payload["url_key"] = derive_url_key(payload["canonical_url"])
            pdf_item = item().model_validate(payload)
            failed = extract.to_article(
                pdf_item,
                FetchResult(FetchOutcome.OK, status=200, body=b"%PDF-1.7"),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.MODEL_UNREACHABLE:
            failed_summary = summarize.to_summary(
                ok_article,
                None,
                model_id="qwen3-8b",
                pipeline_fingerprint="0" * 64,
                generated_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=ok_article,
                summary=failed_summary,
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.OUTPUT_TRUNCATED:
            failed_summary = summarize.to_summary(
                ok_article,
                Completion("{}", finish_reason="length"),
                model_id="qwen3-8b",
                pipeline_fingerprint="0" * 64,
                generated_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=ok_article,
                summary=failed_summary,
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.BAD_SHAPE:
            failed_summary = summarize.to_summary(
                ok_article,
                Completion("{bad"),
                model_id="qwen3-8b",
                pipeline_fingerprint="0" * 64,
                generated_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=ok_article,
                summary=failed_summary,
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.LENGTH_OUT_OF_RANGE:
            draft = {
                "title": "Clear fixture title",
                "summary": " ".join(f"longword{n}" for n in range(20)),
                "key_points": ["One useful fact.", "Second useful fact.", "Third useful fact."],
            }
            failed_summary = summarize.to_summary(
                ok_article,
                Completion(json.dumps(draft)),
                model_id="qwen3-8b",
                pipeline_fingerprint="0" * 64,
                generated_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=ok_article,
                summary=failed_summary,
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.UNKNOWN:
            return telemetry.classify_item(
                planned=item(),
                article=failed_article(ArticleStatus.EXTRACT_FAILED, "=SUM(1,1)"),
                summary=None,
                date=plan().date,
                run_id="2026-08-21-1",
            )

    return telemetry.classify_item(
        planned=item(), article=failed, summary=None, date=plan().date, run_id="2026-08-21-1"
    )


@pytest.mark.parametrize("code", list(FailureCode))
def test_every_failure_code_has_a_real_fixture_writer(code: FailureCode) -> None:
    row = row_for(code)

    if code in {FailureCode.NOT_PROSE, FailureCode.BOILERPLATE}:
        assert row.outcome is ItemOutcome.OK
    else:
        assert row.outcome is ItemOutcome.FAILED
    assert row.code is code


def test_a_finished_item_reaches_publish_ok() -> None:
    timed_summary = summary().model_copy(
        update={"fetch_ms": 123, "extract_ms": 45, "summarize_ms": 678}
    )
    row = telemetry.classify_item(
        planned=item(),
        article=article(),
        summary=timed_summary,
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert row.stage is ItemStage.PUBLISH
    assert row.outcome is ItemOutcome.OK
    assert row.code is None
    assert (row.fetch_ms, row.extract_ms, row.summarize_ms) == (123, 45, 678)


def test_a_summarize_failure_carries_stage_timings() -> None:
    failed = summary().model_copy(
        update={
            "status": "failed",
            "summary": None,
            "key_points": [],
            "failure_code": FailureCode.MODEL_UNREACHABLE,
            "fetch_ms": 321,
            "extract_ms": 54,
            "summarize_ms": 987,
        }
    )

    row = telemetry.classify_item(
        planned=item(), article=article(), summary=failed, date=plan().date, run_id="2026-08-21-1"
    )

    assert row.stage is ItemStage.SUMMARIZE
    assert row.outcome is ItemOutcome.FAILED
    assert (row.fetch_ms, row.extract_ms, row.summarize_ms) == (321, 54, 987)


def test_a_sixteen_column_item_health_row_reads_as_unmeasured() -> None:
    old = ItemHealthRow(
        version="2026-08-23",
        date=plan().date,
        run_id="2026-08-21-1",
        item_id=item().item_id,
        url_key=item().url_key,
        canonical_url=item().canonical_url,
        vertical=item().vertical,
        source_id=item().source_id,
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
    ).csv_row()
    old.pop("fetch_ms")
    old.pop("extract_ms")
    old.pop("summarize_ms")

    row = ItemHealthRow.from_csv_row(old)

    assert (row.fetch_ms, row.extract_ms, row.summarize_ms) == (None, None, None)


def test_unknown_detail_is_sanitized_guarded_and_truncated() -> None:
    row = row_for(FailureCode.UNKNOWN)

    assert row.detail is not None
    assert not row.detail.startswith(("=", "+", "-", "@", "\t", "\r"))
    assert len(row.detail) <= 200
