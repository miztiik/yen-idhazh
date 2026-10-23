"""Verify native observation decisions survive the actual daily, monthly and yearly tasks."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from conftest import FIXTURES_DIR

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_health import FeedHealthRow, derive_endpoint_key
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.sources import FeedDef
from idhazh.health_order import availability_evidence
from idhazh.telemetry import source_health

from ._task import run_task


def verify_health_order_compaction(root: Path) -> None:
    """A bounded fixture year is read by date, so packaging alone is the variable."""
    base: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "feed-ingest-plan" / "feed-health-row.json").read_text(encoding="utf-8")
    )
    recording: dict[str, Any] = json.loads(
        (FIXTURES_DIR / "feed-ingest-plan" / "health-order-cases.json").read_text(encoding="utf-8")
    )
    day = base["date"]
    second = base["checked_at"][:-1]
    cases = recording["cases"]
    threshold = recording["threshold"]
    feeds = [
        FeedDef(
            id=case["id"], title=case["id"], vertical="ai",
            url=f"https://fixture.example/{case['id']}/feed", tier=1,
        )
        for case in cases
    ]
    state = root / ledger.STATE_DIRNAME
    raw_files: list[Path] = []
    for index, suffix in enumerate(recording["run_suffixes"]):
        run_id = f"{day}-{suffix}"
        rows = [
            FeedHealthRow.model_validate({
                **base,
                "version": "2026-09-02T20:00" if case["times"][index] == "Z" else FeedHealthRow.schema_version(),
                "run_id": run_id, "feed_id": feed.id,
                "checked_at": second + case["times"][index],
                "endpoint_key": derive_endpoint_key(feed.url),
                "outcome": case["kinds"][index], "status": case["statuses"][index],
                "items": 3 if case["kinds"][index] == "ok" else 0,
                "target_attempted": case["kinds"][index] != "skipped",
                "robots_outcome": None if case["kinds"][index] == "skipped" else base["robots_outcome"],
            })
            for case, feed in zip(cases, feeds, strict=True)
        ]
        raw_files.extend(ledger.persist(
            state, rows, ledger=LedgerName.FEED_HEALTH, covers=day,
            identity=WriterIdentity(
                run_id=run_id, attempt=1, job=ServerJob.PLAN, shard=0,
                producer="tests.health_order", git_sha="a" * 40,
            ),
        ))
    original = ledger.load_stored(raw_files, model=FeedHealthRow)
    known = {derive_endpoint_key(feed.url) for feed in feeds if feed.id == "known-retired"}

    def decisions() -> dict[str, str]:
        rows = ledger.load_days(state, LedgerName.FEED_HEALTH, [day], model=FeedHealthRow)
        records = source_health.endpoint_records(rows)
        retired = known | {
            row.endpoint_key
            for row in source_health.retirements(
                feeds, records=records, already=known, after_runs=threshold,
                date=day, run_id=f"{day}-999",
            )
        }
        result = {}
        for feed in feeds:
            evidence = availability_evidence(
                [row for row in rows if row.feed_id == feed.id], after_failures=threshold
            )
            result[feed.id] = (
                "retired" if derive_endpoint_key(feed.url) in retired
                else "resting" if evidence.resting is True
                else "unknown" if evidence.resting is None else "eligible"
            )
        return result

    expected = {case["id"]: case.get("python_expected", case["expected"]) for case in cases}
    assert decisions() == expected
    for period, today in (
        (Period.DAILY, date(2026, 10, 25)),
        (Period.MONTHLY, date(2027, 1, 5)),
        (Period.YEARLY, date(2027, 3, 10)),
    ):
        covers = day if period is Period.DAILY else day[:7] if period is Period.MONTHLY else day[:4]
        packed = None
        for _ in range(3):
            run_task(
                "compact-feed-health", root, today=today, dry_run=False,
                max_periods_per_run=None, daily_keep_days=31, monthly_keep_days=63,
                monthly_window={"unit": "forever"}, yearly_prune_enable=False,
            )
            packed = ledger.compact_file(state, LedgerName.FEED_HEALTH, period, covers)
            if packed is not None:
                break
        assert packed is not None, f"actual {period.value} task did not pack the named fixture day"
        held = ledger.load_stored([packed], model=FeedHealthRow)
        assert sorted(held, key=lambda row: (row.row.feed_id, row.row.run_id)) == sorted(
            original, key=lambda row: (row.row.feed_id, row.row.run_id)
        )
        assert decisions() == expected
