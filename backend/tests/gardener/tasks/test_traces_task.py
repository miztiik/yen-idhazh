"""How far back does the traces task keep the committed span traces, and what bounds the tree?"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger, telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.gardener import DaysWindow

from ._task import declared, run_task

pytestmark = pytest.mark.contract

#: A day inside the committed window's own month, so the fixtures read as a recent run.
TRACE_TODAY: Final = date(2026, 8, 20)


def window_days() -> int:
    window = declared()["traces"].window
    assert isinstance(window, DaysWindow), "traces keeps a window of days"
    return window.value


def a_trace(root: Path, run_id: str) -> Path:
    """One shard's committed trace at the real path, with real span records in it."""
    path = telemetry.committed_trace_path(
        root / ledger.STATE_DIRNAME, run_id=run_id, attempt=1, job=ServerJob.WORK, shard=0
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    record = telemetry.Span(
        trace_id="unattributed",
        span_id="item-000",
        parent_id=None,
        name=telemetry.SpanName.ITEM,
        kind=telemetry.SpanKind.SPAN,
        started_at=f"{run_id[:10]}T02:20:00Z",
        duration_ms=1234,
        attributes={"run_id": run_id, "shard": 0, "url_key": "a" * 64},
    ).as_record()
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text(line + "\n", encoding="utf-8")
    return path


def relpath(run_id: str) -> str:
    return telemetry.committed_trace_relpath(run_id=run_id, attempt=1, job=ServerJob.WORK, shard=0)


def test_a_trace_past_the_window_goes_and_a_recent_one_stays(tmp_path: Path) -> None:
    """Across the boundary itself: six days back is kept, seven days back goes."""
    newest = a_trace(tmp_path, "2026-08-20-1")
    edge_kept = a_trace(tmp_path, "2026-08-14-1")
    edge_gone = a_trace(tmp_path, "2026-08-13-1")
    oldest = a_trace(tmp_path, "2026-07-30-1")

    outcome = run_task("traces", tmp_path, today=TRACE_TODAY, dry_run=False)

    assert newest.exists()
    assert edge_kept.exists()
    assert not edge_gone.exists(), "a trace seven days back was inside the window"
    assert not oldest.exists()
    assert sorted(outcome.taken) == [relpath("2026-07-30-1"), relpath("2026-08-13-1")]


def test_the_window_bounds_the_tree_by_construction(tmp_path: Path) -> None:
    """One run per kept day and one expired run prove the window's size bound."""
    per_run = 0
    for back in range(window_days() + 1):
        run_day = TRACE_TODAY - timedelta(days=back)
        per_run = max(per_run, a_trace(tmp_path, f"{run_day.isoformat()}-1").stat().st_size)

    run_task("traces", tmp_path, today=TRACE_TODAY, dry_run=False)

    files = list((tmp_path / ledger.STATE_DIRNAME / "traces").rglob("*.jsonl"))
    assert len(files) == window_days(), "one run a day, so exactly the window's days survive"
    assert sum(path.stat().st_size for path in files) <= window_days() * per_run


def test_a_tree_tracing_never_wrote_is_walked_as_nothing(tmp_path: Path) -> None:
    """`state/traces/` does not exist until tracing writes one, and then there is nothing to take."""
    outcome = run_task("traces", tmp_path, today=TRACE_TODAY, dry_run=False)

    assert (outcome.taken, outcome.seen, outcome.bytes_freed) == ((), 0, 0)


def test_a_dry_run_names_the_trace_and_leaves_it(tmp_path: Path) -> None:
    stale = a_trace(tmp_path, "2026-07-30-1")

    outcome = run_task("traces", tmp_path, today=TRACE_TODAY)

    assert outcome.dry_run, "traces ships in dry run"
    assert outcome.taken == (relpath("2026-07-30-1"),)
    assert stale.exists()


def test_a_trace_newer_than_the_date_it_was_handed_is_never_taken(tmp_path: Path) -> None:
    live = a_trace(tmp_path, "2026-08-20-1")
    stale = a_trace(tmp_path, "2026-01-01-1")

    outcome = run_task("traces", tmp_path, today=date(2026, 8, 5), dry_run=False)

    assert live.exists(), "a trace ahead of the handed date was taken"
    assert not stale.exists()
    assert outcome.taken == (relpath("2026-01-01-1"),)
