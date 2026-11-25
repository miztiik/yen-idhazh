"""Does the shipped visual attempt policy pack full records and then delete expired months?"""

from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest
from support.ledger import writer_identity

from idhazh import ledger
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual import PlanDecision
from idhazh.contracts.visual_decision import NoneReason, VisualState
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.ledger import json_lines, parquet
from idhazh.ledger.persist import file_columns

from ._task import declared, run_task

pytestmark = pytest.mark.contract
TASK = "compact-visual-design-attempts"
LEDGER = LedgerName.VISUAL_DESIGN_ATTEMPTS


def _write_an_old_file_without_the_reason(path: Path, version: str) -> None:
    envelope = ledger.read_envelope(path)
    metadata, rows = parquet.read(path.read_bytes())
    for cells in rows:
        cells.pop("model_reason")
    columns = [column for column in file_columns(VisualAttemptRow) if column.name != "model_reason"]
    path.write_bytes(parquet.render(
        columns, rows, compression=envelope.compression, envelope=metadata | {
            b"schema_version": version.encode(),
            b"content_sha256": sha256(json_lines.rows_bytes(rows)).hexdigest().encode(),
        },
    ))


def test_shipped_policy_retains_full_rows_then_deletes_without_an_aggregate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    row = VisualAttemptRow(
        version=VisualAttemptRow.schema_version(),
        date="2026-08-21", run_id="2026-08-21-1", item_id="energy-01",
        decision=PlanDecision.NONE, none_reason=NoneReason.MODEL_DECLINED,
        model_reason="The figures do not explain the trend.",
        state=VisualState.ABSENT, visual_id="a" * 64,
    )
    legacy = VisualAttemptRow(
        version="2026-10-29", date="2026-08-20", run_id="2026-08-20-1", item_id="energy-02",
        decision=PlanDecision.NONE, none_reason=NoneReason.NOT_REACHABLE,
        state=VisualState.ABSENT, visual_id="b" * 64,
    )
    (raw,) = ledger.persist(
        state, [row], ledger=LEDGER, covers=row.date,
        identity=writer_identity(row.run_id),
    )
    (old_raw,) = ledger.persist(
        state, [legacy], ledger=LEDGER, covers=legacy.date,
        identity=writer_identity(legacy.run_id),
    )
    _write_an_old_file_without_the_reason(old_raw, legacy.version)
    assert ledger.load([old_raw], model=VisualAttemptRow) == [legacy]
    first = run_task(TASK, tmp_path, today=date(2026, 8, 24))
    assert not first.dry_run
    daily = ledger.compact_path(state, LEDGER, Period.DAILY, row.date)
    assert ledger.load([daily], model=VisualAttemptRow) == [row]
    assert not raw.exists()
    old_daily = ledger.compact_path(state, LEDGER, Period.DAILY, legacy.date)
    _write_an_old_file_without_the_reason(old_daily, legacy.version)
    assert ledger.load([old_daily], model=VisualAttemptRow) == [legacy]

    # A range covers one month only, independent of production archive growth.
    run_task(TASK, tmp_path, today=date(2026, 10, 17), period_range=("2026-08", "2026-08"),
             max_periods_per_run=40)
    run_task(TASK, tmp_path, today=date(2026, 10, 18), period_range=("2026-08", "2026-08"),
             max_periods_per_run=40)
    monthly = ledger.compact_path(state, LEDGER, Period.MONTHLY, "2026-08")
    assert ledger.load([monthly], model=VisualAttemptRow) == [legacy, row]
    assert not daily.exists()
    run_task(TASK, tmp_path, today=date(2027, 11, 16), period_range=("2026-08", "2026-08"),
             max_periods_per_run=40)
    assert monthly.exists(), "14 absorbed months are retained before the keep line moves"
    run_task(TASK, tmp_path, today=date(2027, 12, 16), period_range=("2026-08", "2026-08"),
             max_periods_per_run=40)
    assert not monthly.exists()
    assert ledger.load_days(state, LEDGER, [row.date], model=VisualAttemptRow) == []
    index = CompactIndex.read(ledger.compact_index_path(state, LEDGER, Period.MONTHLY))
    assert not any(entry.covers == "2026-08" for entry in index.period_entries)
    policy = declared()[TASK]
    assert isinstance(policy, CompactionPolicy)
    assert policy.monthly_window.model_dump() == {"unit": "months", "value": 14}
    assert policy.monthly_keep_days is None
