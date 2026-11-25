"""Do ordinary reader, compaction and expiry preserve the TypeScript writer's task identity?"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import ValidationError
from support.paths import CONFIG_DIR, REPO_ROOT

from idhazh import config, ledger
from idhazh.contracts import AppConfig
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgersConfig
from idhazh.contracts.task_performance import TaskPerformanceRow
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.period_inputs import paths_for_task
from idhazh.gardener.tasks import compaction
from idhazh.ledger import parquet
from idhazh.ledger.persist import file_columns

pytestmark = pytest.mark.contract

LEDGER: Final = LedgerName.TASK_PERFORMANCE
DAY: Final = "2026-12-31"


def test_a_task_cannot_record_nonfinite_elapsed_time() -> None:
    with pytest.raises(ValidationError, match="finite number"):
        TaskPerformanceRow.model_validate({
            "version": TaskPerformanceRow.schema_version(), "date": DAY,
            "run_id": f"{DAY}-8", "pipeline_name": "digest", "task_name": "work", "shard": 2,
            "task_kind": "workflow-task", "outcome": "success", "elapsed_ms": float("inf"),
        })


def write_raw(state: Path, attempt: int, *rows: dict[str, Any]) -> list[Path]:
    registry = LedgersConfig.from_json((CONFIG_DIR / "ledgers.json").read_text(encoding="utf-8"))
    family = next(family for family in registry.families if family.name == LEDGER.value)
    (held,) = family.ledgers
    bun = shutil.which("bun")
    assert bun, "Install Bun to exercise the shared TypeScript Parquet writer"
    settings = AppConfig.from_json((CONFIG_DIR / "idhazh.json").read_text(encoding="utf-8")).ledger
    completed = subprocess.run(
        [bun, "run", "test/write-task-performance.ts", str(state)],
        cwd=REPO_ROOT / "packages" / "ledger-file-writer",
        input=json.dumps({
            "attempt": attempt,
            "rows": rows,
            "registryEntry": {
                "name": held.name, "grain": held.grain, "prefix": held.prefix,
                "family": family.name, "lifecycle_status": family.lifecycle_status,
            },
            "ledgerSettings": settings.model_dump(
                mode="json", include={"format", "compression_raw", "compression_compact"}
            ),
        }),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return [state.joinpath(*path.split("/")) for path in json.loads(completed.stdout)]


def test_raw_tasks_survive_a_partial_retry_after_month_closure_and_expire(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    task = config.compaction_task(LEDGER)
    settings = config.load_gardener()
    policy = settings.tasks[task]
    assert isinstance(policy, CompactionPolicy)
    # Retain the live age rules; catch up the intervening empty days in fewer passes.
    policy = policy.model_copy(update={"max_periods_per_run": 64})

    def pack(today: date, *, month: str | None = None) -> None:
        period_range = (month, month) if month is not None else None
        outcome = compaction.run(TaskContext(
            state_dir=state, repo_root=tmp_path, today=today, policy=policy,
            run_id=f"{today.isoformat()}-9", attempt=1, job=ServerJob.RUN_TASKS, shard=0,
            git_sha="b" * 40,
            owned_folders=tuple(name for name in policy.owns if (tmp_path / name).is_dir()),
            listing=FileListing.from_disk(
                tmp_path, policy.owns, paths=paths_for_task(
                    tmp_path, task, policy, period_range, today=today,
                ),
            ),
            first_ledger_year=settings.config.first_ledger_year,
            operator_range=period_range, period_range=period_range,
        ))
        assert outcome.fault is None, outcome

    common = {
        "version": TaskPerformanceRow.schema_version(), "date": DAY,
        "run_id": f"{DAY}-8", "pipeline_name": "digest", "shard": 2, "outcome": "success",
    }
    phase = common | {
        "task_kind": "workflow-task", "task_name": "work", "elapsed_ms": 10.5, "model_calls": 0,
        "started_at": f"{DAY}T23:59:59.990Z", "finished_at": "2027-01-01T00:00:00.001Z",
        "worker_rss_peak_kib": 2048,
    }
    serving = common | {
        "task_kind": "model-serving", "task_name": "serve-summary", "subject_id": "summary",
        "server_prompt_tokens": 0,
    }
    phase_path, serving_path = write_raw(state, 1, phase, serving)
    expected_schema = parquet.schema_of(file_columns(TaskPerformanceRow))
    for path in (phase_path, serving_path):
        assert parquet.read_footer_schema(path)[1].equals(expected_schema)
        envelope = ledger.read_envelope(path)
        assert envelope.writer == "idhazh_typescript.ledger.parquet"
        assert envelope.row_schema_version == TaskPerformanceRow.schema_version()
    initial = ledger.load_stored([phase_path, serving_path], model=TaskPerformanceRow)
    assert [held.row for held in initial] == [
        TaskPerformanceRow.model_validate(phase), TaskPerformanceRow.model_validate(serving),
    ]
    assert initial[0].identity.unit_id != initial[1].identity.unit_id
    assert len(ledger.load_days(state, LEDGER, [DAY], model=TaskPerformanceRow)) == 2

    pack(date(2027, 1, 2))
    assert ledger.compact_file(state, LEDGER, Period.DAILY, DAY) is not None
    assert not phase_path.exists() and not serving_path.exists()
    pack(date(2027, 2, 16))
    month = ledger.compact_file(state, LEDGER, Period.MONTHLY, "2026-12")
    assert month is not None
    assert ledger.compact_file(state, LEDGER, Period.DAILY, DAY) is None

    retried = phase | {"elapsed_ms": 22.25, "outcome": "error", "model_calls": None}
    (late,) = write_raw(state, 2, retried)
    assert ledger.load_stored([late], model=TaskPerformanceRow)[0].identity.unit_id == initial[0].identity.unit_id
    # The month closed after the scheduled rerun window, so name the historical period.
    pack(date(2027, 2, 17), month="2026-12")
    assert not late.exists()
    packed = ledger.load_stored([month], model=TaskPerformanceRow)
    assert len(packed) == 2
    assert {held.row.task_name: held.identity.attempt for held in packed} == {"work": 2, "serve-summary": 1}
    current = ledger.load_days(state, LEDGER, [DAY], model=TaskPerformanceRow)
    assert len(current) == 2
    assert {row.task_name: row for row in current} == {
        "work": TaskPerformanceRow.model_validate(retried),
        "serve-summary": TaskPerformanceRow.model_validate(serving),
    }

    pack(date(2027, 4, 5))
    pack(date(2027, 4, 6))
    year = ledger.compact_file(state, LEDGER, Period.YEARLY, "2026")
    assert year is not None and year.is_file() and not month.exists()
    pack(date(2029, 12, 31))
    assert year.is_file()
    pack(date(2030, 1, 1))
    assert not year.exists()
    index = CompactIndex.read(ledger.compact_index_path(state, LEDGER, Period.YEARLY))
    assert index.expired_through == "2026"
