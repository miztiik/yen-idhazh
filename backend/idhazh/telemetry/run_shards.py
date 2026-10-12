"""File the manifest's narrow count record through the normal ledger door."""

import json
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_shards import RunShards


def rows_of(manifest: RunManifest) -> list[RunShards]:
    """Match plannedShards: last numeric record per run, not last null."""
    return _last_numeric(
        RunShards(
            version=RunShards.schema_version(), date=manifest.date,
            run_id=run.run_id, shards=run.shards,
        )
        for run in manifest.runs
    )


def _last_numeric(rows: Iterable[RunShards]) -> list[RunShards]:
    found: dict[str, RunShards] = {}
    for row in rows:
        if row.run_id not in found or row.shards is not None:
            found[row.run_id] = row
    return list(found.values())


def record(state: Path, manifest: RunManifest, *, identity: WriterIdentity) -> int:
    return _persist(state, rows_of(manifest), manifest.date, identity)


def _persist(state: Path, rows: list[RunShards], on: str, identity: WriterIdentity) -> int:
    files = [
        [
            row for row in ledger.load_stored([held.path], model=RunShards)
            if row.identity.covers == on
        ]
        for held in ledger.find_holding_files(state, LedgerName.RUN_SHARDS, [on])
    ]
    current = {
        held.row.run_id: held.row.shards
        for held in ledger.settle_rows(files, ledger.door_key(LedgerName.RUN_SHARDS))
    }
    changed = [
        row for row in rows
        if row.run_id not in current
        or (row.shards is not None and row.shards != current[row.run_id])
    ]
    filed = ledger.persist(
        state, changed, ledger=LedgerName.RUN_SHARDS, covers=on, identity=identity
    )
    return len(changed) if filed else 0


def historical_rows(path: Path, on: str) -> list[RunShards]:
    """Read count cells without rejecting legacy duplicate whole-manifest records."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["date"] != on:
        raise ValueError(f"{path} records {payload['date']}, not its named UTC day {on}")
    return _last_numeric(
        RunShards(
            version=RunShards.schema_version(), date=on,
            run_id=run["run_id"], shards=run.get("shards"),
        )
        for run in payload["runs"]
    )


def backfill(
    digest: Path, state: Path, *, first: str, through: str, identity: WriterIdentity
) -> int:
    """Read one named UTC day's run.json at a time, within explicit inclusive bounds."""
    start, end = date.fromisoformat(first), date.fromisoformat(through)
    if start > end:
        raise ValueError("first must not follow through")
    filed = 0
    day = start
    while day <= end:
        path = digest / f"{day.year:04d}" / f"{day.month:02d}" / f"{day.day:02d}" / "run.json"
        if path.is_file():
            on = day.isoformat()
            filed += _persist(state, historical_rows(path, on), on, identity)
        day += timedelta(days=1)
    return filed
