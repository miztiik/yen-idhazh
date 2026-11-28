"""Does a host pack keep original measurements before it takes the inputs?"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Final

import pytest
from support.paths import CONFIG_DIR, read_text

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import (
    HOST_FINGERPRINT_PRODUCER,
    Compression,
    FileEnvelope,
    Period,
    RowIdentity,
    Tier,
    WriterIdentity,
)
from idhazh.contracts.host_fingerprint import (
    HOST_FINGERPRINT_VERSION,
    HOST_HARDWARE_VERSION,
    HOST_MODEL_FIELDS,
    LEGACY_CPU_FIELDS,
    RETIRED_HOST_CLOCK,
    HostFingerprintRow,
    HostHardwareRow,
    LegacyHostFingerprintRow,
)
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import _daily_period, _monthly_period, _reopened_month, _yearly_period
from idhazh.gardener.tasks._compact_tree import CompactTree
from idhazh.ledger import json_lines, parquet, published_columns
from idhazh.ledger.arrow_schema import Column, ColumnType
from idhazh.ledger.persist import file_columns

HOST: Final = LedgerName.HOST_FINGERPRINT
DAY: Final = "2026-11-26"
NEXT_MONTH: Final = "2026-12-01"
SHA: Final = "2" * 40
PACKER = WriterIdentity(
    run_id="2027-04-07-1", attempt=1, job="run-tasks", shard=0,
    producer="gardener.compaction", git_sha=SHA,
)


def _policy() -> CompactionPolicy:
    return CompactionPolicy.model_validate_json(
        read_text(CONFIG_DIR / "gardener" / "compact-host-fingerprint.json")
    )


def _writer(
    day: str, *, job: str | None, pipeline: str | None = None, task: str | None = None,
    attempt: int = 1,
) -> WriterIdentity:
    return WriterIdentity(
        run_id=f"{day}-1", attempt=attempt, job=job, shard=0, pipeline_name=pipeline,
        task_name=task, producer=HOST_FINGERPRINT_PRODUCER, git_sha=SHA,
    )


def _new(
    state: Path, day: str, *, pipeline: str = "digest", task: str = "work",
    job: str | None = "work", attempt: int = 1,
) -> Path:
    identity = _writer(day, job=job, pipeline=pipeline, task=task, attempt=attempt)
    row = HostHardwareRow(
        version=HOST_HARDWARE_VERSION, date=day, run_id=identity.run_id, job=job,
        pipeline_name=pipeline, task_name=task, shard=0, measured_at=f"{day}T00:03:00Z",
        cpu_logical_processors=4, machine_memory_total_mib=16383.75,
    )
    (path,) = ledger.persist(state, [row], ledger=HOST, covers=day, identity=identity)
    return path


def _retained_model(state: Path, *, generic: bool = False) -> Path:
    identity = _writer(
        DAY, job=None if generic else "work",
        pipeline="digest" if generic else None, task="work" if generic else None,
    )
    row = HostFingerprintRow(
        version="2026-10-26", date=DAY, run_id=identity.run_id, job=identity.job, shard=0,
        pipeline_name=identity.pipeline_name, task_name=identity.task_name,
        measured_at=f"{DAY}T00:01:00Z", model_load_ms=123.5,
        server_prompt_tokens=321, server_prompt_seconds=1.25,
    )
    (path,) = ledger.persist(state, [row], ledger=HOST, covers=DAY, identity=identity)
    return path


def _archived(state: Path) -> Path:
    identity = _writer(DAY, job="assemble")
    row = LegacyHostFingerprintRow(
        version="2026-09-20", date=DAY, run_id=identity.run_id, job=ServerJob.ASSEMBLE, shard=0,
        measured_at=f"{DAY}T00:02:00Z", cores=2, threads=4, mhz_at_probe=2750.0,
        mhz_max=3100.0,
    )
    unit = ledger.unit_id(
        ledger=HOST, covers=DAY, run_id=identity.run_id, job=identity.job, shard=0,
        producer=identity.producer,
    )
    written_at_ms = 1795651320000  # The archived sample's opening UTC instant.
    file_id = ledger.file_id(unit=unit, attempt=1, written_at_ms=written_at_ms)
    stamped = RowIdentity(
        ledger=HOST, covers=DAY, run_id=identity.run_id, attempt=1, job="assemble",
        shard=0, unit_id=str(unit),
    )
    cells = stamped.model_dump(mode="json") | row.model_dump(mode="json")
    envelope = FileEnvelope(
        version=FileEnvelope.schema_version(),
        row_schema_version=row.version, tier=Tier.RAW, ledger=HOST, covers=DAY,
        written_at_ms=written_at_ms, identity=identity, unit_id=unit, file_id=file_id,
        content_sha256=hashlib.sha256(json_lines.rows_bytes([cells])).hexdigest(),
        writer="idhazh.ledger.parquet", writer_version=parquet.engine_version(),
        compression=Compression.NONE,
    )
    path = ledger.raw_path(state, HOST, DAY, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(parquet.render(
        file_columns(LegacyHostFingerprintRow), [cells], envelope=envelope.as_metadata(),
        compression=envelope.compression,
    ))
    return path


def _tree(
    state: Path, paths: list[Path], *,
    daily: dict[str, CompactEntry] | None = None, monthly: dict[str, CompactEntry] | None = None,
) -> CompactTree:
    return CompactTree(
        state_dir=state, ledger=HOST,
        listing=FileListing.from_disk(state.parent, ["state"], paths=paths),
        daily=daily or {}, monthly=monthly or {}, yearly={}, raw_days=[],
    )


def _land(tree: CompactTree, period: Period, covers: str, *, replaces: list[Path]) -> Path:
    tree.finish()
    tree.apply()
    path = ledger.compact_path(tree.state_dir, HOST, period, covers)
    assert path.is_file()
    assert all(not item.exists() for item in replaces)
    return path


def _rows(path: Path) -> list[dict[str, Any]]:
    _, rows = parquet.read(path.read_bytes())
    return rows


def _facts(paths: list[Path]) -> set[bytes]:
    return {
        json_lines.rows_bytes([{key: value for key, value in row.items() if value is not None}])
        for path in paths for row in _rows(path)
    }


@pytest.mark.parametrize("historical", [False, True], ids=["hardware-only", "mixed"])
def test_host_rows_pack_from_raw_through_year_without_changing_their_evidence(
    tmp_path: Path, historical: bool
) -> None:
    state = tmp_path / "state"
    days = {
        DAY: [
            _new(state, DAY),
            _new(state, DAY, pipeline="alternate", job=None),
            _new(state, DAY, task="inspect", job="work"),
        ],
        NEXT_MONTH: [_new(state, NEXT_MONTH)],
    }
    if historical:
        days[DAY].extend([_retained_model(state), _archived(state)])
    facts = {day: _facts(raw) for day, raw in days.items()}
    month_files: dict[str, Path] = {}
    month_entries: dict[str, CompactEntry] = {}
    for day, raw in days.items():
        month = day[:7]
        tree = _tree(state, raw)
        tree.name_days([day])
        assert _daily_period._take(
            tree, _policy(), day, model=HostFingerprintRow, key=ledger.HOST_FINGERPRINT_KEY,
            identity=PACKER,
        ) is None
        daily = _land(tree, Period.DAILY, day, replaces=raw)
        assert _facts([daily]) == facts[day]
        assert len(ledger.load([daily], model=HostFingerprintRow)) == len(raw)
        tree = _tree(state, [daily], daily=tree.daily)
        tree.name_months([month])
        assert _monthly_period._close(tree, month, model=HostFingerprintRow, identity=PACKER) == ()
        monthly = _land(tree, Period.MONTHLY, month, replaces=[daily])
        assert _facts([monthly]) == facts[day]
        month_files[month] = monthly
        month_entries.update(tree.monthly)

    years = _tree(state, list(month_files.values()), monthly=month_entries)
    years.name_years(["2026"])
    assert _yearly_period._pack(years, "2026", identity=PACKER) == ()
    annual = _land(years, Period.YEARLY, "2026", replaces=list(month_files.values()))

    assert _facts([annual]) == facts[DAY] | facts[NEXT_MONTH]
    rows = ledger.load([annual], model=HostFingerprintRow)
    assert len(rows) == sum(map(len, days.values()))
    if historical:
        assert set(_rows(annual)[0]) >= HOST_MODEL_FIELDS | LEGACY_CPU_FIELDS
        models = [row for row in rows if row.model_load_ms is not None]
        assert [(row.model_load_ms, row.server_prompt_tokens, row.server_prompt_seconds)
                for row in models] == [(123.5, 321, 1.25)]
        assert ledger.read_envelope(annual).row_schema_version == HOST_FINGERPRINT_VERSION
    else:
        assert all(not (row.keys() & (HOST_MODEL_FIELDS | LEGACY_CPU_FIELDS)) for row in _rows(annual))
    with parquet.open_bytes(annual.read_bytes()) as opened:
        assert opened.num_row_groups == len(month_files)
    assert published_columns.check(tmp_path, [HOST]) == 0


@pytest.mark.parametrize("tier", [Tier.RAW, Period.DAILY, Period.MONTHLY], ids=["raw", "day", "month"])
def test_unknown_physical_host_column_refuses_the_period_without_removing_its_source(
    tmp_path: Path, tier: Tier | Period,
) -> None:
    state = tmp_path / "state"
    raw = _new(state, DAY)
    model = HostFingerprintRow
    source = ledger.persist_period(
        state, ledger.load_stored([raw], model=model), model=model, ledger=HOST,
        period=tier, covers=DAY if tier is Period.DAILY else DAY[:7], identity=PACKER, built_from=1,
    ) if isinstance(tier, Period) else raw
    metadata, rows = parquet.read(source.read_bytes())
    rows = [{**row, "unknown_cell": None} for row in rows]
    data = parquet.render(
        (*file_columns(HostHardwareRow), Column(name="unknown_cell", type=ColumnType.STRING, nullable=True)),
        rows, envelope={
            **metadata, b"content_sha256": hashlib.sha256(json_lines.rows_bytes(rows)).hexdigest().encode("ascii"),
        }, compression=Compression.NONE,
    )
    source.write_bytes(data)
    month = DAY[:7]
    if tier is Tier.RAW:
        tree = _tree(state, [source])
        tree.name_days([DAY])
        assert _daily_period._take(
            tree, _policy(), DAY, model=model, key=ledger.HOST_FINGERPRINT_KEY,
            identity=PACKER,
        ) is not None
    elif tier is Period.DAILY:
        tree = _tree(state, [source], daily={DAY: CompactEntry(covers=DAY, rows=1, bytes=len(data))})
        tree.name_months([month])
        assert _monthly_period._close(tree, month, model=model, identity=PACKER)
    else:
        tree = _tree(state, [source], monthly={
            month: CompactEntry(covers=month, rows=1, bytes=len(data)),
        })
        tree.name_years(["2026"])
        assert _yearly_period._pack(tree, "2026", identity=PACKER)
    assert tree.changes == []
    assert source.read_bytes() == data


@pytest.mark.parametrize("overlaps", [False, True], ids=["different-task", "supersedes"])
def test_reopened_host_month_never_takes_a_model_reading_without_a_copy(
    tmp_path: Path, overlaps: bool,
) -> None:
    state = tmp_path / "state"
    old = _retained_model(state, generic=True)
    model = HostFingerprintRow
    month = DAY[:7]
    packed = ledger.persist_period(
        state, ledger.load_stored([old], model=model), model=model, ledger=HOST,
        period=Period.MONTHLY, covers=month, identity=PACKER, built_from=1,
    )
    old.unlink()
    new = _new(state, DAY, task="work" if overlaps else "inspect", attempt=2)
    original = {path: path.read_bytes() for path in (new, packed)}
    facts = _facts([new, packed])
    tree = _tree(state, [new, packed], monthly={
        month: CompactEntry(covers=month, rows=1, bytes=len(original[packed])),
    })

    stops = _reopened_month.reopen(
        tree, month, most=_policy().max_raw_files_per_period, model=model,
        key=ledger.HOST_FINGERPRINT_KEY, identity=PACKER,
    )
    if not overlaps:
        assert stops == ()
        assert _facts([_land(tree, Period.MONTHLY, month, replaces=[new])]) == facts
        return
    assert stops
    assert tree.changes == []
    assert {path: path.read_bytes() for path in original} == original


def test_original_retained_parquet_is_checked_before_projection(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    path = _retained_model(state)
    metadata, (cells,) = parquet.read(path.read_bytes())
    columns = (*file_columns(HostFingerprintRow), Column(RETIRED_HOST_CLOCK, ColumnType.INT64, True))
    original = {**cells, RETIRED_HOST_CLOCK: 33}
    metadata[b"schema_version"] = b"2026-10-26"
    metadata[b"content_sha256"] = hashlib.sha256(json_lines.rows_bytes([original])).hexdigest().encode()
    path.write_bytes(parquet.render(
        columns, [original], envelope=metadata, compression=Compression.NONE,
    ))
    (stored,) = ledger.load_stored([path], model=HostFingerprintRow)
    assert (stored.row.model_load_ms, stored.row.server_prompt_tokens) == (123.5, 321)
    tree = _tree(state, [path])
    tree.name_days([DAY])
    assert _daily_period._take(
        tree, _policy(), DAY, model=HostFingerprintRow, key=ledger.HOST_FINGERPRINT_KEY,
        identity=PACKER,
    ) is None
    assert RETIRED_HOST_CLOCK not in (stored.original_host_cells or {})

    # Alter only the cell no reader projects. The original digest must still fail.
    data = parquet.render(
        columns, [{**original, RETIRED_HOST_CLOCK: 34}],
        envelope=metadata, compression=Compression.NONE,
    )
    path.write_bytes(data)

    with pytest.raises(ValueError, match="original host content_sha256 mismatch"):
        ledger.load([path], model=HostFingerprintRow)
    tree = _tree(state, [path])
    tree.name_days([DAY])
    assert _daily_period._take(
        tree, _policy(), DAY, model=HostFingerprintRow, key=ledger.HOST_FINGERPRINT_KEY,
        identity=PACKER,
    ) is not None
    assert tree.changes == []
    assert path.read_bytes() == data
