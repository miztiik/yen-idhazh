"""How far back does the trace tree reach, and what bounds it?"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Final

import pytest

from idhazh import telemetry
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    RUN_ID,
    TODAY,
)

#: A day inside the committed window's own month, so the fixtures below read as a
#: recent run rather than one the seen tests already use.
TRACE_TODAY: Final = date(2026, 8, 20)


def _write_trace(state: Path, run_id: str, shard: int = 0, *, spans: int = 45) -> Path:
    """One shard's committed trace at the real path, with real span records in it.

    The bytes are a `telemetry.Span` serialized the way `FileSink` writes it, so
    a per-run size the byte-bound test reads off the fixture is the size a run
    actually writes rather than a number this test invented.
    """
    path = telemetry.committed_trace_path(
        state, run_id=run_id, attempt=1, job=ServerJob.WORK, shard=shard
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
        attributes={"run_id": run_id, "shard": shard, "url_key": "a" * 64},
    ).as_record()
    line = json.dumps(record, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join([line] * spans) + "\n", encoding="utf-8")
    return path


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
                commit_sha="a" * 40,
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "trace prune: every committed trace is inside the" in caplog.text
    assert str(ObservabilityConfig().trace_window_days) in caplog.text
