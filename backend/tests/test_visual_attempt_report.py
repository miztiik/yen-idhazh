"""Do raw and compact attempt records produce the same complete, correctly counted Parquet report?"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet
import pytest
from support.ledger import writer_identity
from support.paths import REPO_ROOT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.ledger import keys, parquet, raw_files
from idhazh.ledger.persist import file_columns, read_envelope
from utilities.visual_attempt_report import main

pytestmark = [pytest.mark.visual, pytest.mark.contract]

DAYS = ("2026-08-21", "2026-08-22")
LEDGER = LedgerName.VISUAL_DESIGN_ATTEMPTS
PERIODS = (Period.DAILY, Period.MONTHLY, Period.YEARLY)
EXPECTED_COLUMNS = (
    "date", "potential_primary", "state", "rejection_reason", "planned_type",
    "rendered_type", "attempts",
)


def attempt(day: str, number: int, **changes: object) -> VisualAttemptRow:
    return VisualAttemptRow.model_validate({
        "version": VisualAttemptRow.schema_version(),
        "date": day,
        "run_id": f"{day}-1",
        "item_id": f"item-{number:02}",
        "visual_id": f"{number:064x}",
        "decision": "visual",
        "potential_primary": "chartable",
        "state": "rendered",
        "planned_type": "bar",
        "rendered_type": "bar",
        "downgrade_depth": 0,
        "marks": 4,
    } | changes)


def filed(
    state: Path, row: VisualAttemptRow, *, attempt_number: int = 1, part: str | None = None,
) -> Path:
    (path,) = ledger.persist(
        state, [row], ledger=LEDGER, covers=row.date, fmt=Format.PARQUET,
        identity=writer_identity(
            row.run_id, attempt=attempt_number, job=ServerJob.WORK,
            producer=f"tests.visual_attempt_report:{part or row.visual_id or row.item_id}",
        ),
    )
    return path


def seeded(state: Path) -> None:
    first = attempt(DAYS[0], 1, item_id="shared-item-01")
    filed(state, VisualAttemptRow.model_validate(first.model_dump() | {
        "state": "render_failed", "rendered_type": None, "marks": None,
    }))
    filed(state, first, attempt_number=2)
    filed(state, first, part="duplicate-storage")
    for row in (
        attempt(DAYS[0], 2, item_id="shared-item-01"),
        attempt(
            DAYS[0], 3, rejection_reason="enough_data", planned_type="comparison",
            downgrade_depth=1,
        ),
        attempt(
            DAYS[0], 4, state="absent", rejection_reason="pie_exhaustive",
            planned_type="pie", rendered_type=None, marks=None,
            none_reason="validation_failed",
        ),
        attempt(
            DAYS[0], 5, decision="none", potential_primary=None, state="absent",
            planned_type=None, rendered_type=None, marks=None, downgrade_depth=None,
            none_reason="model_declined",
        ),
        attempt(DAYS[0], 6, state="render_failed", rendered_type=None, marks=None),
        attempt(
            DAYS[1], 7, version="2026-10-27T11:32", visual_id=None,
            potential_primary=None, planned_type=None, rendered_type=None,
            downgrade_depth=None,
        ),
        attempt(
            DAYS[1], 8, potential_primary="narrative",
            planned_type="whowhat", rendered_type="whowhat",
        ),
    ):
        filed(state, row)

    outside = filed(state, attempt("2026-08-23", 9))
    outside.write_bytes(b"not a parquet file")


def indexed(state: Path, period: Period, entries: list[CompactEntry]) -> Path:
    index = CompactIndex(
        version=CompactIndex.schema_version(), ledger=LEDGER, period=period, entries=entries,
    )
    path = ledger.compact_index_path(state, LEDGER, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(index.to_json().encode("ascii"))
    return path


def packed(state: Path, through: Period) -> dict[tuple[Period, str], Path]:
    raw = ledger.list_raw_files(state, LEDGER, days=DAYS)
    rows = raw_files.settle_registered_rows(
        [ledger.load_stored([file.path], model=VisualAttemptRow) for file in raw],
        keys.door_key(LEDGER), ledger=LEDGER,
    )
    paths: dict[tuple[Period, str], Path] = {}
    for position, period in enumerate(PERIODS):
        entries: list[CompactEntry] = []
        if position <= PERIODS.index(through):
            width = {Period.DAILY: 10, Period.MONTHLY: 7, Period.YEARLY: 4}[period]
            for covers in sorted({row.day[:width] for row in rows}):
                selected = [row for row in rows if row.day[:width] == covers]
                path = ledger.persist_period(
                    state, selected, model=VisualAttemptRow, ledger=LEDGER,
                    covers=covers, period=period, built_from=len(raw), fmt=Format.PARQUET,
                    identity=writer_identity(
                        f"{DAYS[1]}-2", job=ServerJob.RUN_TASKS,
                        producer="tests.pack_visual_attempts",
                    ),
                )
                paths[period, covers] = path
                entries.append(CompactEntry(
                    covers=covers, rows=len(selected), bytes=path.stat().st_size,
                    file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                ))
        indexed(state, period, entries)
    return paths


def snapshot(state: Path) -> dict[str, bytes]:
    return {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in state.rglob("*") if path.is_file()
    }


def command(state: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "backend")
    return subprocess.run(
        [sys.executable, "-m", "utilities.visual_attempt_report", "--state-dir", str(state),
         *arguments],
        cwd=state.parent, env=env, stdin=subprocess.DEVNULL, capture_output=True, check=False,
    )


def report(state: Path, days: tuple[str, ...] = DAYS) -> subprocess.CompletedProcess[bytes]:
    arguments = [value for day in days for value in ("--date", day)]
    return command(state, arguments)


@pytest.mark.parametrize("period", PERIODS)
def test_real_command_matches_raw_and_compact_counts_without_changing_inputs(
    tmp_path: Path, period: Period,
) -> None:
    raw, compact = tmp_path / "raw-state", tmp_path / "compact-state"
    seeded(raw)
    seeded(compact)
    packed(compact, period)
    before = {state: snapshot(state) for state in (raw, compact)}

    raw_result = report(raw, (DAYS[1], DAYS[0], DAYS[0]))
    compact_result = report(compact)

    assert raw_result.returncode == 0, raw_result.stderr.decode()
    assert compact_result.returncode == 0, compact_result.stderr.decode()
    assert raw_result.stdout == compact_result.stdout
    with (
        pyarrow.BufferReader(raw_result.stdout) as source,
        pyarrow.parquet.ParquetFile(source, pre_buffer=False) as opened,
    ):
        table = opened.read(use_threads=False)
    assert table.column_names == list(EXPECTED_COLUMNS)
    assert [field.type for field in table.schema] == [
        *([pyarrow.string()] * (len(EXPECTED_COLUMNS) - 1)), pyarrow.int64(),
    ]
    assert [field.nullable for field in table.schema] == [
        False, True, False, True, True, True, False,
    ]
    expected = (
        (DAYS[0], None, "absent", None, None, None, 1),
        (DAYS[0], "chartable", "absent", "pie_exhaustive", "pie", None, 1),
        (DAYS[0], "chartable", "render_failed", None, "bar", None, 1),
        (DAYS[0], "chartable", "rendered", None, "bar", "bar", 2),
        (DAYS[0], "chartable", "rendered", "enough_data", "comparison", "bar", 1),
        (DAYS[1], None, "rendered", None, None, None, 1),
        (DAYS[1], "narrative", "rendered", None, "whowhat", "whowhat", 1),
    )
    assert table.to_pylist() == [
        dict(zip(EXPECTED_COLUMNS, row, strict=True)) for row in expected
    ]
    assert {state: snapshot(state) for state in (raw, compact)} == before


def test_missing_dates_are_named_once_without_invented_zero_groups(tmp_path: Path) -> None:
    state = tmp_path / "state"
    filed(state, attempt(DAYS[0], 1))
    before = snapshot(state)

    result = report(state, (DAYS[1], DAYS[0], DAYS[1]))

    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr.count(DAYS[1].encode()) == 1
    with pyarrow.BufferReader(result.stdout) as source:
        table = pyarrow.parquet.read_table(source, use_threads=False)
    assert table["date"].to_pylist() == [DAYS[0]]
    assert table["attempts"].to_pylist() == [1]
    assert snapshot(state) == before


def test_no_records_refuses_parquet_and_names_each_requested_date(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()

    result = report(state, (DAYS[1], DAYS[0], DAYS[1]))

    assert result.returncode == 1
    assert result.stdout == b""
    assert b"no records" in result.stderr
    for day in DAYS:
        assert result.stderr.count(day.encode()) == 1
    assert snapshot(state) == {}


@pytest.mark.parametrize(
    "fault",
    ["raw-corrupt", "raw-invalid-row", "bad-index", "missing-index", "missing-file", "lost-day",
     "lost-month"],
)
def test_incomplete_read_refuses_all_output_even_with_readable_rows(
    tmp_path: Path, fault: str,
) -> None:
    state = tmp_path / "state"
    filed(state, attempt(DAYS[0], 1))
    second = filed(state, attempt(DAYS[1], 2)) if fault != "lost-month" else None
    if fault == "raw-corrupt":
        assert second is not None
        second.write_bytes(b"not a parquet file")
    elif fault == "raw-invalid-row":
        assert second is not None
        envelope, rows = parquet.read(second.read_bytes())
        compression = read_envelope(second).compression
        rows[0]["state"] = "not-a-state"
        second.write_bytes(parquet.render(
            file_columns(VisualAttemptRow), rows, envelope=envelope, compression=compression,
        ))
    else:
        paths = packed(state, Period.MONTHLY if fault == "lost-month" else Period.DAILY)
        if fault == "bad-index":
            ledger.compact_index_path(state, LEDGER, Period.YEARLY).write_bytes(b"{broken")
        elif fault == "missing-index":
            ledger.compact_index_path(state, LEDGER, Period.YEARLY).unlink()
        elif fault == "missing-file":
            paths[Period.DAILY, DAYS[1]].unlink()
        elif fault == "lost-day":
            indexed(state, Period.DAILY, [
                CompactEntry(
                    covers=DAYS[0], rows=1, bytes=paths[Period.DAILY, DAYS[0]].stat().st_size,
                ),
                CompactEntry(covers=DAYS[1], rows=0, bytes=0, state=EntryState.LOST),
            ])
        elif fault == "lost-month":
            path = paths[Period.MONTHLY, DAYS[0][:7]]
            indexed(state, Period.MONTHLY, [
                CompactEntry(
                    covers=DAYS[0][:7], rows=1, bytes=path.stat().st_size, lost_days=[DAYS[1]],
                ),
            ])
    before = snapshot(state)

    result = report(state)

    assert result.returncode == 1
    assert result.stdout == b""
    assert b"incomplete" in result.stderr
    assert snapshot(state) == before


@pytest.mark.parametrize("has_rows", [True, False])
def test_required_missing_date_diagnostics_do_not_depend_on_logging_level(
    tmp_path: Path, capfdbinary: pytest.CaptureFixture[bytes], has_rows: bool,
) -> None:
    state = tmp_path / "state"
    state.mkdir()
    if has_rows:
        filed(state, attempt(DAYS[0], 1))
    before = snapshot(state)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        status = main([
            "--state-dir", str(state), "--date", DAYS[0], "--date", DAYS[1],
        ])
    finally:
        logging.disable(previous)
    stdout, stderr = capfdbinary.readouterr()

    assert status == (0 if has_rows else 1)
    assert bool(stdout) is has_rows
    assert stderr.count(DAYS[1].encode()) == 1
    assert snapshot(state) == before


@pytest.mark.parametrize(
    "arguments",
    [[], ["--date", "20260821"], ["--date", "2026-02-30"],
     ["--date", "2026-08-21T00:00:00Z"], ["--date", "../2026-08-21"]],
)
def test_date_arguments_require_explicit_real_utc_days(
    tmp_path: Path, arguments: list[str],
) -> None:
    result = command(tmp_path / "state", arguments)

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"--date" in result.stderr
    assert not (tmp_path / "state").exists()
