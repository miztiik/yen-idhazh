"""Item-health classification tests.

The cases use real contract payloads and real stage conversion functions. No
network and no mocks.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import config, extract, ledger, summarize, telemetry
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
        case FailureCode.CONTEXT_EXCEEDED:
            failed_summary = summarize.to_summary(
                ok_article,
                None,
                model_id="qwen3-8b",
                pipeline_fingerprint="0" * 64,
                generated_at="2026-08-21T06:00:00Z",
                no_reply=FailureCode.CONTEXT_EXCEEDED,
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
        case FailureCode.COPIED_SOURCE:
            draft = {
                "title": "Example Lab publishes a smaller inference model",
                "summary": ok_article.text or "",
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
        case FailureCode.LEAKED_ADDRESS:
            draft = {
                "title": "Example Lab publishes a smaller inference model",
                "summary": (
                    "Example Lab released a smaller inference model and published the "
                    "weights under a permissive licence. The release notice sits at "
                    "https://collect.canary.example/beacon for anyone reading along."
                ),
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


# --- The length before the cap ----------------------------------------------


def cut_article(*, before: int, after: int) -> Article:
    """An article the truncation cap shortened, validated the way extract writes it."""
    payload = article().model_dump(mode="json")
    payload.update(
        {
            "word_count": after,
            "source_word_count": before,
            "truncated": True,
            "truncated_at_tokens": 2500,
        }
    )
    return Article.model_validate(payload)


def records(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def committed_shards() -> list[Path]:
    return sorted((REPO_ROOT / "state" / ledger.ITEM_HEALTH_DIRNAME).glob("*.csv"))


def test_a_cut_item_carries_both_counts_and_the_cut_is_the_difference() -> None:
    """The comparison is the test for a cut, so both counters ride the same row.

    `source_words == int(extract.truncation_cap_tokens / 1.3)` was the only other
    way to spot a cut, and that constant moves whenever the cap moves - so a
    window spanning the change would mix two cut points, and an article whose
    body happens to end on the boundary would be called cut when it was not.
    """
    row = telemetry.classify_item(
        planned=item(),
        article=cut_article(before=2610, after=1923),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert (row.source_words, row.source_words_before_cap) == (1923, 2610)
    assert row.source_words_before_cap is not None
    assert row.source_words is not None
    assert row.source_words_before_cap - row.source_words == 687


def test_an_uncut_item_carries_the_same_number_twice() -> None:
    """Equal is not cut. The row says so rather than leaving the reader to infer it."""
    row = telemetry.classify_item(
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert row.source_words_before_cap == row.source_words


def test_an_article_that_never_measured_the_full_body_writes_an_empty_cell() -> None:
    """Never the post-cap count copied across: that would read as a clean article.

    `Article.source_word_count` is None on a payload written before 2026-08-26,
    and the pre-cap body is not kept, so nothing can recover the number later.
    """
    payload = article().model_dump(mode="json") | {"source_word_count": None}

    row = telemetry.classify_item(
        planned=item(),
        article=Article.model_validate(payload),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert row.source_words_before_cap is None
    assert row.csv_row()["source_words_before_cap"] == ""


def test_a_row_written_before_the_pre_cap_column_reads_as_unmeasured() -> None:
    old = ItemHealthRow(
        version="2026-08-27",
        date=plan().date,
        run_id="2026-08-21-1",
        item_id=item().item_id,
        url_key=item().url_key,
        canonical_url=item().canonical_url,
        vertical=item().vertical,
        source_id=item().source_id,
        stage=ItemStage.PUBLISH,
        outcome=ItemOutcome.OK,
        source_words=1923,
    ).csv_row()
    old.pop("source_words_before_cap")

    row = ItemHealthRow.from_csv_row(old)

    assert row.source_words_before_cap is None


def test_every_migrated_item_health_row_records_its_absence() -> None:
    """The Oracle, first half: an empty cell, never a value invented today.

    A run before 2026-08-28 never looked at the body's full length, and the
    pre-cap text is gone, so no later pass can recover it. Writing anything into
    those cells would make `source_words_before_cap > source_words` - the whole
    test for a cut - answer on evidence nobody gathered. The row's own `version`
    cell says which side of the change wrote it.
    """
    shards = committed_shards()
    assert shards, "no item-health shard is committed, so this proves nothing"

    for shard in shards:
        relpath = shard.relative_to(REPO_ROOT).as_posix()
        rows = records(shard)
        assert rows, f"{relpath} has a header and no rows"
        for number, record in enumerate(rows, start=2):
            assert None not in record, f"{relpath}:{number} has more cells than the header names"
            assert all(value is not None for value in record.values()), (
                f"{relpath}:{number} has fewer cells than the header names"
            )
        predates = [record for record in rows if record["version"] < "2026-08-28"]
        assert predates, f"{relpath} holds no row older than the column, so nothing was migrated"
        assert {record["source_words_before_cap"] for record in predates} == {""}


def test_the_committed_item_health_shard_still_takes_a_row_today(tmp_path: Path) -> None:
    """The Oracle, second half: append to a byte copy of what is committed.

    `require_matching_header` compares the header tuple exactly, so the commit
    that gave the contract this column stops the shard the pipeline is appending
    to until the file is widened by the same column. That is a failed scheduled
    run, not a failed lint. This is the run a release blocker would fail, and it
    also proves the widened file can carry a real value - an absence check on
    its own passes on a file nothing was ever written to.
    """
    committed = committed_shards()[-1]
    date = f"{committed.stem}-01"
    state = tmp_path / "state"
    target = ledger.item_health_path(state, date)
    target.parent.mkdir(parents=True)
    target.write_bytes(committed.read_bytes())
    before = records(target)
    fresh = telemetry.classify_item(
        planned=item(),
        article=cut_article(before=2610, after=1923),
        summary=summary(),
        date=date,
        run_id=f"{date}-9",
    )
    assert (date, fresh.run_id, fresh.item_id) not in ledger.recorded_item_health(target)

    assert ledger.append_item_health(state, date, [fresh]) == 1

    after = records(target)
    assert ledger.read_header(target) == ItemHealthRow.csv_columns()
    assert after[:-1] == before, "the append moved a cell an earlier run wrote"
    assert after[-1]["source_words_before_cap"] == "2610"
    assert after[-1]["source_words"] == "1923"
