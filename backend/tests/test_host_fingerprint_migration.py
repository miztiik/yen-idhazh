"""Does a bounded dry-run preserve source bytes and reconcile real generated history?"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Format
from idhazh.contracts.host_migration import HistoryManifest
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    LEGACY_HOST_VERSIONS,
    CandidateFileEnvelope,
    HostWriterIdentity,
    LegacyHostFingerprintRow,
    fingerprint_v1,
    host_file_id,
    host_unit_id,
)
from idhazh.ledger import json_lines, parquet
from idhazh.telemetry.host_history_bundle import dry_run
from idhazh.telemetry.host_history_files import HistoryLimits
from idhazh.telemetry.host_output_verify import host_output_columns

pytestmark = pytest.mark.contract
REPO = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


@pytest.fixture
def workspace() -> Iterator[Path]:
    root = REPO / "backend" / "var" / "d15-tests" / str(uuid.uuid4())
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root)


def specification() -> dict[str, Any]:
    document: object = json.loads(
        (REPO / "tests" / "fixtures" / "host-events" / "history-migration.json").read_bytes()
    )
    if not isinstance(document, dict):
        raise ValueError("history fixture must be a JSON object")
    return document


def manifest_document() -> dict[str, Any]:
    document: object = specification()["manifest"]
    if not isinstance(document, dict):
        raise ValueError("manifest fixture requires a JSON object")
    return document


def add_source(
    root: Path,
    document: dict[str, Any],
    path: str,
    data: bytes,
    kind: str,
    *,
    dependencies: list[str] | None = None,
    covers: str | None = None,
) -> str:
    target = root / Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    document["sources"].append(
        {
            "root": "production",
            "path": path,
            "kind": kind,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "covers": covers,
            "period": "daily" if covers else None,
            "dependencies": dependencies or [],
        }
    )
    return path


def generated_raw(
    root: Path,
    document: dict[str, Any],
    *,
    version: str = "2026-09-20",
    fmt: Format = Format.JSON,
    attempt: int = 1,
    clock_offset: int = 0,
    average: float | None = 2300.0,
    clocks: bool = False,
    shard: int = 0,
    fingerprint: bool = True,
) -> tuple[str, dict[str, Any]]:
    spec = specification()
    identity = HostWriterIdentity(
        run_id=spec["run_id"],
        attempt=attempt,
        job=ServerJob.WORK,
        shard=shard,
        producer="telemetry.silicon",
        git_sha="b" * 40,
    )
    old = LegacyHostFingerprintRow.model_validate(
        {
            "version": version,
            "date": spec["day"],
            "run_id": identity.run_id,
            "job": "work",
            "shard": shard,
            "fingerprint": "0" * 16,
            "cpu_model": "Recorded CPU",
            "measured_at": "2026-09-20T12:00:00Z",
            **spec["dropped"],
            "mhz_at_probe": average,
            **({"job_seconds": 17, "model_load_ms": 8.0} if clocks else {}),
        }
    )
    row = old.model_dump(mode="json")
    row["fingerprint"] = fingerprint_v1(old) if fingerprint else None
    row = {c.name: row[c.name] for c in host_output_columns(version) if c.name in row}
    unit = host_unit_id(covers=spec["day"], identity=identity)
    row.update(ledger="host-fingerprint", covers=spec["day"], attempt=attempt, unit_id=str(unit))
    clock = spec["clock_ms"] + clock_offset
    file_id = host_file_id(unit=unit, attempt=attempt, written_at_ms=clock)
    envelope = CandidateFileEnvelope.model_validate(
        {
            "version": "2026-10-06",
            "row_schema_version": version,
            "tier": "raw",
            "ledger": "host-fingerprint",
            "covers": spec["day"],
            "written_at_ms": clock,
            "identity": identity,
            "unit_id": unit,
            "file_id": file_id,
            "content_sha256": hashlib.sha256(json_lines.rows_bytes([row])).hexdigest(),
            "writer": "idhazh.ledger.json_lines" if fmt is Format.JSON else "idhazh.ledger.parquet",
            "writer_version": json_lines.engine_version()
            if fmt is Format.JSON
            else parquet.engine_version(),
            "compression": "none",
        }
    )
    data = (
        json_lines.render([row], envelope=envelope.as_metadata())
        if fmt is Format.JSON
        else (
            parquet.render(
                host_output_columns(version),
                [row],
                envelope=envelope.as_metadata(),
                compression=envelope.compression,
            )
        )
    )
    suffix = ".json" if fmt is Format.JSON else ".parquet"
    path = f"state/raw/host-fingerprint/2026/09/20/{file_id}{suffix}"
    add_source(root, document, path, data, "raw", covers=spec["day"])
    return path, row


def limits_document() -> dict[str, Any]:
    document: object = json.loads((REPO / "config" / "host-telemetry-experiment.json").read_bytes())
    if not isinstance(document, dict):
        raise ValueError("experiment configuration must be a JSON object")
    migration: object = json.loads((REPO / "config" / "host-history-migration.json").read_bytes())
    if not isinstance(migration, dict):
        raise ValueError("history migration configuration must be a JSON object")
    return {
        "verification_limits": document["verification_limits"],
        "history_migration_limits": migration["history_migration_limits"],
    }


def test_named_history_config_uses_shared_verification_and_computed_bounds() -> None:
    config_root = REPO / "config"
    experiment_path = config_root / "host-telemetry-experiment.json"
    migration_path = config_root / "host-history-migration.json"
    original_experiment = experiment_path.read_bytes()
    original_migration = migration_path.read_bytes()
    experiment = json.loads(original_experiment)
    migration = json.loads(original_migration)
    assert "history_migration_limits" not in experiment
    assert set(migration) == {"history_migration_limits"}
    assert set(migration["history_migration_limits"]) == {
        field.name for field in fields(HistoryLimits) if field.name != "verification"
    }
    effective = limits_document()
    limits = HistoryLimits.from_config(effective)
    assert limits.report_bounds() == (
        experiment["verification_limits"] | migration["history_migration_limits"]
    )
    assert experiment_path.read_bytes() == original_experiment
    assert migration_path.read_bytes() == original_migration


@pytest.mark.parametrize(
    "bound", ["max_roots", "max_periods", "max_manifest_bytes", "max_bundle_bytes"]
)
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "2", None])
def test_invalid_history_bounds_protect_sources(
    workspace: Path, bound: str, value: object
) -> None:
    document = manifest_document()
    source, _ = generated_raw(workspace, document)
    original = (workspace / source).read_bytes()
    config = limits_document()
    if value is None:
        del config["history_migration_limits"][bound]
    else:
        config["history_migration_limits"][bound] = value
    with pytest.raises(ValueError, match="positive named integer bounds"):
        dry_run(
            HistoryManifest.model_validate(document),
            workspace_root=workspace,
            config_document=config,
        )
    assert (workspace / source).read_bytes() == original
    assert not (workspace / document["isolated_root"]).exists()


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "missing_experiment",
        "missing_migration",
        "invalid_json",
        "nonobject",
        "missing_section",
        "unknown_bound",
        "invalid_bound",
    ],
)
def test_cli_named_configs_fail_closed_without_source_or_config_writes(
    workspace: Path, case: str
) -> None:
    document = manifest_document()
    source, _ = generated_raw(workspace, document)
    manifest = workspace / "manifest.json"
    manifest.write_bytes(json.dumps(document).encode("ascii"))
    checkout = workspace / "maintenance-repo"
    script = checkout / "backend" / "utilities" / "migrate_host_fingerprints.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(REPO / "backend" / "utilities" / script.name, script)
    config_root = checkout / "config"
    config_root.mkdir()
    experiment = config_root / "host-telemetry-experiment.json"
    migration = config_root / "host-history-migration.json"
    shutil.copyfile(REPO / "config" / experiment.name, experiment)
    shutil.copyfile(REPO / "config" / migration.name, migration)
    if case == "missing_experiment":
        experiment.unlink()
    elif case == "missing_migration":
        migration.unlink()
    elif case == "invalid_json":
        migration.write_bytes(b"{")
    elif case == "nonobject":
        migration.write_bytes(b"[]")
    elif case == "missing_section":
        migration.write_bytes(b"{}")
    elif case in ("unknown_bound", "invalid_bound"):
        config = json.loads(migration.read_bytes())
        config["history_migration_limits"][
            "unknown_bound" if case == "unknown_bound" else "max_roots"
        ] = 0
        migration.write_bytes(json.dumps(config).encode("ascii"))
    # Workspace configs are not an alternate source, even when the named
    # repository-owned file is missing.
    decoy = workspace / "config"
    decoy.mkdir()
    for name in (experiment.name, migration.name):
        shutil.copyfile(REPO / "config" / name, decoy / name)
    decoy_migration = json.loads((decoy / migration.name).read_bytes())
    decoy_migration["history_migration_limits"]["max_roots"] = 0
    (decoy / migration.name).write_bytes(json.dumps(decoy_migration).encode("ascii"))
    protected = {
        path: path.read_bytes()
        for path in (
            workspace / source,
            manifest,
            script,
            experiment,
            migration,
            decoy / experiment.name,
            decoy / migration.name,
        )
        if path.exists()
    }
    completed = subprocess.run(
        [
            PYTHON,
            str(script),
            "--workspace-root",
            str(workspace),
            "--manifest",
            "manifest.json",
        ],
        cwd=REPO / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    summary = json.loads(completed.stdout)
    if case == "valid":
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert summary["inventory_complete"]
        assert (workspace / summary["bundle_root"] / "report.json").exists()
    else:
        assert completed.returncode == 1, completed.stdout + completed.stderr
        assert not summary["inventory_complete"] and summary["reason"]
        assert not (workspace / document["isolated_root"]).exists()
    assert all(path.read_bytes() == data for path, data in protected.items())
    assert experiment.exists() == (case != "missing_experiment")
    assert migration.exists() == (case != "missing_migration")


def run(root: Path, document: dict[str, Any]) -> Any:
    return dry_run(
        HistoryManifest.model_validate(document),
        workspace_root=root,
        config_document=limits_document(),
    )


def machine_view() -> bytes:
    from idhazh.contracts.machine_shard import MachineShardRow

    row = MachineShardRow.model_validate(
        {
            "date": "2026-09-20",
            "run_id": "2026-09-20-17",
            "shard": 0,
            "items": 0,
            "cpu_model": "Recorded CPU",
        }
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=MachineShardRow.csv_columns(), lineterminator="\n")
    writer.writeheader()
    writer.writerow(row.csv_row())
    return output.getvalue().encode("ascii")


@pytest.mark.parametrize("fmt", list(Format))
@pytest.mark.parametrize("version", LEGACY_HOST_VERSIONS)
def test_exact_raw_replacement(workspace: Path, fmt: Format, version: str) -> None:
    document = manifest_document()
    path, old = generated_raw(workspace, document, fmt=fmt, version=version)
    original = (workspace / path).read_bytes()
    report = run(workspace, document)
    assert report.inventory_complete and report.historical_readiness == "blocked"
    assert report.consumer_mode == "candidate_reader"
    file = report.files[0]
    candidate = workspace / report.bundle_root / file.candidate_path
    metadata, rows = (
        json_lines.read(candidate.read_bytes())
        if fmt is Format.JSON
        else parquet.read(candidate.read_bytes())
    )
    env = CandidateFileEnvelope.from_metadata(metadata)
    assert env.file_id == uuid.UUID(Path(path).stem)
    assert env.written_at_ms == specification()["clock_ms"]
    assert env.identity.git_sha == "b" * 40
    assert rows[0]["fingerprint"] == old["fingerprint"]
    assert rows[0]["fingerprint_version"] == 1
    assert rows[0]["cpu_observed_mhz"] == 2300.0
    assert all(rows[0][key] is None for key in specification()["unmeasured"])
    assert file.rows[0].dropped_values == specification()["dropped"]
    assert set(file.rows[0].null_fields) >= set(specification()["unmeasured"])
    assert file.rows[0].original_identity == file.rows[0].normalized_identity
    assert file.old_content_sha256 != file.new_content_sha256
    assert (workspace / path).read_bytes() == original
    assert env.row_schema_version == HOST_OUTPUT_VERSION
    assert env.writer.startswith("idhazh.")
    assert report.derived_views_status == "not_applicable"
    assert run(workspace, document) == report


def test_duplicates_attempts_views_receipts(workspace: Path) -> None:
    document = manifest_document()
    first, _ = generated_raw(workspace, document)
    second, _ = generated_raw(workspace, document, clock_offset=1, clocks=True)
    third, _ = generated_raw(workspace, document, attempt=2, clock_offset=2, average=None)
    view = add_source(
        workspace,
        document,
        "frontend/public/machine/2026-09.csv",
        machine_view(),
        "view",
        dependencies=[first, second, third],
    )
    receipt = {
        "version": "2026-10-09",
        "identity": document["invocation"],
        "writes": {entry["path"]: entry["sha256"] for entry in document["sources"]},
    }
    add_source(
        workspace,
        document,
        "evidence/old-receipt.json",
        (json.dumps(receipt) + "\n").encode(),
        "receipt",
        dependencies=[first, second, third, view],
    )
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    report = run(workspace, document)
    assert report.original_settled_keys == report.normalized_settled_keys == 1
    assert report.settlement[0].source_path == third
    assert report.derived_views_status == report.receipt_status_derived_views == "deferred"
    assert report.historical_readiness == "blocked"
    assert report.affected_view_paths == (view,)
    assert report.files[3].candidate_path is None
    assert report.deferred_receipt_paths == ("evidence/old-receipt.json",)
    maintenance = report.maintenance_receipt_candidate
    assert (
        maintenance.identity.model_dump()
        == HistoryManifest.model_validate(document).invocation.model_dump()
    )
    assert view not in maintenance.writes
    assert maintenance.writes[first] != receipt["writes"][first]
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize("fault", ["hash", "missing", "metadata", "unknown", "mixed", "dependency"])
def test_bad_final_source_has_no_bundle(workspace: Path, fault: str) -> None:
    document = manifest_document()
    first, _ = generated_raw(workspace, document)
    last, _ = generated_raw(workspace, document, clock_offset=1)
    if fault == "hash":
        (workspace / last).write_bytes(b"drift")
    elif fault == "missing":
        (workspace / last).unlink()
    else:
        data = (workspace / last).read_bytes()
        metadata, rows = json_lines.read(data)
        if fault == "metadata":
            del metadata[b"git_sha"]
        elif fault == "unknown":
            metadata[b"schema_version"] = b"2099-01-01"
        elif fault == "mixed":
            rows[0]["version"] = "2026-09-19"
            metadata[b"content_sha256"] = (
                hashlib.sha256(json_lines.rows_bytes(rows)).hexdigest().encode()
            )
        elif fault == "dependency":
            document["sources"][-1]["dependencies"] = ["state/not-declared.json"]
        replacement = json_lines.render(rows, envelope=metadata)
        (workspace / last).write_bytes(replacement)
        document["sources"][-1].update(
            bytes=len(replacement), sha256=hashlib.sha256(replacement).hexdigest()
        )
    original = (workspace / first).read_bytes()
    with pytest.raises((ValueError, OSError)):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert (workspace / first).read_bytes() == original


def test_apply_is_not_a_capability(workspace: Path) -> None:
    completed = subprocess.run(
        [PYTHON, "-m", "utilities.migrate_host_fingerprints", "--apply"],
        cwd=REPO / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "apply is not implemented" in completed.stderr.lower()


def generated_compact(
    workspace: Path,
    document: dict[str, Any],
    fmt: Format,
    *,
    compact_only: bool = True,
    period: str = "daily",
    compression: str = "none",
) -> str:
    from idhazh.contracts.ledger_index import CompactIndex
    from idhazh.ledger.filenames import unit_id

    first, row = generated_raw(workspace, document, fmt=fmt)
    second, other = generated_raw(workspace, document, fmt=fmt, shard=1)
    dependencies = [first, second]
    if compact_only:
        document["sources"] = []
        (workspace / first).unlink()
        (workspace / second).unlink()
        dependencies = []
    covers = {"daily": "2026-09-20", "monthly": "2026-09", "yearly": "2026"}[period]
    if period != "daily":
        document["closed_periods"].append(
            {"root": "production", "covers": covers, "period": period}
        )
    if period == "yearly":
        document.update(
            range_start="2026-01-01", range_end="2026-12-31", converted_at="2027-01-02T12:00:00Z"
        )
    identity = HostWriterIdentity(
        run_id=document["invocation"]["run_id"],
        attempt=1,
        job=ServerJob.OPERATOR,
        shard=0,
        producer="gardener.compact",
        git_sha="a" * 40,
    )
    unit = unit_id(
        ledger="host-fingerprint",
        covers=covers,
        run_id=identity.run_id,
        job=identity.job.value,
        shard=0,
        producer=identity.producer,
    )
    clock = specification()["clock_ms"] + 20 * 86400000
    envelope = CandidateFileEnvelope.model_validate(
        {
            "version": "2026-10-06",
            "row_schema_version": "2026-09-20",
            "tier": "compact",
            "period": period,
            "ledger": "host-fingerprint",
            "covers": covers,
            "written_at_ms": clock,
            "identity": identity,
            "unit_id": unit,
            "file_id": host_file_id(unit=unit, attempt=1, written_at_ms=clock),
            "content_sha256": hashlib.sha256(json_lines.rows_bytes([row, other])).hexdigest(),
            "writer": "idhazh.ledger.json_lines" if fmt is Format.JSON else "idhazh.ledger.parquet",
            "writer_version": json_lines.engine_version()
            if fmt is Format.JSON
            else parquet.engine_version(),
            "compression": compression if fmt is Format.PARQUET else "none",
            "built_from": 2,
        }
    )
    data = (
        json_lines.render([row, other], envelope=envelope.as_metadata())
        if fmt is Format.JSON
        else (
            parquet.render(
                host_output_columns("2026-09-20"),
                [row, other],
                envelope=envelope.as_metadata(),
                compression=envelope.compression,
            )
        )
    )
    relative = {"daily": "2026/09/20", "monthly": "2026/09", "yearly": "2026/2026"}[period]
    path = f"state/compact/host-fingerprint/{period}/{relative}.{fmt.value}"
    add_source(workspace, document, path, data, "compact", dependencies=dependencies, covers=covers)
    document["sources"][-1]["period"] = period
    index = CompactIndex.model_validate(
        {
            "version": "2026-10-07",
            "ledger": "host-fingerprint",
            "period": period,
            "entries": [
                {
                    "covers": covers,
                    "rows": 2,
                    "bytes": len(data),
                    "state": "packed",
                    "lost_days": [] if period == "daily" else ["2026-09-19"],
                    "set_aside": 0,
                }
            ],
            **({"expired_through": "2025"} if period == "yearly" else {}),
        }
    )
    add_source(
        workspace,
        document,
        f"state/compact/host-fingerprint/index/{period}.json",
        index.to_json().encode(),
        "compact_index",
        dependencies=[path],
    )
    return path


@pytest.mark.parametrize("fmt", list(Format))
@pytest.mark.parametrize("period", ["daily", "monthly", "yearly"])
@pytest.mark.parametrize("compact_only", [True, False])
def test_compact_dependencies_and_index(
    workspace: Path, fmt: Format, period: str, compact_only: bool
) -> None:
    document = manifest_document()
    path = generated_compact(workspace, document, fmt, period=period, compact_only=compact_only)
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    report = run(workspace, document)
    file = next(file for file in report.files if file.source.path == path)
    assert file.row_count == file.settled_key_count == 2
    assert file.old_envelope.identity == file.new_envelope.identity
    assert file.old_envelope.file_id == file.new_envelope.file_id
    assert file.old_envelope.built_from == file.new_envelope.built_from == 2
    index = report.files[-1]
    assert index.candidate_document["entries"][0]["bytes"] == file.candidate_bytes
    assert index.candidate_document["entries"][0]["rows"] == 2
    for marker in ("state", "lost_days", "set_aside"):
        assert (
            index.original_document["entries"][0][marker]
            == index.candidate_document["entries"][0][marker]
        )
    assert index.original_document.get("expired_through") == index.candidate_document.get(
        "expired_through"
    )
    assert report.original_settled_keys == report.normalized_settled_keys == 2
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


def test_lost_and_empty_index_periods_are_not_recovered(workspace: Path) -> None:
    from idhazh.contracts.ledger_index import CompactIndex

    document = manifest_document()
    document["closed_periods"].append(
        {"root": "production", "covers": "2026-09-21", "period": "daily"}
    )
    index = CompactIndex.model_validate(
        {
            "ledger": "host-fingerprint",
            "period": "daily",
            "entries": [
                {"covers": "2026-09-20", "rows": 0, "bytes": 0, "state": "lost"},
                {"covers": "2026-09-21", "rows": 0, "bytes": 0, "state": "empty"},
            ],
        }
    )
    path = add_source(
        workspace,
        document,
        "state/compact/host-fingerprint/index/daily.json",
        index.to_json().encode(),
        "compact_index",
    )
    original = (workspace / path).read_bytes()
    report = run(workspace, document)
    assert report.original_settled_keys == 0
    assert (
        report.files[0].candidate_document["entries"]
        == report.files[0].original_document["entries"]
    )
    assert (workspace / path).read_bytes() == original


def test_set_aside_is_an_explicit_unresolved_source(workspace: Path) -> None:
    document = manifest_document()
    add_source(
        workspace,
        document,
        "state/raw/host-fingerprint/set-aside/bad.json",
        b"unread original",
        "set_aside",
        covers="2026-09-20",
    )
    report = run(workspace, document)
    assert report.inventory_complete is False
    assert report.files[0].status == "unresolved"
    assert report.files[0].candidate_path is None
    assert "set_aside_sources_unresolved" in report.blocked_by


@pytest.mark.parametrize(
    "bound",
    [
        "max_files",
        "max_file_bytes",
        "max_total_bytes",
        "max_rows",
        "max_periods",
        "max_roots",
        "max_manifest_bytes",
        "max_bundle_bytes",
    ],
)
def test_configured_bounds_fail_before_publication(workspace: Path, bound: str) -> None:
    document = manifest_document()
    generated_compact(workspace, document, Format.JSON, compact_only=False)
    config = limits_document()
    section = (
        "verification_limits"
        if bound in config["verification_limits"]
        else "history_migration_limits"
    )
    config[section][bound] = 1
    if bound in ("max_roots", "max_periods"):
        document["roots"].append(
            {
                "name": "trial",
                "kind": "trial",
                "state_root": "state",
                "prefix": ["trial", "host-fingerprint"],
            }
        )
        document["closed_periods"].append(
            {"root": "trial", "covers": "2026-09-20", "period": "daily"}
        )
    with pytest.raises(ValueError):
        dry_run(
            HistoryManifest.model_validate(document),
            workspace_root=workspace,
            config_document=config,
        )
    assert not (workspace / document["isolated_root"]).exists()


def test_raw_index_bytes_and_exact_dependencies(workspace: Path) -> None:
    from idhazh.contracts.ledger_index import RawDayIndex

    document = manifest_document()
    path, _ = generated_raw(workspace, document)
    name = Path(path).name
    index = RawDayIndex.model_validate(
        {
            "ledger": "host-fingerprint",
            "date": "2026-09-20",
            "files": [name],
            "bytes": [document["sources"][0]["bytes"]],
            "content_sha256": hashlib.sha256(name.encode()).hexdigest(),
            "listed_at": "2026-10-01T12:00:00Z",
        }
    )
    add_source(
        workspace,
        document,
        "state/raw/host-fingerprint/2026/09/20/index.json",
        index.to_json().encode(),
        "raw_index",
        dependencies=[path],
        covers="2026-09-20",
    )
    report = run(workspace, document)
    assert report.files[-1].candidate_document["bytes"] == [report.files[0].candidate_bytes]


def test_restart_accepts_only_exact_partial_candidates(workspace: Path) -> None:
    document = manifest_document()
    path, _ = generated_raw(workspace, document)
    report = run(workspace, document)
    bundle = workspace / report.bundle_root
    (bundle / "report.json").unlink()
    assert run(workspace, document) == report
    candidate = bundle / report.files[0].candidate_path
    candidate.write_bytes(b"third state")
    with pytest.raises(ValueError, match="conflicts"):
        run(workspace, document)
    assert (
        hashlib.sha256((workspace / path).read_bytes()).hexdigest()
        == document["sources"][0]["sha256"]
    )


def test_cli_reads_only_explicit_manifest(workspace: Path) -> None:
    document = manifest_document()
    generated_raw(workspace, document)
    manifest = workspace / "manifest.json"
    manifest.write_text(json.dumps(document), encoding="ascii")
    completed = subprocess.run(
        [
            PYTHON,
            "-m",
            "utilities.migrate_host_fingerprints",
            "--workspace-root",
            str(workspace),
            "--manifest",
            "manifest.json",
        ],
        cwd=REPO / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["inventory_complete"] and summary["historical_readiness"] == "blocked"
    assert (workspace / summary["bundle_root"] / "report.json").exists()


@pytest.mark.parametrize("fault", ["metadata", "index", "dependency", "view_version"])
def test_final_compact_or_view_defect_cannot_publish(workspace: Path, fault: str) -> None:
    document = manifest_document()
    generated_compact(workspace, document, Format.JSON, compact_only=False)
    if fault == "view_version":
        view = machine_view().replace(b"2026-09-20T18:00", b"2099-01-01")
        add_source(
            workspace,
            document,
            "frontend/public/machine/2026-09.csv",
            view,
            "view",
            dependencies=[document["sources"][0]["path"]],
        )
    elif fault == "dependency":
        document["sources"][-1]["dependencies"] = []
    else:
        selected = document["sources"][-2 if fault == "metadata" else -1]
        path = workspace / selected["path"]
        if fault == "metadata":
            metadata, rows = json_lines.read(path.read_bytes())
            del metadata[b"git_sha"]
            data = json_lines.render(rows, envelope=metadata)
        else:
            index = json.loads(path.read_bytes())
            index["entries"][0]["rows"] += 1
            data = json.dumps(index).encode()
        path.write_bytes(data)
        selected.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    with pytest.raises(ValueError):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


def test_source_read_only_and_report_tamper_detection(workspace: Path) -> None:
    import stat

    from idhazh.contracts.host_migration import HistoryReport

    document = manifest_document()
    path, _ = generated_raw(workspace, document)
    source = workspace / path
    original = source.read_bytes()
    source.chmod(stat.S_IREAD)
    try:
        report = run(workspace, document)
        assert source.read_bytes() == original
        assert HistoryReport.from_json(report.to_json()) == report
        tampered = report.model_dump(mode="json")
        tampered["estimated_read_bytes"] += 1
        with pytest.raises(ValueError, match="evidence_hash"):
            HistoryReport.model_validate(tampered)
        falsely_ready = report.model_dump(mode="json") | {"historical_readiness": "ready"}
        with pytest.raises(ValueError, match="candidate reader"):
            HistoryReport.model_validate(falsely_ready)
    finally:
        source.chmod(stat.S_IREAD | stat.S_IWRITE)


def test_separate_trial_roots_do_not_merge_settlement_keys(workspace: Path) -> None:
    document = manifest_document()
    production, _ = generated_raw(workspace, document)
    data = (workspace / production).read_bytes()
    document["roots"].append(
        {
            "name": "trial",
            "kind": "trial",
            "state_root": "state",
            "prefix": ["trial", "nested", "host-fingerprint"],
        }
    )
    document["closed_periods"].append({"root": "trial", "covers": "2026-09-20", "period": "daily"})
    trial = production.replace("raw/host-fingerprint", "raw/trial/nested/host-fingerprint")
    add_source(workspace, document, trial, data, "raw", covers="2026-09-20")
    document["sources"][-1]["root"] = "trial"
    report = run(workspace, document)
    assert report.original_settled_keys == 2
    assert {s.root for s in report.settlement} == {"production", "trial"}


def test_already_corrected_python_bytes_are_excluded_without_reencoding(workspace: Path) -> None:
    from idhazh.contracts.host_output import normalize_stored_host_rows

    document = manifest_document()
    path, _ = generated_raw(workspace, document)
    metadata, rows = json_lines.read((workspace / path).read_bytes())
    corrected = [
        r.model_dump(mode="json")
        for r in normalize_stored_host_rows(
            rows, content_sha256=metadata[b"content_sha256"].decode()
        )
    ]
    metadata[b"envelope_version"] = HOST_OUTPUT_VERSION.encode()
    metadata[b"schema_version"] = HOST_OUTPUT_VERSION.encode()
    metadata[b"content_sha256"] = (
        hashlib.sha256(json_lines.rows_bytes(corrected)).hexdigest().encode()
    )
    data = json_lines.render(corrected, envelope=metadata)
    (workspace / path).write_bytes(data)
    document["sources"][0].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    report = run(workspace, document)
    assert report.files[0].status == "excluded_corrected"
    assert report.files[0].candidate_path is None
    assert report.maintenance_receipt_candidate.writes == {}
    assert (workspace / path).read_bytes() == data


@pytest.mark.parametrize("compression", ["snappy", "zstd"])
def test_compact_actual_compression(workspace: Path, compression: str) -> None:
    document = manifest_document()
    generated_compact(workspace, document, Format.PARQUET, compression=compression)
    report = run(workspace, document)
    assert report.files[0].old_envelope.compression.value == compression
    assert report.files[0].new_envelope.compression.value == compression
    assert report.files[0].row_count == 2


def test_console_view_is_validated_but_not_fabricated(workspace: Path) -> None:
    from idhazh.contracts.console_band import ConsoleBand

    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    console = ConsoleBand.model_validate(
        {
            "generated_at": "2026-10-01T12:00:00Z",
            "verdict": {"sentence": "Recorded run.", "health": "green"},
            "size": {"sentence": "Size not recorded."},
        }
    )
    view = add_source(
        workspace,
        document,
        "frontend/public/console/band.json",
        console.to_json().encode("ascii"),
        "view",
        dependencies=[raw],
    )
    original = (workspace / view).read_bytes()
    report = run(workspace, document)
    assert report.files[-1].status == "deferred"
    assert report.files[-1].new_physical_sha256 is None
    assert view not in report.maintenance_receipt_candidate.writes
    assert (workspace / view).read_bytes() == original


def test_empty_scope_has_complete_inventory_but_no_historical_readiness(workspace: Path) -> None:
    document = manifest_document()
    report = run(workspace, document)
    assert report.inventory_complete
    assert report.files == ()
    assert report.original_settled_keys == 0
    assert report.derived_views_status == "not_applicable"
    assert report.historical_readiness == "blocked"


def test_distinct_evidence_generations_keep_the_same_scope(workspace: Path) -> None:
    document = manifest_document()
    generated_raw(workspace, document)
    first = run(workspace, document)
    config = limits_document()
    config["history_migration_limits"]["max_bundle_bytes"] += 1
    second = dry_run(
        HistoryManifest.model_validate(document), workspace_root=workspace, config_document=config
    )
    assert first.scope_hash == second.scope_hash
    assert first.evidence_hash != second.evidence_hash
    assert first.bundle_root != second.bundle_root
    assert (workspace / first.bundle_root / "report.json").exists()
    assert (workspace / second.bundle_root / "report.json").exists()


@pytest.mark.parametrize("fmt", list(Format))
def test_unmeasured_history_never_gains_observations(workspace: Path, fmt: Format) -> None:
    document = manifest_document()
    generated_raw(workspace, document, average=None, fingerprint=False, fmt=fmt)
    report = run(workspace, document)
    row = report.files[0].rows[0]
    assert row.retained_average is None
    assert row.original_fingerprint is None and row.fingerprint_version is None
    assert "cpu_observed_mhz" in row.null_fields and "fingerprint_version" in row.null_fields


def test_mixed_legacy_revisions_in_distinct_files_are_inventory_not_error(workspace: Path) -> None:
    document = manifest_document()
    first, _ = generated_raw(workspace, document, version=LEGACY_HOST_VERSIONS[0])
    second, _ = generated_raw(workspace, document, version=LEGACY_HOST_VERSIONS[-1], attempt=2)
    report = run(workspace, document)
    assert [file.rows[0].original_version for file in report.files] == [
        LEGACY_HOST_VERSIONS[0],
        LEGACY_HOST_VERSIONS[-1],
    ]
    assert report.original_settled_keys == 1
    assert report.settlement[0].source_path == second != first


@pytest.mark.parametrize("fault", ["partial", "payload"])
def test_compact_dependency_provenance_must_reconcile(workspace: Path, fault: str) -> None:
    document = manifest_document()
    compact = generated_compact(workspace, document, Format.JSON, compact_only=False)
    source = next(source for source in document["sources"] if source["path"] == compact)
    if fault == "partial":
        source["dependencies"].pop()
    else:
        target = workspace / compact
        metadata, rows = json_lines.read(target.read_bytes())
        rows[0]["cores"] += 1
        metadata[b"content_sha256"] = (
            hashlib.sha256(json_lines.rows_bytes(rows)).hexdigest().encode()
        )
        data = json_lines.render(rows, envelope=metadata)
        target.write_bytes(data)
        source.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        # Keep the index truthful so the dependency reconciliation, not a size
        # mismatch, is the refusal being exercised.
        index_source = document["sources"][-1]
        index_path = workspace / index_source["path"]
        index = json.loads(index_path.read_bytes())
        index["entries"][0]["bytes"] = len(data)
        index_data = json.dumps(index).encode()
        index_path.write_bytes(index_data)
        index_source.update(bytes=len(index_data), sha256=hashlib.sha256(index_data).hexdigest())
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    with pytest.raises(ValueError, match=r"compact.*(dependencies|settlement)"):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize(
    "fault", ["envelope_version", "file_identity", "receipt_hash", "view_path"]
)
def test_finite_metadata_and_original_lineage_refusals(workspace: Path, fault: str) -> None:
    from idhazh.contracts.publication_receipt import PublicationReceipt

    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    if fault == "receipt_hash":
        receipt = PublicationReceipt(
            version=PublicationReceipt.schema_version(),
            identity=HostWriterIdentity.model_validate(document["invocation"]),
            writes={raw: "f" * 64},
        )
        add_source(
            workspace,
            document,
            "state/receipts/old.json",
            receipt.to_json().encode("ascii"),
            "receipt",
            dependencies=[raw],
        )
    elif fault == "view_path":
        add_source(
            workspace,
            document,
            "frontend/public/machine/extra/2026-09.csv",
            machine_view(),
            "view",
            dependencies=[raw],
        )
    else:
        source = document["sources"][0]
        target = workspace / raw
        metadata, rows = json_lines.read(target.read_bytes())
        metadata[b"version" if fault == "envelope_version" else b"file_id"] = (
            b"2099-01-01"
            if fault == "envelope_version"
            else str(
                host_file_id(
                    unit=uuid.UUID(rows[0]["unit_id"]),
                    attempt=1,
                    written_at_ms=specification()["clock_ms"] + 1,
                )
            ).encode()
        )
        data = json_lines.render(rows, envelope=metadata)
        target.write_bytes(data)
        source.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    with pytest.raises(ValueError):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize(
    "fault", ["missing_file", "unresolved", "settlement", "receipt_invocation"]
)
def test_report_rehash_cannot_hide_inconsistent_inventory(workspace: Path, fault: str) -> None:
    from idhazh.contracts.base import compact_json
    from idhazh.contracts.host_migration import HistoryReport

    document = manifest_document()
    generated_raw(workspace, document)
    payload = run(workspace, document).model_dump(mode="json")
    if fault == "missing_file":
        payload["files"] = []
        payload["maintenance_receipt_candidate"]["writes"] = {}
    elif fault == "unresolved":
        payload["inventory_complete"] = False
    elif fault == "settlement":
        payload["settlement"] = []
    else:
        payload["maintenance_receipt_candidate"]["identity"]["git_sha"] = "d" * 40
    payload["evidence_hash"] = hashlib.sha256(
        compact_json(
            {
                key: value
                for key, value in payload.items()
                if key not in ("evidence_hash", "bundle_root")
            }
        ).encode("ascii")
    ).hexdigest()
    payload["bundle_root"] = (
        f"{document['isolated_root']}/{payload['scope_hash']}/{payload['evidence_hash']}"
    )
    with pytest.raises(ValueError):
        HistoryReport.model_validate(payload)


@pytest.mark.parametrize("boundary", ["source", "output"])
def test_real_link_or_reparse_boundary_is_refused(workspace: Path, boundary: str) -> None:
    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    original = (workspace / raw).read_bytes()
    held = workspace / "held"
    if boundary == "source":
        link = (workspace / raw).parent
        link.rename(held)
    else:
        held.mkdir()
        link = workspace / document["isolated_root"]
        link.parent.mkdir(parents=True)
    if os.name == "nt":
        # Junctions exercise the real Windows reparse boundary without requiring
        # administrator privilege or Developer Mode for symlink creation.
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "New-Item -ItemType Junction -Path '"
                + str(link).replace("'", "''")
                + "' -Target '"
                + str(held).replace("'", "''")
                + "' | Out-Null",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
    else:
        link.symlink_to(held, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match=r"symlink|reparse"):
            run(workspace, document)
        if boundary == "source":
            assert (held / Path(raw).name).read_bytes() == original
            assert not (workspace / document["isolated_root"]).exists()
        else:
            assert not list(held.iterdir())
            assert (workspace / raw).read_bytes() == original
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def repin_source(workspace: Path, source: dict[str, Any], data: bytes) -> None:
    (workspace / source["path"]).write_bytes(data)
    source.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def duplicate_root_source(
    workspace: Path, document: dict[str, Any], *, state: str, hardlink: bool = False
) -> None:
    original = document["sources"][0]
    path = original["path"].replace("state/", state + "/", 1)
    target = workspace / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if hardlink:
        os.link(workspace / original["path"], target)
    elif not target.exists():
        target.write_bytes((workspace / original["path"]).read_bytes())
    document["roots"].append({**document["roots"][0], "name": "other", "state_root": state})
    document["closed_periods"].append({**document["closed_periods"][0], "root": "other"})
    document["sources"].append({**original, "root": "other", "path": path})


def test_case_alias_history_roots_use_real_filesystem_identity(workspace: Path) -> None:
    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    duplicate_root_source(workspace, document, state="STATE")
    before = (workspace / raw).read_bytes()
    if (workspace / "state").samefile(workspace / "STATE"):
        with pytest.raises(ValueError, match="duplicate physical history root"):
            run(workspace, document)
        assert not (workspace / document["isolated_root"]).exists()
    else:
        report = run(workspace, document)
        assert report.original_settled_keys == 2
        assert {root.state_root for root in report.manifest.roots} == {"state", "STATE"}
    assert (workspace / raw).read_bytes() == before


@pytest.mark.parametrize("historical_root", ["backend/VAR", "backend/VAR/host-history"])
def test_case_alias_isolated_overlap_has_no_writes(
    workspace: Path, historical_root: str
) -> None:
    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    source = document["sources"][0]
    data = (workspace / raw).read_bytes()
    source["path"] = raw.replace("state/", historical_root + "/", 1)
    document["roots"][0]["state_root"] = historical_root
    (workspace / source["path"]).parent.mkdir(parents=True)
    repin_source(workspace, source, data)
    document["isolated_root"] = "backend/var/host-history/dry-run"
    if os.name == "nt":
        assert (workspace / "backend/VAR").samefile(workspace / "backend/var")
        with pytest.raises(ValueError, match="isolated output overlaps"):
            run(workspace, document)
        assert not (workspace / document["isolated_root"]).exists()
    else:
        assert not (workspace / "backend/var").exists()
        report = run(workspace, document)
        assert report.manifest.roots[0].state_root == historical_root
    assert (workspace / source["path"]).read_bytes() == data


def test_hardlinked_sources_cannot_create_distinct_settlements(workspace: Path) -> None:
    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    duplicate_root_source(workspace, document, state="other-state", hardlink=True)
    before = (workspace / raw).read_bytes()
    with pytest.raises(ValueError, match="duplicate physical source"):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert all((workspace / s["path"]).read_bytes() == before for s in document["sources"])


def test_hardlinked_candidate_targets_fail_whole_batch_preflight(workspace: Path) -> None:
    from idhazh.telemetry.host_history_files import HistoryLimits
    from idhazh.telemetry.host_history_migration import prepare_history

    document = manifest_document()
    generated_raw(workspace, document)
    duplicate_root_source(workspace, document, state="other-state")
    prepared = prepare_history(
        HistoryManifest.model_validate(document),
        workspace=workspace,
        limits=HistoryLimits.from_config(limits_document()),
    )
    bundle = workspace / prepared.report.bundle_root
    candidates = [
        (bundle / p, data)
        for p, data in prepared.artifacts.items()
        if p.startswith("candidates/")
    ]
    assert len(candidates) == 2 and candidates[0][1] == candidates[1][1]
    for target, _ in candidates:
        target.parent.mkdir(parents=True, exist_ok=True)
    candidates[0][0].write_bytes(candidates[0][1])
    os.link(candidates[0][0], candidates[1][0])
    before = {
        p.relative_to(workspace): p.read_bytes() for p in workspace.rglob("*") if p.is_file()
    }
    with pytest.raises(ValueError, match="duplicate physical bundle target"):
        run(workspace, document)
    assert {
        p.relative_to(workspace): p.read_bytes() for p in workspace.rglob("*") if p.is_file()
    } == before
    assert not (bundle / "report.json").exists()


@pytest.mark.parametrize("footer_rows", [1, 3])
def test_repinned_compact_footer_cardinality_refused_before_bundle(
    workspace: Path, footer_rows: int
) -> None:
    from test_host_parquet_admission import _patch_footer

    document = manifest_document()
    generated_compact(workspace, document, Format.PARQUET, compact_only=False)
    raw = document["sources"][0]["path"]
    source = next(s for s in document["sources"] if s["kind"] == "compact")
    data = _patch_footer((workspace / source["path"]).read_bytes(), {(3,): footer_rows})
    repin_source(workspace, source, data)
    index = document["sources"][-1]
    original_index = json.loads((workspace / index["path"]).read_bytes())
    original_index["entries"][0]["bytes"] = len(data)
    repin_source(workspace, index, json.dumps(original_index).encode("ascii"))
    # The corrupt compact source is the final read, after every other valid source.
    document["sources"].remove(source)
    document["sources"].append(source)
    engine = parquet.pyarrow  # type: ignore[attr-defined]
    opened = engine.parquet.ParquetFile(engine.BufferReader(data))
    assert opened.metadata.num_rows == footer_rows
    assert sum(
        opened.metadata.row_group(i).num_rows for i in range(opened.metadata.num_row_groups)
    ) == 2
    opened.close()
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    with pytest.raises(ValueError, match=r"Parquet.*row.*(footer|cardinality)"):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert (workspace / raw).read_bytes() == before[raw]
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


def test_repinned_raw_footer_cardinality_remains_refused(workspace: Path) -> None:
    from test_host_parquet_admission import _patch_footer

    document = manifest_document()
    generated_raw(workspace, document, fmt=Format.PARQUET)
    source = document["sources"][0]
    repin_source(
        workspace,
        source,
        _patch_footer((workspace / source["path"]).read_bytes(), {(3,): 2}),
    )
    before = (workspace / source["path"]).read_bytes()
    with pytest.raises(ValueError, match="exactly one row"):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert (workspace / source["path"]).read_bytes() == before


@pytest.mark.parametrize("fmt", list(Format))
@pytest.mark.parametrize("period", ["monthly", "yearly"])
def test_repinned_lost_day_with_compact_rows_refuses_entire_batch(
    workspace: Path, fmt: Format, period: str
) -> None:
    document = manifest_document()
    generated_compact(workspace, document, fmt, period=period, compact_only=False)
    index = document["sources"][-1]
    payload = json.loads((workspace / index["path"]).read_bytes())
    payload["entries"][0]["lost_days"] = ["2026-09-20"]
    repin_source(workspace, index, json.dumps(payload).encode("ascii"))
    before = {s["path"]: (workspace / s["path"]).read_bytes() for s in document["sources"]}
    with pytest.raises(ValueError, match=r"compact index.*lost.*rows"):
        run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()
    assert all((workspace / path).read_bytes() == data for path, data in before.items())


def test_case_alias_source_is_not_a_second_manifested_file(workspace: Path) -> None:
    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    alias = raw.replace("state/", "STATE/", 1)
    if os.name == "nt":
        assert (workspace / raw).samefile(workspace / alias)
        document["sources"].append({**document["sources"][0], "path": alias})
        with pytest.raises(ValueError, match="duplicate physical source"):
            run(workspace, document)
    else:
        (workspace / alias).parent.mkdir(parents=True)
        (workspace / alias).write_bytes((workspace / raw).read_bytes())
        assert not (workspace / raw).samefile(workspace / alias)
        document["sources"].append({**document["sources"][0], "path": alias})
        with pytest.raises(ValueError, match="path contradicts"):
            run(workspace, document)
    assert not (workspace / document["isolated_root"]).exists()


def test_case_alias_trial_prefix_is_not_a_second_history_root(workspace: Path) -> None:
    document = manifest_document()
    raw, _ = generated_raw(workspace, document)
    path = raw.replace("state/raw/", "state/raw/trial/", 1)
    (workspace / path).parent.mkdir(parents=True)
    (workspace / path).write_bytes((workspace / raw).read_bytes())
    document["roots"][0].update(kind="trial", prefix=["trial", "host-fingerprint"])
    document["sources"][0]["path"] = path
    alias = path.replace("/trial/", "/TRIAL/", 1)
    document["roots"].append(
        {**document["roots"][0], "name": "other", "prefix": ["TRIAL", "host-fingerprint"]}
    )
    document["closed_periods"].append({**document["closed_periods"][0], "root": "other"})
    if os.name == "nt":
        assert (workspace / alias).samefile(workspace / path)
        document["sources"].append({**document["sources"][0], "path": alias, "root": "other"})
        with pytest.raises(ValueError, match="duplicate physical history root"):
            run(workspace, document)
        assert not (workspace / document["isolated_root"]).exists()
    else:
        (workspace / alias).parent.mkdir(parents=True)
        (workspace / alias).write_bytes((workspace / path).read_bytes())
        document["sources"].append({**document["sources"][0], "path": alias, "root": "other"})
        report = run(workspace, document)
        assert report.original_settled_keys == 2
        assert {root.prefix[0] for root in report.manifest.roots} == {"trial", "TRIAL"}


@pytest.mark.parametrize(
    ("period", "lost_day"),
    [("monthly", "2026-09-30"), ("yearly", "2026-12-31")],
)
def test_loss_without_rows_and_set_aside_are_preserved(
    workspace: Path, period: str, lost_day: str
) -> None:
    document = manifest_document()
    generated_compact(workspace, document, Format.PARQUET, period=period)
    source = document["sources"][-1]
    index = json.loads((workspace / source["path"]).read_bytes())
    index["entries"][0].update(lost_days=[lost_day], set_aside=2)
    repin_source(workspace, source, json.dumps(index).encode("ascii"))
    before = (workspace / source["path"]).read_bytes()
    report = run(workspace, document)
    candidate = report.files[-1].candidate_document
    assert candidate["entries"][0]["lost_days"] == [lost_day]
    assert candidate["entries"][0]["set_aside"] == 2
    assert candidate.get("expired_through") == index.get("expired_through")
    assert (workspace / source["path"]).read_bytes() == before


def test_all_set_aside_period_does_not_claim_recovered_rows(workspace: Path) -> None:
    from idhazh.contracts.ledger_index import CompactIndex

    document = manifest_document()
    document["closed_periods"].append(
        {"root": "production", "covers": "2026-09", "period": "monthly"}
    )
    index = CompactIndex.model_validate(
        {
            "ledger": "host-fingerprint",
            "period": "monthly",
            "entries": [
                {
                    "covers": "2026-09",
                    "rows": 0,
                    "bytes": 0,
                    "state": "empty",
                    "lost_days": ["2026-09-20"],
                    "set_aside": 2,
                }
            ],
        }
    )
    add_source(
        workspace, document, "state/compact/host-fingerprint/index/monthly.json",
        index.to_json().encode("ascii"), "compact_index",
    )
    report = run(workspace, document)
    assert report.files[0].candidate_document["entries"] == index.model_dump(mode="json")["entries"]
    assert report.original_settled_keys == report.normalized_settled_keys == 0
    assert report.historical_readiness == "blocked"


def test_missing_candidate_case_aliases_are_preflighted_without_creation(workspace: Path) -> None:
    from idhazh.telemetry.host_history_paths import preflight_targets

    document = manifest_document()
    parent = workspace / document["isolated_root"]
    parent.mkdir(parents=True)
    probe = parent / "case-probe"
    probe.write_bytes(b"fixture")
    aliases = (parent / "candidates" / "row.json", parent / "candidates" / "ROW.json")
    manifest = HistoryManifest.model_validate(document)
    if (parent / "CASE-PROBE").exists() and probe.samefile(parent / "CASE-PROBE"):
        with pytest.raises(ValueError, match="duplicate physical bundle target"):
            preflight_targets(manifest, workspace=workspace, targets=aliases)
    else:
        preflight_targets(manifest, workspace=workspace, targets=aliases)
    assert not (parent / "candidates").exists()
    assert probe.read_bytes() == b"fixture"


def test_missing_isolated_case_overlap_is_refused_before_any_directory(workspace: Path) -> None:
    document = manifest_document()
    parent = workspace / "backend"
    parent.mkdir()
    probe = parent / "case-probe"
    probe.write_bytes(b"fixture")
    document["roots"][0]["state_root"] = "backend/VAR/host-history"
    document["isolated_root"] = "backend/var/host-history/dry-run"
    if (parent / "CASE-PROBE").exists() and probe.samefile(parent / "CASE-PROBE"):
        with pytest.raises(ValueError, match="isolated output overlaps"):
            run(workspace, document)
        assert not (parent / "VAR").exists()
        assert not (parent / "var").exists()
    else:
        report = run(workspace, document)
        assert report.manifest.roots[0].state_root == "backend/VAR/host-history"
    assert probe.read_bytes() == b"fixture"
