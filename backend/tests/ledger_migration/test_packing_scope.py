"""Does packing touch only the named months and never skip an older period?"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import pytest
from conftest import SEED_COMMIT

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import schedule
from utilities.ledger_migration import (
    csv_files,
    packing,
    phases,
    refusals,
)
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs

from ._fixtures import (
    EVALS,
    MONTHS,
    OLD,
    RUN,
    compaction_identity,
    config_beside,
    run_migration,
    score_row,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def _counterfactual(day: str) -> CounterfactualScoreRow:
    return CounterfactualScoreRow(
        version=CounterfactualScoreRow.schema_version(),
        date=day,
        run_id=f"{day}-100",
        vertical="technology",
        url_key=hashlib.sha256(day.encode()).hexdigest(),
        taken=False,
        lens_id="",
        lens_bonus=0.0,
        lens_multiplier=1.0,
        score_committed=0.0,
        score_counterfactual=0.0,
    )


def _monthly_history(
    state: Path,
    which: LedgerName,
    model: type[Any],
    months: dict[str, list[tuple[str, Any]]],
    *,
    today: date,
    daily_through: str | None = None,
) -> None:
    """Build real monthly door files and indexes for a bounded compaction fixture."""
    scratch = state.parent / f"{which.value}-raw-source"
    entries: list[CompactEntry] = []
    identity = compaction_identity()
    for month, dated_rows in sorted(months.items()):
        raw = [
            path
            for day, row in dated_rows
            for path in ledger.persist(
                scratch,
                [row],
                ledger=which,
                covers=day,
                identity=writer_identity(RUN, SEED_COMMIT),
            )
        ]
        period = ledger.persist_period(
            state,
            ledger.load_stored(raw, model=model),
            model=model,
            ledger=which,
            period=Period.MONTHLY,
            covers=month,
            identity=identity,
            built_from=len(raw),
        )
        entries.append(
            CompactEntry(covers=month, rows=len(dated_rows), bytes=period.stat().st_size)
        )
    monthly_index = ledger.compact_index_path(state, which, Period.MONTHLY)
    monthly_index.parent.mkdir(parents=True, exist_ok=True)
    monthly_index.write_bytes(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=which,
            period=Period.MONTHLY,
            entries=entries,
        )
        .to_json()
        .encode("ascii")
    )
    latest_month = max(months)
    monthly_mark = ledger.watermark_path(state, which, Period.MONTHLY)
    monthly_mark.parent.mkdir(parents=True, exist_ok=True)
    monthly_mark.write_bytes(
        Watermark(
            version=Watermark.schema_version(),
            ledger=which,
            period=Period.MONTHLY,
            through=latest_month,
            advanced_at="2027-03-20T00:41:00Z",
            run_id=RUN,
        )
        .to_json()
        .encode("ascii")
    )
    daily_index = ledger.compact_index_path(state, which, Period.DAILY)
    daily_index.parent.mkdir(parents=True, exist_ok=True)
    daily_index.write_bytes(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=which,
            period=Period.DAILY,
            entries=[],
        )
        .to_json()
        .encode("ascii")
    )
    through = (
        daily_through
        or schedule.newest_eligible(
            now=datetime.combine(today, time.min, tzinfo=UTC), after_days=1
        ).isoformat()
    )
    daily_mark = ledger.watermark_path(state, which, Period.DAILY)
    daily_mark.parent.mkdir(parents=True, exist_ok=True)
    daily_mark.write_bytes(
        Watermark(
            version=Watermark.schema_version(),
            ledger=which,
            period=Period.DAILY,
            through=through,
            advanced_at="2027-03-20T00:41:00Z",
            run_id=RUN,
        )
        .to_json()
        .encode("ascii")
    )


def test_finite_monthly_window_reports_without_losing_migrated_rows(tmp_path: Path) -> None:
    state = tmp_path / "state"
    which = LedgerName.COUNTERFACTUAL_SCORES
    day = "2026-08-15"
    month = day[:7]
    today = date(2026, 10, 20)
    row = _counterfactual(day)
    _monthly_history(
        state,
        which,
        CounterfactualScoreRow,
        {month: [(day, row)]},
        today=today,
        daily_through="2026-08-31",
    )

    config_dir = config_beside(state)
    ((_, moved),) = phases.migrate_roots(
        MigrationInputs(
            state_dirs=[state],
            which=[which],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=today,
            config_dir=config_dir,
            months=[month],
        )
    )

    month_file = ledger.compact_file(state, which, Period.MONTHLY, month)
    assert month_file is not None and month_file.exists()
    assert ledger.load_days(state, which, [day], model=CounterfactualScoreRow) == [row]
    assert not any(
        f"/monthly/{month.replace('-', '/')}.parquet" == path for path in moved.compaction_deleted
    )


def test_migration_packs_a_finished_year_for_a_forever_ledger(tmp_path: Path) -> None:
    state = tmp_path / "state"
    days = [f"{year}-{month:02d}-15" for year in (2026, 2027) for month in range(1, 13)] + [
        "2028-01-15"
    ]
    expected = {day: score_row(day, number) for number, day in enumerate(days)}
    months = {day[:7]: [(day, expected[day])] for day in days}
    _monthly_history(state, EVALS, EvalRow, months, today=date(2028, 4, 4))
    config_dir = config_beside(state)
    declaration = config_dir / "gardener" / f"compact-{EVALS.value}.json"
    policy = json.loads(declaration.read_text(encoding="utf-8"))
    declaration.write_text(
        json.dumps(policy | {"max_periods_per_run": 1}, indent=2) + "\n",
        encoding="ascii",
        newline="",
    )

    ((_, moved),) = phases.migrate_roots(
        MigrationInputs(
            state_dirs=[state],
            which=[EVALS],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=date(2028, 4, 4),
            config_dir=config_dir,
            months=tuple(months),
        )
    )

    for year in ("2026", "2027"):
        packed = ledger.compact_file(state, EVALS, Period.YEARLY, year)
        assert packed is not None
    assert [ledger.load_days(state, EVALS, [day], model=EvalRow)[0] for day in days] == [
        expected[day] for day in days
    ]
    packed_years = sorted(
        path.rsplit("/", 1)[-1].removesuffix(".parquet")
        for path in moved.compaction_written
        if "/yearly/" in path and path.endswith(".parquet")
    )
    assert packed_years == ["2026", "2027"]


def test_scoped_packing_keeps_an_unnamed_indexed_month(tmp_path: Path) -> None:
    state = tmp_path / "state"
    old_day = "2026-08-15"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {"2026-08": [(old_day, score_row(old_day, 1))]},
        today=date(2026, 11, 20),
        daily_through="2026-08-31",
    )
    old_file = ledger.compact_file(state, EVALS, Period.MONTHLY, "2026-08")
    assert old_file is not None
    before = old_file.read_bytes()
    write_csv(state, EVALS, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [score_row(OLD, 2).csv_row()])

    run_migration(state, EVALS, today=date(2026, 11, 20))

    assert old_file.read_bytes() == before
    assert ledger.compact_file(state, EVALS, Period.MONTHLY, MONTHS[0]) is not None
    assert len(ledger.load_days(state, EVALS, [OLD], model=EvalRow)) == 1


def test_named_months_cannot_skip_the_daily_watermark_gap(tmp_path: Path) -> None:
    state = tmp_path / "state"
    old_day = "2026-08-15"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {"2026-08": [(old_day, score_row(old_day, 1))]},
        today=date(2026, 12, 20),
        daily_through="2026-08-31",
    )
    day = "2026-10-01"
    write_csv(state, EVALS, day, writer_file_name(day, 1, ServerJob.WORK), [score_row(day, 2).csv_row()])

    with pytest.raises(refusals.NotProvenError, match="named months omit 2026-09"):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=[EVALS],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=date(2026, 12, 20),
                config_dir=config_beside(state),
                months=["2026-10"],
            )
        )

    assert len(csv_files.left(state, [EVALS], months=["2026-10"])) == 1


def test_scoped_packing_cannot_skip_an_unabsorbed_month(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {"2026-08": [("2026-08-15", score_row("2026-08-15", 1))]},
        today=date(2026, 12, 20),
        daily_through="2026-09-30",
    )
    day = "2026-09-15"
    raw = ledger.persist(
        tmp_path / "source",
        [score_row(day, 2)],
        ledger=EVALS,
        covers=day,
        identity=writer_identity(RUN, SEED_COMMIT),
    )
    daily = ledger.persist_period(
        state,
        ledger.load_stored(raw, model=EvalRow),
        model=EvalRow,
        ledger=EVALS,
        period=Period.DAILY,
        covers=day,
        identity=compaction_identity(),
        built_from=len(raw),
    )
    ledger.compact_index_path(state, EVALS, Period.DAILY).write_bytes(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=EVALS,
            period=Period.DAILY,
            entries=[CompactEntry(covers=day, rows=1, bytes=daily.stat().st_size)],
        )
        .to_json()
        .encode("ascii")
    )
    before = daily.read_bytes()
    selected = "2026-10-01"
    write_csv(
        state,
        EVALS,
        selected,
        writer_file_name(selected, 1, ServerJob.WORK),
        [score_row(selected, 3).csv_row()],
    )

    with pytest.raises(refusals.NotProvenError, match="compaction refused"):
        phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=[EVALS],
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=date(2026, 12, 20),
                config_dir=config_beside(state),
                months=["2026-10"],
            )
        )

    assert daily.read_bytes() == before
    assert Watermark.read(ledger.watermark_path(state, EVALS, Period.MONTHLY)).through == "2026-08"
    assert len(csv_files.left(state, [EVALS], months=["2026-10"])) == 1


def test_scoped_packing_cannot_skip_an_unabsorbed_year(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {
            "2025-08": [("2025-08-15", score_row("2025-08-15", 1))],
            "2026-12": [("2026-12-15", score_row("2026-12-15", 2))],
        },
        today=date(2028, 4, 4),
        daily_through="2026-12-31",
    )
    old_file = ledger.compact_file(state, EVALS, Period.MONTHLY, "2025-08")
    assert old_file is not None
    before = old_file.read_bytes()
    months = tuple(f"2026-{number:02d}" for number in range(1, 13))
    policy = packing.declared([EVALS], config_beside(state))[EVALS]

    with pytest.raises(refusals.NotProvenError, match="compaction refused"):
        packing.pack(
            state,
            EVALS,
            writer_identity(RUN, SEED_COMMIT),
            policy=policy,
            today=date(2028, 4, 4),
            months=months,
        )

    assert old_file.read_bytes() == before
    assert not ledger.watermark_path(state, EVALS, Period.YEARLY).exists()
