"""Item-health classification tests.

The cases use real contract payloads and real stage conversion functions. No
network and no mocks.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Final, get_args, get_origin

import pytest
from conftest import (
    CONFIG_DIR,
    CONTRACT_FIXTURES_DIR,
    REPO_ROOT,
    fold,
    read_text,
    seed_item_health,
)
from pydantic import StringConstraints, TypeAdapter, ValidationError

from idhazh import config, day_shards, extract, ledger, summarize, telemetry
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import ServerJob, column_bounds, derive_url_key, field_column
from idhazh.contracts.call_cost import COST_FIELDS, DERIVED_FIELDS, CallCost, CallKind
from idhazh.contracts.feed_health import FetchOutcome, RobotsOutcome
from idhazh.contracts.item_health import (
    UNSPECIFIED,
    ElementClass,
    FailureCode,
    ItemHealthDetail,
    ItemHealthRow,
    ItemOutcome,
    ItemStage,
)
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.span_rollup import RollupSpan, SpanRollupRow
from idhazh.contracts.summary import Summary
from idhazh.elements import ExtractionHealth
from idhazh.fetch import BLOCKED_REASONS, FetchResult, refused
from idhazh.llm.server import Completion, parse_completion
from idhazh.stages.common import _log_no_reply
from idhazh.telemetry.census import EXTRACTION_CELLS


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
            "title_source": None,
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
                refused(RobotsOutcome.DENIED),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
        case FailureCode.ROBOTS_UNREACHABLE:
            failed = extract.to_article(
                item(),
                refused(RobotsOutcome.UNREACHABLE),
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
        case FailureCode.NO_TITLE:
            headless = item().model_validate(item().model_dump(mode="json") | {"title": None})
            failed = extract.to_article(
                headless,
                FetchResult(
                    FetchOutcome.OK,
                    status=200,
                    body=(
                        b"<html><body><article>"
                        b"<p>This sentence has enough words to count as article prose today.</p>"
                        b"<p>Another sentence has enough words to count as article prose today.</p>"
                        b"<p>A third sentence has enough words to count as article prose today.</p>"
                        b"</article></body></html>"
                    ),
                ),
                config=settings.app.extract,
                fetched_at="2026-08-21T06:00:00Z",
            )
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
        case FailureCode.CONTAMINATED:
            signalled = extract.to_article(
                item(),
                FetchResult(
                    FetchOutcome.OK,
                    status=200,
                    body=(
                        REPO_ROOT / "tests" / "fixtures" / "pages" / "contaminated-front-page.html"
                    ).read_bytes(),
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
                        b'<html><head><script type="application/ld+json">'
                        b'{"isAccessibleForFree": false, "hasPart": {'
                        b'"cssSelector": ".paywall", "isAccessibleForFree": false}}'
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
                generated_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=ok_article,
                summary=failed_summary,
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.MODEL_TIMED_OUT | FailureCode.SHARD_OUT_OF_TIME:
            # Both are a clock running out rather than a reply arriving, and they
            # differ only in whose clock: the request's, or the worker's.
            failed_summary = summarize.to_summary(
                ok_article,
                None,
                model_id="qwen3-8b",
                generated_at="2026-08-21T06:00:00Z",
                no_reply=code,
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
        case FailureCode.MODEL_REFUSED:
            failed_summary = summarize.to_summary(
                ok_article,
                None,
                model_id="qwen3-8b",
                generated_at="2026-08-21T06:00:00Z",
                no_reply=FailureCode.MODEL_REFUSED,
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
                generated_at="2026-08-21T06:00:00Z",
            )
            return telemetry.classify_item(
                planned=item(),
                article=ok_article,
                summary=failed_summary,
                date=plan().date,
                run_id="2026-08-21-1",
            )
        case FailureCode.LABELS_TRUNCATED:
            failed_summary = summarize.to_summary(
                ok_article,
                None,
                model_id="qwen3-8b",
                generated_at="2026-08-21T06:00:00Z",
                no_reply=FailureCode.LABELS_TRUNCATED,
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
            }
            failed_summary = summarize.to_summary(
                ok_article,
                Completion(json.dumps(draft)),
                model_id="qwen3-8b",
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
            }
            failed_summary = summarize.to_summary(
                ok_article,
                Completion(json.dumps(draft)),
                model_id="qwen3-8b",
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
            }
            failed_summary = summarize.to_summary(
                ok_article,
                Completion(json.dumps(draft)),
                model_id="qwen3-8b",
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

    if code in {
        FailureCode.NOT_PROSE,
        FailureCode.BOILERPLATE,
        FailureCode.CONTAMINATED,
    }:
        assert row.outcome is ItemOutcome.OK
    else:
        assert row.outcome is ItemOutcome.FAILED
    assert row.code is code


@pytest.mark.parametrize("permission", [RobotsOutcome.DENIED, RobotsOutcome.UNREACHABLE])
def test_every_refusal_the_fetcher_writes_arrives_here_typed(
    permission: RobotsOutcome,
) -> None:
    """The two modules spell the reason once, in `fetch`, and read it back here.

    They used to hold a literal each. Rewording either one turned a refusal
    into `unknown` with a diagnostic sentence in the ledger, and every gate
    stayed green because both sides still compiled.
    """
    settings = config.load(CONFIG_DIR)
    article = extract.to_article(
        item(),
        refused(permission),
        config=settings.app.extract,
        fetched_at="2026-08-21T06:00:00Z",
    )
    row = telemetry.classify_item(
        planned=item(), article=article, summary=None, date=plan().date, run_id="2026-08-21-1"
    )
    assert row.code is not FailureCode.UNKNOWN
    assert row.stage is ItemStage.FETCH
    assert row.detail is None


@pytest.mark.parametrize("reason", sorted(BLOCKED_REASONS))
def test_every_address_the_fetcher_blocks_arrives_here_typed(reason: str) -> None:
    """The same drift, one branch along: `fetch` owns the reasons and this reads them."""
    settings = config.load(CONFIG_DIR)
    article = extract.to_article(
        item(),
        FetchResult(FetchOutcome.BLOCKED, detail=reason),
        config=settings.app.extract,
        fetched_at="2026-08-21T06:00:00Z",
    )
    row = telemetry.classify_item(
        planned=item(), article=article, summary=None, date=plan().date, run_id="2026-08-21-1"
    )
    assert row.code is FailureCode.BLOCKED_ADDRESS


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


# --- The census door, and the ratchet on it --------------------------------
#
# `census_row` prefers the row a shard sealed. The tests below are the guard on
# that preference: one that the door carries every cell the shard recorded, and
# one that names, column by column, what nothing writes yet.

#: A value for each string column the row constrains by pattern. Keyed on the
#: pattern rather than the column, so a column that joins an existing family is
#: filled the day it lands, and a column in a NEW family raises here by name
#: instead of arriving empty and unnoticed.
_BY_PATTERN: Final[Mapping[str, str]] = {
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$": "2026-08-21T06:00:00Z",
    r"^[a-z0-9][a-z0-9_.+-]*$": "fixture",
    r"^[ -~]+$": "a value this column accepts",
}

#: A value for each plain column, by its own declared type.
_BY_TYPE: Final[Mapping[type, object]] = {bool: True, int: 1, float: 1.0, str: "fixture"}

#: Every column no production writer fills today, and the reason each one is
#: empty. **It is empty, and that is the ratchet at its tightest**: all 119
#: columns have a producer, so the assertion below reads "no column of this row
#: is None on the way through" with no exceptions to read past. The last three
#: left on 2026-09-16, when the slot columns started carrying the item's first
#: call. A column that arrives with no writer is added here with its reason,
#: which is the one way to land empty and still pass.
UNFILLED: Final[Mapping[str, str]] = {}


def _a_cell(name: str, annotation: Any) -> Any:
    """A value this column accepts, read off the column's own declared type.

    Nothing here is keyed on a column name, so a column added to the contract is
    filled by whichever branch its type lands in. A type no branch knows raises
    and names the column, which is the whole point.
    """
    inner = next((arg for arg in get_args(annotation) if arg is not type(None)), annotation)
    if get_origin(inner) is Annotated:
        base, *metadata = get_args(inner)
        constraint = next((meta for meta in metadata if isinstance(meta, StringConstraints)), None)
        pattern = constraint.pattern if constraint is not None else None
        if pattern is not None:
            if not isinstance(pattern, str) or pattern not in _BY_PATTERN:
                raise AssertionError(f"{name} constrains its text a way this test cannot fill")
            return _BY_PATTERN[pattern]
    else:
        base = inner
    if isinstance(base, type) and issubclass(base, Enum):
        return next(iter(base))
    if base not in _BY_TYPE:
        raise AssertionError(f"{name} is typed a way this test cannot fill: {base}")
    return _BY_TYPE[base]


def a_recorded_row(**overrides: Any) -> ItemHealthRow:
    """The row a shard seals for an item, with every column it can carry filled.

    The identity cells come from the run-plan fixture so they agree with each
    other. The state cells are pinned because the contract pairs them: a row
    carries `http_status` only where it stopped at the fetch, and a failure code
    only where the stage it names can fail that way. The two call slots are
    filled whole with the flat cells equal to their sum, which is what
    `_a_recorded_call_is_recorded_whole` asks for. Everything else is filled
    from its own declared type by `_a_cell`.
    """
    planned = item()
    cells: dict[str, Any] = {
        name: _a_cell(name, field.annotation)
        for name, field in ItemHealthRow.model_fields.items()
        if name not in UNFILLED
    }
    cells.update(
        version=ItemHealthRow.schema_version(),
        date=plan().date,
        run_id="2026-08-21-1",
        item_id=planned.item_id,
        url_key=planned.url_key,
        canonical_url=planned.canonical_url,
        vertical=planned.vertical,
        source_id=planned.source_id,
        stage=ItemStage.FETCH,
        outcome=ItemOutcome.FAILED,
        code=FailureCode.HTTP_CLIENT_ERROR,
        http_status=404,
        model_calls=2,
        prefill_ms=2,
        decode_ms=2,
        input_tokens=2,
        output_tokens=2,
        cached_tokens=2,
    )
    cells.update(overrides)
    return ItemHealthRow.model_validate(cells)


def test_no_census_column_is_silently_unowned() -> None:
    """The ratchet: every column is filled on the way through, or named as empty.

    It cannot settle that a written value is the RIGHT value - only that no
    column is silently unowned. A cell that is present and wrong passes here and
    is caught by the test that owns the quantity.

    Two ways to fail, which is why the assertion is an exact equality. A column
    the shard records that the census drops fails on the left: that was the
    defect this row closes, when the census rebuilt from two payloads that
    between them could say 43 of the 113 columns the row carried then. A column
    nothing writes and nobody declared fails on the right, naming itself.

    **`UNFILLED` is empty, so the right side is the empty set** and this is one
    assertion rather than three. The two that checked the map's contents - that
    every key is a real column, and that none of them is an extraction cell -
    went with the last entry on 2026-09-16: a guard on an empty map passes for a
    reason unrelated to what it checks, and they come back with the entry that
    needs them.
    """
    recorded = a_recorded_row()

    carried = telemetry.census_row(
        recorded=recorded,
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
        extraction=ExtractionHealth(
            span_integrity=True, elements_found=3, element_class=ElementClass.CHARTABLE
        ),
    )

    empty = {name for name in ItemHealthRow.csv_columns() if getattr(carried, name) is None}
    assert empty == set(UNFILLED)


def test_the_census_prefers_the_recorded_row_and_overlays_only_the_extraction_cells() -> None:
    """The shard's row wins cell for cell, except the three the census measures.

    The extraction cells are the one thing the work stage does not seal - it
    counts elements after the summary is written - so they are laid over the
    recorded row rather than derived a second time.
    """
    recorded = a_recorded_row(elements_found=3, element_class=ElementClass.CHARTABLE)
    overlay = ExtractionHealth(span_integrity=False, elements_found=None, element_class=None)

    carried = telemetry.census_row(
        recorded=recorded,
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
        extraction=overlay,
    )

    moved = {
        name
        for name in ItemHealthRow.csv_columns()
        if getattr(carried, name) != getattr(recorded, name)
    }
    assert moved == set(EXTRACTION_CELLS)
    assert (carried.span_integrity, carried.elements_found, carried.element_class) == (
        False,
        None,
        None,
    )


def test_an_item_whose_shard_sealed_nothing_is_rebuilt_from_its_payloads() -> None:
    """The fallback stays: an item whose worker died still needs a census line.

    Nothing wrote a row for it, so there is nothing to prefer, and the row the
    census builds says what the two payloads can say and no more.
    """
    rebuilt = telemetry.census_row(
        recorded=None,
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert rebuilt == telemetry.classify_item(
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
    )
    assert rebuilt.stage is ItemStage.PUBLISH
    assert rebuilt.cpu_model is None


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


def test_unknown_detail_is_sanitized_guarded_and_fitted_to_its_column() -> None:
    """A detail is cut to the column's own ceiling, not to a number written here.

    The ceiling moved from 200 to 2,000 on 2026-09-15 and this test did not have
    to be edited, which is the point: a test restating a bound is one more place
    the bound can drift from the column.
    """
    row = row_for(FailureCode.UNKNOWN)
    _, _, ceiling = column_bounds(field_column(ItemHealthRow.model_fields["detail"]))

    assert row.detail is not None
    assert not row.detail.startswith(("=", "+", "-", "@", "\t", "\r"))
    assert ceiling is not None
    assert len(row.detail) <= ceiling
    assert len(telemetry.detail_cell("x" * (ceiling * 3))) <= ceiling


def test_a_detail_the_column_would_refuse_is_folded_rather_than_dropped() -> None:
    """The live defect: a dash in a failure message killed the row reporting it.

    `ItemHealthDetail` takes printable ASCII on one line. A Pydantic
    `ValidationError` quotes the value it refused, so a page title's curly quote
    arrives inside the message saying the title was refused - and the row that
    raised was the only record that anything had gone wrong.
    """
    adapter = TypeAdapter(ItemHealthDetail)
    hostile = {
        "em_dash": "the model \u2014 not the runtime \u2014 refused",
        "curly_quote": "the page\u2019s own \u201cheadline\u201d",
        "non_latin": "\u0418\u0437\u0432\u0435\u0441\u0442\u0438\u044f",
        "emoji": "shipped \U0001f680",
        "newline": "first\nsecond",
        "replacement": "read \ufffd\ufffd back",
    }

    for case, raw in hostile.items():
        cell = telemetry.detail_cell(raw)
        adapter.validate_python(cell)
        assert cell, f"{case} produced an empty detail"
        assert len(cell.splitlines()) == 1, f"{case} produced more than one line"

    assert telemetry.detail_cell("the model \u2014 not the runtime") == (
        "the model - not the runtime"
    )
    assert telemetry.detail_cell("\u0418\u0437\u0432\u0435\u0441\u0442\u0438\u044f") == "?"


def test_a_detail_that_folds_away_to_nothing_still_says_a_failure_happened() -> None:
    """`detail` has `min_length=1`, so the floor cannot be an empty string.

    A row whose detail folded to nothing is still a row reporting a failure. An
    empty cell would raise and take that report with it.
    """
    assert telemetry.detail_cell("") == UNSPECIFIED
    assert telemetry.detail_cell("   ") == UNSPECIFIED
    assert telemetry.detail_cell("\u200b\u200b") == UNSPECIFIED


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


def test_the_census_row_says_which_call_each_number_came_from() -> None:
    """The summary's slots reach the ledger, and the ledger stays their sum.

    This is the only ledger carrying every planned item, so it is where a
    per-call cost has to land for anything later to read it. The translation is
    one function - a CSV line cannot nest - and the fact worth pinning is that
    the two cache figures survive it apart.
    """
    calls = (
        CallCost(
            kind=CallKind.LABEL,
            prefill_ms=214122,
            decode_ms=88795,
            input_tokens=1497,
            output_tokens=205,
            cached_tokens=0,
        ),
        CallCost(
            kind=CallKind.SUMMARIZE_AND_PLAN,
            prefill_ms=186750,
            decode_ms=292626,
            input_tokens=2389,
            output_tokens=567,
            cached_tokens=1493,
        ),
    )
    totals = {
        field: sum(getattr(call, field) for call in calls)
        for field in ("prefill_ms", "decode_ms", "input_tokens", "output_tokens", "cached_tokens")
    }
    split = summary().model_copy(update={"call_1": calls[0], "call_2": calls[1], **totals})

    row = telemetry.classify_item(
        planned=item(), date=plan().date, run_id="2026-08-21-1", article=article(), summary=split
    )

    assert row.model_calls == 2
    assert (row.label_kind, row.summary_kind) == (CallKind.LABEL, CallKind.SUMMARIZE_AND_PLAN)
    assert row.label_cached_tokens == 0, "the first call read its prompt cold"
    assert row.summary_cached_tokens == 1493
    assert row.cached_tokens == 1493, "the folded cell is their sum and says neither"

    cells = row.csv_row()
    assert cells["label_kind"] == "label"
    assert ItemHealthRow.from_csv_row(cells) == row


def test_a_rebuilt_row_carries_the_six_cells_that_are_arithmetic() -> None:
    """The six columns a row the shard never sealed used to leave empty.

    Every one of them is arithmetic over five cells the row already carries, so
    the cost of leaving them blank is not the number - it is that each reader
    works it out again, and the readers then disagree. All 12,437 committed rows
    carry these six empty, which is the whole reason the row exists.

    The numbers are chosen so the prefill rate tells one convention from the
    other: 1,224 prompt tokens in 6.2 seconds is 197.42 a second over the whole
    prompt, and 8.39 over the 52 the server had not already read.
    """
    calls = (
        CallCost(
            kind=CallKind.LABEL,
            prefill_ms=500,
            decode_ms=1_250,
            input_tokens=1_000,
            output_tokens=41,
            cached_tokens=175,
        ),
        CallCost(
            kind=CallKind.SUMMARIZE_AND_PLAN,
            prefill_ms=6_200,
            decode_ms=3_300,
            input_tokens=1_224,
            output_tokens=193,
            cached_tokens=1_172,
        ),
    )
    totals = {field: sum(getattr(call, field) for call in calls) for field in COST_FIELDS}
    split = summary().model_copy(update={"call_1": calls[0], "call_2": calls[1], **totals})

    row = telemetry.classify_item(
        planned=item(), date=plan().date, run_id="2026-08-21-1", article=article(), summary=split
    )

    assert row.label_cache_pct == 17.5
    assert row.summary_cache_pct == 95.75
    assert row.label_prefill_tokens_per_s == 1650.0, "825 tokens evaluated in half a second"
    assert row.summary_prefill_tokens_per_s == 8.39, "52 tokens evaluated, not 1,224"
    assert row.label_decode_tokens_per_s == 32.8
    assert row.summary_decode_tokens_per_s == 58.48

    cells = row.csv_row()
    assert cells["summary_prefill_tokens_per_s"] == "8.39"
    assert ItemHealthRow.from_csv_row(cells) == row


def test_a_call_with_no_clock_to_divide_by_writes_null_and_not_zero() -> None:
    """A rate of zero claims the model produced nothing in measurable time.

    That is a different statement from "this call reports no clock", and it is
    the difference between a skipped row and a zero dragging down every average
    that reads the column. The share of the prompt that was cached still lands,
    because that denominator is there.
    """
    no_clock = CallCost(
        kind=CallKind.LABEL,
        prefill_ms=0,
        decode_ms=0,
        input_tokens=900,
        output_tokens=12,
        cached_tokens=300,
    )
    totals = {field: getattr(no_clock, field) for field in COST_FIELDS}
    split = summary().model_copy(update={"call_1": no_clock, "call_2": None, **totals})

    row = telemetry.classify_item(
        planned=item(), date=plan().date, run_id="2026-08-21-1", article=article(), summary=split
    )

    assert row.model_calls == 1
    assert row.label_cache_pct == 33.33, "the share is answerable, the rates are not"
    assert row.label_prefill_tokens_per_s is None
    assert row.label_decode_tokens_per_s is None
    assert row.csv_row()["label_prefill_tokens_per_s"] == ""


def test_both_writers_of_the_six_reach_the_same_arithmetic() -> None:
    """The test that would have caught the second divider.

    Two places fill these cells - the work stage as the call returns, and the
    census when it rebuilds a row from the payloads - and a rate written two
    ways is two rates. The work stage's own cell builder is driven here against
    the contract's properties on the same five numbers, so the day one of them
    changes denominator is the day this goes red rather than the day an operator
    notices one day's column reads three times the next.
    """
    from idhazh.stages.two_calls import _call_cells

    reply = Completion(
        content="{}",
        prompt_tokens=1_224,
        completion_tokens=193,
        prefill_ms=6_200,
        decode_ms=3_300,
        cached_tokens=1_172,
    )
    same = CallCost(
        kind=CallKind.SUMMARIZE_AND_PLAN,
        prefill_ms=reply.prefill_ms,
        decode_ms=reply.decode_ms,
        input_tokens=reply.prompt_tokens,
        output_tokens=reply.completion_tokens,
        cached_tokens=reply.cached_tokens,
    )
    written = _call_cells("summary", CallKind.SUMMARIZE_AND_PLAN, reply, wall_ms=9_700)

    assert {field: written[f"summary_{field}"] for field in DERIVED_FIELDS} == {
        field: getattr(same, field) for field in DERIVED_FIELDS
    }
    assert same.prefill_tokens_per_s == 8.39, "both of them over the evaluated tokens"


def test_a_refused_reply_reaches_the_census_row_with_what_it_cost() -> None:
    """Defect 19's second half: the summary carried the numbers and this row dropped them.

    `reconcile_prefill.pool_ledger` skips a row whose `prefill_ms` or
    `input_tokens` cell is empty, so a blank here is not a zero in the pool - it
    is a request the server counted and the ledger never saw. The row is driven
    through the real stage from a recorded reply, so the cells are the server's.
    """
    ok_article = article()
    reply = parse_completion(
        read_text(REPO_ROOT / "tests" / "fixtures" / "completions" / "timed.json")
    )
    assert reply.prefill_ms and reply.prompt_tokens, "a free reply would prove nothing"
    unreadable = summarize.to_summary(
        ok_article,
        replace(reply, content="{bad"),
        model_id="qwen3-8b",
        generated_at="2026-08-21T06:00:00Z",
    )
    assert unreadable.failure_code is FailureCode.BAD_SHAPE

    row = telemetry.classify_item(
        planned=item(),
        article=ok_article,
        summary=unreadable,
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert row.outcome is ItemOutcome.FAILED
    assert row.prefill_ms == reply.prefill_ms
    assert row.input_tokens == reply.prompt_tokens
    assert row.model_calls == 1
    assert row.label_kind is CallKind.SUMMARIZE
    cells = row.csv_row()
    assert cells["prefill_ms"] and cells["input_tokens"], "an empty cell is skipped, not pooled"


def test_a_summarize_call_that_never_returned_leaves_the_cost_cells_empty() -> None:
    """A null is not a zero, and inventing one here would be the same defect twice.

    Nothing came back, so there is no number to copy. The cells stay blank, which
    is what keeps a pooled read skipping the row rather than averaging it in.
    """
    row = row_for(FailureCode.MODEL_UNREACHABLE)

    assert row.outcome is ItemOutcome.FAILED
    assert row.prefill_ms is None
    assert row.input_tokens is None
    assert row.model_calls is None
    assert row.csv_row()["prefill_ms"] == ""


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


#: The header a run wrote before the truncation counters existed, and the point
#: of building it is that no run of this checkout can produce one. Eleven names
#: every row has always filled plus the three body counts of that generation -
#: `source_words_before_cap` is deliberately absent, because that is the column
#: the migration below has to add to a file it did not write.
AN_OLDER_GENERATION: Final = (
    "version",
    "date",
    "run_id",
    "item_id",
    "url_key",
    "canonical_url",
    "vertical",
    "source_id",
    "stage",
    "outcome",
    "code",
    "source_chars",
    "source_words",
    "summary_words",
)


def a_day_file_from_before_the_cap_counter(path: Path, rows: list[ItemHealthRow]) -> None:
    """One day file under that header, written the way a run of the day wrote it.

    Every cell comes from the row's own `csv_row`, so the file cannot drift from
    the contract it is meant to predate - only the column list is older.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.writer(handle, lineterminator="\n")
        out.writerow(AN_OLDER_GENERATION)
        for row in rows:
            payload = row.csv_row()
            out.writerow([payload[name] for name in AN_OLDER_GENERATION])


def test_a_day_file_from_before_the_cap_counter_still_takes_todays_row(tmp_path: Path) -> None:
    """The Oracle, second half: append to a file written under an older header.

    `require_matching_header` compares the header tuple exactly, so the commit
    that gave the contract a column stops the file the pipeline is appending to
    until it is widened by the same column. That is a failed scheduled run, not
    a failed lint. This is the run a release blocker would fail, and it also
    proves the widened file can carry a real value - an absence check on its own
    passes on a file nothing was ever written to.

    **The narrow file is built, not checked out.** It used to be a byte copy of
    the newest committed shard, which made the test pass or fail on which day
    the archive happened to end at: a widening landing before that shard
    migrated turned it red on a pull request that touched neither
    (`CLAUDE.md` section 13). A header this checkout cannot write is the input
    the question actually needs, and it carries the case the archive no longer
    holds - a row from before the cap counters, whose cell has to migrate to
    empty rather than to a number nobody measured.
    """
    date_ = plan().date
    state = tmp_path / "state"
    target = ledger.item_health_path(state, date_) / day_shards.SETTLED_NAME
    earlier = telemetry.classify_item(
        planned=item(),
        article=article(),
        summary=summary(),
        date=date_,
        run_id=f"{date_}-1",
    )
    a_day_file_from_before_the_cap_counter(target, [earlier])
    before = records(target)
    assert "source_words_before_cap" not in before[0], "the fixture is not older than the column"

    fresh = telemetry.classify_item(
        planned=item(),
        article=cut_article(before=2610, after=1923),
        summary=summary(),
        date=date_,
        run_id=f"{date_}-9",
    )
    assert (date_, fresh.run_id, fresh.item_id) not in ledger.recorded_item_health(target)

    assert seed_item_health(state, date_, [fresh]) == 1

    after = records(target)
    assert ledger.read_header(target) == ItemHealthRow.csv_columns()
    assert len(after) == 2, "the migration dropped or duplicated a row"
    assert after[0]["item_id"] == earlier.item_id
    assert after[0]["source_words"] == before[0]["source_words"], (
        "the widening moved a cell an earlier run wrote"
    )
    assert after[0]["source_words_before_cap"] == "", (
        "a row from before the counter never measured the full body, and a number "
        "here would read as an article nothing cut"
    )
    assert after[-1]["source_words_before_cap"] == "2610"
    assert after[-1]["source_words"] == "1923"


# --- Which worker wrote the row ---------------------------------------------


def flagged_article() -> Article:
    """An article extract kept and flagged, so the degraded-but-done case has a payload."""
    return extract.to_article(
        item(),
        FetchResult(
            FetchOutcome.OK,
            status=200,
            body=b"<html><body><article><p>Two words.</p></article></body></html>",
        ),
        config=config.load(CONFIG_DIR).app.extract,
        fetched_at="2026-08-21T06:00:00Z",
    )


def refused_summary() -> Summary:
    return summary().model_copy(
        update={
            "status": "failed",
            "summary": None,
            "failure_code": FailureCode.MODEL_UNREACHABLE,
        }
    )


def every_case() -> dict[str, tuple[Article | None, Summary | None]]:
    """One payload pair for each place `classify_item` builds a row."""
    return {
        "nothing reached it": (None, None),
        "extract failed": (failed_article(ArticleStatus.EXTRACT_FAILED, "=SUM(1,1)"), None),
        "extract flagged it and stopped": (flagged_article(), None),
        "the summary payload is missing": (article(), None),
        "the model refused": (article(), refused_summary()),
        "published": (article(), summary()),
    }


def test_every_case_of_the_classifier_carries_the_shard() -> None:
    """Six places build a row and a shard missed on one is a hole in the join.

    The hole would not raise: the cell reads empty, which is the same thing an
    unclaimed row says, so a per-shard figure would quietly drop those items and
    still add up to a plausible number.
    """
    for name, (payload, reply) in every_case().items():
        row = telemetry.classify_item(
            planned=item(),
            article=payload,
            summary=reply,
            date=plan().date,
            run_id="2026-08-21-1",
            shard=6,
        )
        assert row.shard == 6, f"{name} lost the shard"
        assert row.csv_row()["shard"] == "6", f"{name} did not write the shard"


def test_shard_zero_is_a_worker_and_an_empty_cell_is_not() -> None:
    """The one confusion this column can cause, refused at the round trip.

    Every row committed before 2026-08-30 has an empty cell, and there are
    thousands of them. A reader that coerces empty to zero would hand shard 0 the
    whole history of the ledger and report it as the slowest machine we own.
    """
    worker = telemetry.classify_item(
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
        shard=0,
    )
    unclaimed = telemetry.classify_item(
        planned=item(),
        article=article(),
        summary=summary(),
        date=plan().date,
        run_id="2026-08-21-1",
    )

    assert worker.csv_row()["shard"] == "0"
    assert unclaimed.csv_row()["shard"] == ""
    assert ItemHealthRow.from_csv_row(worker.csv_row()).shard == 0
    assert ItemHealthRow.from_csv_row(unclaimed.csv_row()).shard is None


def test_a_row_written_before_the_shard_column_reads_as_unclaimed() -> None:
    old = ItemHealthRow(
        version="2026-08-28",
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
    old.pop("shard")

    row = ItemHealthRow.from_csv_row(old)

    assert row.shard is None


# --- The event envelope ------------------------------------------------------


def test_a_summarize_failure_logs_the_envelope_the_helper_built(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A captured stream is the fixture, so the record is what gets asserted.

    Every event is a plain serializable payload, which is what lets a test read
    back what a stage logged with no mocks and no network (Guardrail #7). Asserting
    the whole key set matters more than any one value: the point of the helper
    is that a second emitter cannot ship a different set.
    """
    with caplog.at_level(logging.WARNING, logger="idhazh"):
        _log_no_reply(
            article(),
            model_id="qwen3.5-9b-q4_k_m",
            code=FailureCode.MODEL_UNREACHABLE,
            error=OSError("connection refused"),
            run_id="2026-08-21-1",
        )

    assert len(caplog.records) == 1
    envelope = json.loads(caplog.records[0].getMessage())

    assert sorted(envelope) == ["ctx", "data", "level", "name", "run", "src", "ts", "v"]
    assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", envelope["ts"])
    assert envelope["src"] == ItemStage.SUMMARIZE.value
    assert envelope["v"] == telemetry.ENVELOPE_VERSION
    assert envelope["run"] == "2026-08-21-1"
    assert envelope["name"] == telemetry.EventName.ITEM_SUMMARIZE_FAILED.value
    assert envelope["level"] == telemetry.EventLevel.WARNING.value
    assert envelope["ctx"] == {
        "item_id": article().item_id,
        "source_id": article().source_id,
        "model_id": "qwen3.5-9b-q4_k_m",
    }
    assert envelope["data"] == {
        "failure_code": FailureCode.MODEL_UNREACHABLE.value,
        "error_type": "OSError",
    }


def test_the_concept_page_names_no_event_the_code_cannot_emit() -> None:
    """The page listed 20 names and one of them had an emitter.

    So the list read as a promise, and nothing told a reader which names fire.
    This is the check that stops the page and the vocabulary drifting apart
    again, in either direction.

    **The prefix list is read off the vocabulary rather than written out.** It
    was `run|stage|item` and the six flat records added 2026-09-15 brought two
    more prefixes with them, so a hand-written alternation would have let
    `model.waiting` and `shard.done` go unnamed on the page while the test
    stayed green - which is the exact failure it exists to catch.
    """
    page = (REPO_ROOT / "docs" / "concepts" / "telemetry.md").read_text(encoding="utf-8")
    prefixes = "|".join(sorted({name.value.split(".")[0] for name in telemetry.EventName}))
    named = set(re.findall(rf"`((?:{prefixes})\.[a-z.]+)`", page))

    assert named == {name.value for name in telemetry.EventName}


# --- the span rollup ---------------------------------------------------------


def a_span(name: telemetry.SpanName, duration_ms: int, *, index: int = 1) -> telemetry.Span:
    """One finished span, built straight from the dataclass - no tracer, no clock."""
    return telemetry.Span(
        trace_id="2026-08-21-1-energy-01",
        span_id=f"{name.value}-{index:03d}",
        parent_id=None,
        name=name,
        kind=telemetry.SpanKind.SPAN,
        started_at="2026-08-21T06:00:00Z",
        duration_ms=duration_ms,
        attributes={},
    )


def test_the_committed_spans_are_a_named_subset_of_the_tracer_vocabulary() -> None:
    """The five committed span names must each be a name the tracer opens, so the
    fold's contract enum cannot name a span that does not exist."""
    committed = {member.value for member in RollupSpan}
    assert committed == {"item", "robots", "tag", "render_prompt", "parse_reply"}
    assert committed <= {name.value for name in telemetry.SpanName}


def test_the_fold_keeps_only_the_five_committed_spans() -> None:
    """Open every span the tracer knows; the fold keeps the five and drops the six
    a ledger column already times."""
    spans = [a_span(name, 5) for name in telemetry.SpanName]
    rows = telemetry.roll_up_spans(
        spans, date="2026-08-21", run_id="2026-08-21-1", shard=0, wall_clock_ms=1000
    )
    assert [row.span_name for row in rows] == list(RollupSpan)
    dropped = {name.value for name in telemetry.SpanName} - {row.span_name.value for row in rows}
    assert dropped == {"fetch", "extract", "summarize", "model_call", "score", "visual_planner"}


def test_the_fold_counts_the_spans_and_sums_their_durations() -> None:
    spans = [
        a_span(telemetry.SpanName.ROBOTS, 10, index=1),
        a_span(telemetry.SpanName.ROBOTS, 20, index=2),
        a_span(telemetry.SpanName.ROBOTS, 0, index=3),
        a_span(telemetry.SpanName.ITEM, 900, index=1),
    ]
    rows = telemetry.roll_up_spans(
        spans, date="2026-08-21", run_id="2026-08-21-1", shard=3, wall_clock_ms=1000
    )
    by_name = {row.span_name: row for row in rows}
    robots = by_name[RollupSpan.ROBOTS]
    assert (robots.count, robots.total_ms) == (3, 30)
    assert (robots.date, robots.run_id, robots.shard) == ("2026-08-21", "2026-08-21-1", 3)
    item = by_name[RollupSpan.ITEM]
    assert (item.count, item.total_ms) == (1, 900)


def test_a_span_the_shard_never_opened_gets_no_row() -> None:
    """An absent row reads as never opened; a zero row would read as opened and
    measured nothing, which is a different fact."""
    rows = telemetry.roll_up_spans(
        [a_span(telemetry.SpanName.ITEM, 100)],
        date="2026-08-21",
        run_id="2026-08-21-1",
        shard=0,
        wall_clock_ms=1000,
    )
    assert [row.span_name for row in rows] == [RollupSpan.ITEM]
    assert all(row.count >= 1 for row in rows)


def test_the_fold_writes_one_month_shard_and_a_re_run_adds_nothing(tmp_path: Path) -> None:
    """The shard's fold lands once. A re-run recomputes the same numbers, and the
    compaction settles them against the grain rather than doubling every count.

    Through the two calls the pipeline makes rather than through a seed, because
    the claim in the name is now shared between them: the shard writes its fold
    to a segment named for its own attempt, and `stage_compact` merges the
    segments into the month the rows name. A second attempt writes a second
    segment, so the only thing standing between a re-run and a doubled count is
    `SPAN_ROLLUP_KEY`.
    """
    state = tmp_path / "state"
    spans = [
        a_span(telemetry.SpanName.ITEM, 900),
        a_span(telemetry.SpanName.ROBOTS, 10),
        a_span(telemetry.SpanName.TAG, 5),
    ]
    rows = telemetry.roll_up_spans(
        spans, date="2026-08-21", run_id="2026-08-21-1", shard=0, wall_clock_ms=1000
    )
    for attempt in (1, 2):
        assert (
            ledger.write_segment(
                state,
                ledger.SegmentLedger.SPAN_ROLLUP,
                rows,
                run_id="2026-08-21-1",
                attempt=attempt,
                job=ServerJob.WORK,
                shard=0,
            )
            == 3
        )
    report = fold(state, "2026-08-21")
    assert report.trees_touched == (ledger.SPAN_ROLLUP_DIRNAME,)

    shard = ledger.span_rollup_path(state, "2026-08-21") / day_shards.SETTLED_NAME
    written = [
        SpanRollupRow.from_csv_row(raw) for raw in csv.DictReader(shard.read_text().splitlines())
    ]
    assert [row.span_name for row in written] == [
        RollupSpan.ITEM,
        RollupSpan.ROBOTS,
        RollupSpan.TAG,
    ]
    assert {row.span_name: row.total_ms for row in written} == {
        RollupSpan.ITEM: 900,
        RollupSpan.ROBOTS: 10,
        RollupSpan.TAG: 5,
    }


def test_the_item_row_carries_the_shard_wall_clock_the_spans_do_not_cover() -> None:
    """Every second of the shard is accounted for: the item spans plus the residual
    equal the wall clock, and the residual rides on the item row."""
    spans = [
        a_span(telemetry.SpanName.ITEM, 700, index=1),
        a_span(telemetry.SpanName.ITEM, 500, index=2),
        a_span(telemetry.SpanName.ROBOTS, 40),
    ]
    rows = telemetry.roll_up_spans(
        spans, date="2026-08-21", run_id="2026-08-21-1", shard=0, wall_clock_ms=1500
    )
    by_name = {row.span_name: row for row in rows}
    item = by_name[RollupSpan.ITEM]
    # 700 + 500 inside the two item spans, 300 of overhead the shard spent outside them.
    assert item.total_ms == 1200
    assert item.unattributed_ms == 300
    assert item.total_ms + item.unattributed_ms == 1500
    # The residual is the shard's, filed once on the item row, never on a sub-step.
    assert by_name[RollupSpan.ROBOTS].unattributed_ms is None


def test_spans_claiming_more_than_the_shard_ran_do_not_reconcile() -> None:
    """The residual is never rounded to zero: item spans totalling more than the wall
    clock mean the timing is wrong, and the fold raises rather than lie."""
    spans = [a_span(telemetry.SpanName.ITEM, 1200)]
    with pytest.raises(ValueError, match="claim 1200 ms but the shard ran for 900 ms"):
        telemetry.roll_up_spans(
            spans, date="2026-08-21", run_id="2026-08-21-1", shard=0, wall_clock_ms=900
        )


def test_the_residual_may_not_ride_on_a_non_item_row() -> None:
    """unattributed_ms is the shard residual; a value on any row but the item row would
    be a smaller thing wearing the shard's number, and the contract refuses it."""
    with pytest.raises(ValidationError):
        SpanRollupRow(
            version=SpanRollupRow.schema_version(),
            date="2026-08-21",
            run_id="2026-08-21-1",
            shard=0,
            span_name=RollupSpan.ROBOTS,
            count=1,
            total_ms=40,
            unattributed_ms=300,
        )


# --- committed trace paths ---------------------------------------------------


def test_a_committed_trace_relpath_names_the_writer_under_the_day_it_ran() -> None:
    """state/traces/<YYYY>/<MM>/<DD>/<run>-<attempt>-<job>-<shard>.jsonl.

    The three directories are the run's own date and the name is the identity of
    the one writer that can have written the file - the same four elements every
    day tree spells, so two jobs of one run and two attempts at one job never
    arrive at one path.
    """
    assert (
        telemetry.committed_trace_relpath(
            run_id="2026-08-21-1", attempt=1, job=ServerJob.WORK, shard=0
        )
        == "state/traces/2026/08/21/2026-08-21-1-1-work-00.jsonl"
    )


def test_the_shard_is_zero_padded_and_a_multi_digit_ordinal_survives() -> None:
    """The shard matches the run's other per-shard names; the ordinal is left as is."""
    assert (
        telemetry.committed_trace_relpath(
            run_id="2026-08-21-12", attempt=2, job=ServerJob.WORK, shard=3
        )
        == "state/traces/2026/08/21/2026-08-21-12-2-work-03.jsonl"
    )


def test_a_committed_trace_path_and_its_date_round_trip(tmp_path: Path) -> None:
    """The path a run writes and the date the prune reads back are one thing.

    Build the file under a state tree, read the date straight back out of the
    path, and get the run's own day - the round trip `prune_traces` depends on to
    decide which files are past the window.
    """
    state = tmp_path / "state"
    path = telemetry.committed_trace_path(
        state, run_id="2026-08-21-1", attempt=1, job=ServerJob.WORK, shard=0
    )
    assert path == state / "traces" / "2026" / "08" / "21" / "2026-08-21-1-1-work-00.jsonl"
    assert telemetry.trace_date(path, state / "traces") == date(2026, 8, 21)


def test_a_path_that_is_not_a_trace_reads_as_no_date(tmp_path: Path) -> None:
    """A stray file under the tree is left alone, so it reports no date.

    The prune deletes on a date and skips a None, so a file at the wrong depth or
    with an unparseable day is never a candidate - the rule `month_shards` keeps
    for the ledger directories.
    """
    root = tmp_path / "traces"
    assert (
        telemetry.trace_date(root / "2026" / "08" / "notaday" / "a-1-work-00.jsonl", root) is None
    )
    assert telemetry.trace_date(root / "2026" / "08.jsonl", root) is None
    assert telemetry.trace_date(tmp_path / "elsewhere.jsonl", root) is None


def test_a_run_id_that_is_not_a_date_and_ordinal_is_refused() -> None:
    """The helper guards the shape the RunId type already promises upstream."""
    with pytest.raises(ValueError, match="not <YYYY>-<MM>-<DD>-<ordinal>"):
        telemetry.committed_trace_relpath(
            run_id="2026-08-21", attempt=1, job=ServerJob.WORK, shard=0
        )
