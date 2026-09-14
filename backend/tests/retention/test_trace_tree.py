"""How far back does the trace tree reach, and what bounds it?"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import telemetry
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.retention import TracePruneResult, prune_traces
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    RUN_ID,
    TODAY,
)

pytestmark = pytest.mark.slow


#: A day inside the committed window's own month, so the fixtures below read as a
#: recent run rather than one the seen tests already use.
TRACE_TODAY: Final = date(2026, 8, 20)


def _write_trace(state: Path, run_id: str, shard: int = 0, *, spans: int = 45) -> Path:
    """One shard's committed trace at the real path, with real span records in it.

    The bytes are a `telemetry.Span` serialized the way `FileSink` writes it, so
    a per-run size the byte-bound test reads off the fixture is the size a run
    actually writes rather than a number this test invented.
    """
    path = telemetry.committed_trace_path(state, run_id, shard)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = telemetry.Span(
        trace_id="unattributed",
        span_id="item-000",
        parent_id=None,
        name=telemetry.SpanName.ITEM,
        kind=telemetry.SpanKind.SPAN,
        started_at=f"{run_id[:10]}T02:20:00Z",
        duration_ms=1234,
        attributes={"run_id": run_id, "shard": shard, "url_key": "a" * 64},
    ).as_record()
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join([line] * spans) + "\n", encoding="utf-8")
    return path


def test_a_trace_past_the_window_is_gone_and_a_recent_one_stays(tmp_path: Path) -> None:
    """The oracle: the oldest trace is deleted, the newest is kept, on the real path.

    Four runs across the seven-day boundary. `2026-08-14` is six days back and
    inside the window; `2026-08-13` is seven days back and outside it - so the
    boundary itself is exercised, not just a run three weeks old.
    """
    state = tmp_path / "state"
    window = ObservabilityConfig().trace_window_days
    newest = _write_trace(state, "2026-08-20-1")
    edge_kept = _write_trace(state, "2026-08-14-1")
    edge_gone = _write_trace(state, "2026-08-13-1")
    oldest = _write_trace(state, "2026-07-30-1")

    result = prune_traces(state, today=TRACE_TODAY, within_days=window)

    assert newest.exists()
    assert edge_kept.exists()
    assert not edge_gone.exists(), "a trace seven days back was inside the window"
    assert not oldest.exists()
    assert result.kept == 2
    assert telemetry.committed_trace_relpath("2026-07-30-1", 0) in result.deleted
    assert telemetry.committed_trace_relpath("2026-08-20-1", 0) not in result.deleted


def test_the_window_bounds_the_tree_by_construction(tmp_path: Path) -> None:
    """The bound is a number, not an intent: surviving bytes <= window x per-run.

    Seeded with one run a day for a month at a real per-run size, the tree
    collapses to exactly the window's worth of files. Measured 2026-09-06 off a
    real traced run: about 0.47 MB for the 160-item work spans, so a seven-day
    window bounds state/traces/ well under the 1 GB Pages reference it is not
    even part of.
    """
    state = tmp_path / "state"
    window = ObservabilityConfig().trace_window_days
    per_run = 0
    for back in range(30):
        run_day = TRACE_TODAY - timedelta(days=back)
        per_run = max(per_run, _write_trace(state, f"{run_day.isoformat()}-1").stat().st_size)

    result = prune_traces(state, today=TRACE_TODAY, within_days=window)

    root = state / "traces"
    files = list(root.rglob("*.jsonl"))
    surviving = sum(path.stat().st_size for path in files)
    assert len(files) == window, "one run a day, so exactly the window's days survive"
    assert surviving <= window * per_run
    assert result.kept == window


def test_an_empty_trace_tree_is_a_no_op(tmp_path: Path) -> None:
    """state/traces/ does not exist until tracing is switched on (a later plan), so
    the prune walks nothing and changes nothing on every run until then."""
    state = tmp_path / "state"
    result = prune_traces(
        state, today=TRACE_TODAY, within_days=ObservabilityConfig().trace_window_days
    )
    assert result == TracePruneResult(deleted=(), bytes_freed=0, kept=0, dry_run=False)
    assert not result.changed


def test_a_dry_run_names_the_trace_and_leaves_it(tmp_path: Path) -> None:
    """The dry run's list is what a person reads before the deletion is switched on,
    so it names the file and removes nothing."""
    state = tmp_path / "state"
    stale = _write_trace(state, "2026-07-30-1")

    result = prune_traces(
        state,
        today=TRACE_TODAY,
        within_days=ObservabilityConfig().trace_window_days,
        dry_run=True,
    )

    assert telemetry.committed_trace_relpath("2026-07-30-1", 0) in result.deleted
    assert result.dry_run
    assert stale.exists()


def test_a_trace_newer_than_the_date_it_was_handed_is_never_deleted(tmp_path: Path) -> None:
    """A back-dated run keeps the traces since. `prune-state --date <last winter>`
    computes a window around then; every run since is newer and stays."""
    state = tmp_path / "state"
    window = ObservabilityConfig().trace_window_days
    live = _write_trace(state, "2026-08-20-1")
    stale = _write_trace(state, "2026-01-01-1")

    result = prune_traces(state, today=date(2026, 8, 5), within_days=window)

    assert live.exists(), "a trace ahead of the handed date was deleted"
    assert not stale.exists()
    assert telemetry.committed_trace_relpath("2026-01-01-1", 0) in result.deleted


def test_the_stage_reports_the_trace_window_it_measured(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A prune that deleted nothing still names the window, or 'nothing deleted' reads
    the same whether the window is seven days or the config went missing."""
    state = tmp_path / "state"
    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "trace prune: every committed trace is inside the" in caplog.text
    assert str(ObservabilityConfig().trace_window_days) in caplog.text
