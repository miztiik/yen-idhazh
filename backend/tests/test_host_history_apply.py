"""Generated, bounded D17 transaction fixtures; no repository history is read."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from idhazh.contracts.base import ServerJob
from idhazh.contracts.console_band import ConsoleBand
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.host_migration import (
    ClosedHistoryPeriod,
    HistoryManifest,
    HistoryReport,
    HistoryRoot,
)
from idhazh.contracts.host_output import (
    CandidateFileEnvelope,
    HostWriterIdentity,
    LegacyHostFingerprintRow,
    fingerprint_v1,
    host_file_id,
    host_unit_id,
)
from idhazh.contracts.ledger_index import CompactIndex, RawDayIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.ledger import json_lines
from idhazh.ledger.filenames import unit_id
from idhazh.telemetry.host_history_apply import (
    HistoryApplyBlockedError,
    _apply_prepared_batch,
    _ApplyBatch,
    _assert_exact_binding,
    _prepare_batch,
    _Replacement,
    _rollback_transaction,
    _run_transaction,
    apply_history,
)
from idhazh.telemetry.host_history_bundle import dry_run
from idhazh.telemetry.host_history_files import HistoryLimits
from idhazh.telemetry.host_output_verify import host_output_columns

pytestmark = pytest.mark.contract


class TransactionInterruptedError(RuntimeError):
    pass


def _batch(workspace: Path) -> _ApplyBatch:
    manifest_hash = "1" * 64
    scope_hash = "2" * 64
    evidence_hash = "3" * 64
    transaction_id = hashlib.sha256(
        f"{manifest_hash}\0{scope_hash}\0{evidence_hash}".encode("ascii")
    ).hexdigest()
    kinds = ("raw", "compact", "raw_index", "compact_index", "view")
    replacements = []
    for index, kind in enumerate(kinds):
        relative = (
            f"state/generated/{kind}/{index:02d}.json"
            if kind != "view"
            else "frontend/public/console/band.json"
        )
        target = workspace / Path(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        original = f"old-{kind}-{index}\n".encode("ascii")
        candidate = f"new-{kind}-{index}\n".encode("ascii")
        target.write_bytes(original)
        replacements.append(
            _Replacement(
                path=relative,
                kind=kind,
                old_sha256=hashlib.sha256(original).hexdigest(),
                old_bytes=len(original),
                new_bytes=candidate,
            )
        )
    writes = {
        item.path: item.new_sha256
        for item in replacements
    }
    evidence = {
        "candidate-maintenance-receipt.json": json.dumps(
            {"writes": writes}, sort_keys=True, separators=(",", ":")
        ).encode("ascii"),
        "original-receipts/evidence/old-invocation.json": b"old receipt bytes\n",
    }
    return _ApplyBatch(
        manifest=None,
        report=None,
        manifest_sha256=manifest_hash,
        scope_hash=scope_hash,
        report_evidence_hash=evidence_hash,
        transaction_id=transaction_id,
        transaction_root=f"backend/var/d17-tests/{transaction_id}",
        replacements=tuple(replacements),
        evidence=evidence,
    )


def _run(
    batch: _ApplyBatch,
    workspace: Path,
    *,
    interrupt: Callable[[str], None] | None = None,
) -> None:
    _run_transaction(
        batch,
        workspace=workspace,
        max_files=16,
        file_cap=8192,
        max_bytes=65536,
        reconcile=lambda: _reconcile_fixture(batch, workspace),
        interrupt=interrupt,
    )


def _reconcile_fixture(batch: _ApplyBatch, workspace: Path) -> None:
    """Check every generated tier, archived invocation receipt and current receipt."""
    for item in batch.replacements:
        data = (workspace / Path(*item.path.split("/"))).read_bytes()
        assert data == item.new_bytes
        assert hashlib.sha256(data).hexdigest() == item.new_sha256
    receipt = json.loads(
        (workspace / batch.transaction_root / "evidence" / "candidate-maintenance-receipt.json")
        .read_bytes()
    )
    assert receipt["writes"] == {
        item.path: item.new_sha256
        for item in batch.replacements
    }
    assert (
        workspace
        / batch.transaction_root
        / "evidence"
        / "original-receipts"
        / "evidence"
        / "old-invocation.json"
    ).read_bytes() == batch.evidence["original-receipts/evidence/old-invocation.json"]


PHASES = (
    "journal:plan-created",
    "journal:evidence-verified",
    "journal:backups-verified",
    "journal:staged-verified",
    "journal:planned:0",
    "after-replace-before-journal:0",
    "journal:replaced:0",
    "journal:verified:0",
    "journal:reconciled",
    "journal:complete",
)


@pytest.mark.parametrize("phase", PHASES)
def test_interruption_at_each_journal_phase_restarts_exact_batch(
    tmp_path: Path, phase: str
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    batch = _batch(workspace)
    interrupted = False

    def stop_at(requested: str) -> None:
        nonlocal interrupted
        if requested == phase and not interrupted:
            interrupted = True
            raise TransactionInterruptedError(phase)

    with pytest.raises(TransactionInterruptedError):
        _run(batch, workspace, interrupt=stop_at)
    assert interrupted
    _run(batch, workspace)
    assert all(
        (workspace / Path(*item.path.split("/"))).read_bytes() == item.new_bytes
        for item in batch.replacements
    )


def test_rollback_restores_exact_backups_and_is_idempotent(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    batch = _batch(workspace)
    with pytest.raises(TransactionInterruptedError):
        _run(batch, workspace, interrupt=_interrupt_once("after-replace-before-journal:0"))

    _rollback_transaction(
        batch,
        workspace=workspace,
        max_files=16,
        file_cap=8192,
        max_bytes=65536,
    )
    originals = [
        f"old-{item.kind}-{index}\n".encode("ascii")
        for index, item in enumerate(batch.replacements)
    ]
    assert [
        (workspace / Path(*item.path.split("/"))).read_bytes()
        for item in batch.replacements
    ] == originals
    _rollback_transaction(
        batch,
        workspace=workspace,
        max_files=16,
        file_cap=8192,
        max_bytes=65536,
    )


def test_corrupt_backup_refuses_restart_before_any_replacement(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    batch = _batch(workspace)
    with pytest.raises(TransactionInterruptedError):
        _run(batch, workspace, interrupt=_interrupt_once("journal:staged-verified"))
    backup = workspace / batch.transaction_root / "backups" / "00000.bin"
    backup.write_bytes(b"corrupt backup")
    with pytest.raises(ValueError, match="backup"):
        _run(batch, workspace)
    assert all(
        (workspace / Path(*item.path.split("/"))).read_bytes()
        == f"old-{item.kind}-{index}\n".encode("ascii")
        for index, item in enumerate(batch.replacements)
    )


def test_source_drift_is_rechecked_adjacent_to_atomic_replace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    batch = _batch(workspace)
    first = workspace / Path(*batch.replacements[0].path.split("/"))

    def drift(phase: str) -> None:
        if phase == "before-replace:0":
            first.write_bytes(b"third state")

    with pytest.raises(ValueError, match="immediately before replacement"):
        _run(batch, workspace, interrupt=drift)
    assert first.read_bytes() == b"third state"
    assert all(
        (workspace / Path(*item.path.split("/"))).read_bytes()
        == f"old-{item.kind}-{index}\n".encode("ascii")
        for index, item in enumerate(batch.replacements[1:], start=1)
    )


def test_restart_refuses_a_third_state_before_completing_more_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    batch = _batch(workspace)
    with pytest.raises(TransactionInterruptedError):
        _run(
            batch,
            workspace,
            interrupt=_interrupt_once("after-replace-before-journal:0"),
        )
    second = workspace / Path(*batch.replacements[1].path.split("/"))
    second.write_bytes(b"third state")
    with pytest.raises(ValueError, match="neither exact old nor exact new"):
        _run(batch, workspace)
    assert (
        workspace / Path(*batch.replacements[0].path.split("/"))
    ).read_bytes() == batch.replacements[0].new_bytes
    assert second.read_bytes() == b"third state"
    assert all(
        (workspace / Path(*item.path.split("/"))).read_bytes()
        == f"old-{item.kind}-{index}\n".encode("ascii")
        for index, item in enumerate(batch.replacements[2:], start=2)
    )


def test_path_escape_and_symlinked_history_ancestor_are_refused(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    batch = _batch(workspace)
    escaped = batch.replacements[0]
    batch = replace(
        batch,
        replacements=(
            _Replacement(
                path="../outside.json",
                kind=escaped.kind,
                old_sha256=escaped.old_sha256,
                old_bytes=escaped.old_bytes,
                new_bytes=escaped.new_bytes,
            ),
            *batch.replacements[1:],
        ),
    )
    with pytest.raises(ValueError, match="canonical relative"):
        _run(batch, workspace)

    other = tmp_path / "outside"
    other.mkdir()
    outside_target = other / "generated" / "raw" / "00.json"
    outside_target.parent.mkdir(parents=True)
    outside_target.write_bytes(b"symlink target")
    (workspace / "state").rename(workspace / "state-backup")
    (workspace / "state").symlink_to(other, target_is_directory=True)
    safe_batch = _batch_for_symlink(b"symlink target")
    with pytest.raises(ValueError, match=r"symlink|outside"):
        _run(safe_batch, workspace)


def _interrupt_once(expected: str) -> Callable[[str], None]:
    interrupted = False

    def stop(phase: str) -> None:
        nonlocal interrupted
        if phase == expected and not interrupted:
            interrupted = True
            raise TransactionInterruptedError(expected)

    return stop


def _batch_for_symlink(original: bytes) -> _ApplyBatch:
    manifest_hash = "4" * 64
    scope_hash = "5" * 64
    evidence_hash = "6" * 64
    transaction_id = hashlib.sha256(
        f"{manifest_hash}\0{scope_hash}\0{evidence_hash}".encode("ascii")
    ).hexdigest()
    return _ApplyBatch(
        manifest=None,
        report=None,
        manifest_sha256=manifest_hash,
        scope_hash=scope_hash,
        report_evidence_hash=evidence_hash,
        transaction_id=transaction_id,
        transaction_root=f"backend/var/d17-tests/{transaction_id}",
        replacements=(
            _Replacement(
                path="state/generated/raw/00.json",
                kind="raw",
                old_sha256=hashlib.sha256(original).hexdigest(),
                old_bytes=len(original),
                new_bytes=b"new raw",
            ),
        ),
        evidence={},
    )


def test_approval_mismatch_rejects_exact_manifest_and_scope_before_report_use() -> None:
    manifest = HistoryManifest(
        version="2026-10-11",
        converted_at="2026-10-11T12:00:00Z",
        invocation=HostWriterIdentity(
            run_id="2026-10-11-17",
            attempt=1,
            job=ServerJob.OPERATOR,
            shard=0,
            producer="utilities.migrate_host_fingerprints",
            git_sha="a" * 40,
        ),
        isolated_root="backend/var/d17-approval-fixture",
        range_start="2026-09-20",
        range_end="2026-09-20",
        roots=(
            HistoryRoot(
                name="production",
                kind="production",
                state_root="state",
                prefix=("host-fingerprint",),
            ),
        ),
        closed_periods=(
            ClosedHistoryPeriod(root="production", covers="2026-09-20", period=Period.DAILY),
        ),
        sources=(),
    )
    manifest_hash = hashlib.sha256(manifest.to_json().encode("ascii")).hexdigest()
    scope_hash = manifest.scope_hash()
    with pytest.raises(ValueError, match="manifest or scope"):
        _assert_exact_binding(
            manifest,
            cast(HistoryReport, None),
            approved_manifest_sha256="0" * 64,
            approved_scope_hash=scope_hash,
            approved_report_evidence_hash="7" * 64,
        )
    with pytest.raises(ValueError, match="manifest or scope"):
        _assert_exact_binding(
            manifest,
            cast(HistoryReport, None),
            approved_manifest_sha256=manifest_hash,
            approved_scope_hash="8" * 64,
            approved_report_evidence_hash="7" * 64,
        )


def test_live_apply_entrypoint_stays_closed_without_real_gate_infrastructure() -> None:
    with pytest.raises(HistoryApplyBlockedError, match="verified_d16_approval_record"):
        apply_history()


def _config_document(repo: Path) -> dict[str, Any]:
    experiment = json.loads(
        (repo / "config" / "host-telemetry-experiment.json").read_bytes()
    )
    migration = json.loads(
        (repo / "config" / "host-history-migration.json").read_bytes()
    )
    return {
        "verification_limits": experiment["verification_limits"],
        "history_migration_limits": migration["history_migration_limits"],
    }


def _add_source(
    workspace: Path,
    document: dict[str, Any],
    path: str,
    data: bytes,
    kind: str,
    *,
    dependencies: list[str] | None = None,
    covers: str | None = None,
    period: str | None = None,
) -> None:
    target = workspace / Path(*path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    sources = document["sources"]
    assert isinstance(sources, list)
    sources.append(
        {
            "root": "production",
            "path": path,
            "kind": kind,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "covers": covers,
            "period": period or ("daily" if covers else None),
            "dependencies": dependencies or [],
        }
    )


def _full_generated_history(workspace: Path) -> tuple[HistoryManifest, bytes]:
    day = "2026-09-20"
    manifest_document: dict[str, Any] = {
        "version": "2026-10-11",
        "converted_at": "2026-10-11T12:00:00Z",
        "invocation": {
            "run_id": "2026-10-11-17",
            "attempt": 1,
            "job": "operator",
            "shard": 0,
            "producer": "utilities.migrate_host_fingerprints",
            "git_sha": "a" * 40,
        },
        "isolated_root": "backend/var/d17-generated",
        "range_start": day,
        "range_end": day,
        "roots": [
            {
                "name": "production",
                "kind": "production",
                "state_root": "state",
                "prefix": ["host-fingerprint"],
            }
        ],
        "closed_periods": [{"root": "production", "covers": day, "period": "daily"}],
        "sources": [],
    }
    identity = HostWriterIdentity(
        run_id="2026-09-20-17",
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
        producer="telemetry.silicon",
        git_sha="b" * 40,
    )
    legacy = LegacyHostFingerprintRow.model_validate(
        {
            "version": "2026-09-20",
            "date": day,
            "run_id": identity.run_id,
            "job": "work",
            "shard": 0,
            "fingerprint": "0" * 16,
            "cpu_model": "Generated CPU",
            "measured_at": day + "T12:00:00Z",
            "cores": 2,
            "threads": 4,
            "mhz_max": 5000.0,
            "mhz_at_probe": 2300.0,
        }
    )
    row = legacy.model_dump(mode="json")
    row["fingerprint"] = fingerprint_v1(legacy)
    row = {
        column.name: row[column.name]
        for column in host_output_columns("2026-09-20")
        if column.name in row
    }
    unit = host_unit_id(covers=day, identity=identity)
    row.update(ledger=LedgerName.HOST_FINGERPRINT.value, covers=day, attempt=1, unit_id=str(unit))
    raw_clock = 1789905601000
    raw_file_id = host_file_id(unit=unit, attempt=1, written_at_ms=raw_clock)
    raw_envelope = CandidateFileEnvelope.model_validate(
        {
            "version": "2026-10-06",
            "row_schema_version": "2026-09-20",
            "tier": "raw",
            "ledger": "host-fingerprint",
            "covers": day,
            "written_at_ms": raw_clock,
            "identity": identity,
            "unit_id": unit,
            "file_id": raw_file_id,
            "content_sha256": hashlib.sha256(json_lines.rows_bytes([row])).hexdigest(),
            "writer": "idhazh.ledger.json_lines",
            "writer_version": json_lines.engine_version(),
            "compression": "none",
        }
    )
    raw_bytes = json_lines.render([row], envelope=raw_envelope.as_metadata())
    raw_path = f"state/raw/host-fingerprint/2026/09/20/{raw_file_id}.json"
    _add_source(workspace, manifest_document, raw_path, raw_bytes, "raw", covers=day)

    compact_identity = HostWriterIdentity(
        run_id=manifest_document["invocation"]["run_id"],
        attempt=1,
        job=ServerJob.OPERATOR,
        shard=0,
        producer="gardener.compact",
        git_sha="c" * 40,
    )
    compact_unit = unit_id(
        ledger="host-fingerprint",
        covers=day,
        run_id=compact_identity.run_id,
        job=compact_identity.job.value,
        shard=0,
        producer=compact_identity.producer,
    )
    compact_clock = raw_clock + 20 * 86400000
    compact_envelope = CandidateFileEnvelope.model_validate(
        {
            "version": "2026-10-06",
            "row_schema_version": "2026-09-20",
            "tier": "compact",
            "period": "daily",
            "ledger": "host-fingerprint",
            "covers": day,
            "written_at_ms": compact_clock,
            "identity": compact_identity,
            "unit_id": compact_unit,
            "file_id": host_file_id(
                unit=compact_unit, attempt=1, written_at_ms=compact_clock
            ),
            "content_sha256": hashlib.sha256(json_lines.rows_bytes([row])).hexdigest(),
            "writer": "idhazh.ledger.json_lines",
            "writer_version": json_lines.engine_version(),
            "compression": "none",
            "built_from": 1,
        }
    )
    compact_bytes = json_lines.render([row], envelope=compact_envelope.as_metadata())
    compact_path = "state/compact/host-fingerprint/daily/2026/09/20.json"
    _add_source(
        workspace,
        manifest_document,
        compact_path,
        compact_bytes,
        "compact",
        dependencies=[raw_path],
        covers=day,
    )
    raw_name = Path(raw_path).name
    raw_index = RawDayIndex.model_validate(
        {
            "ledger": "host-fingerprint",
            "date": day,
            "files": [raw_name],
            "bytes": [len(raw_bytes)],
            "content_sha256": hashlib.sha256(raw_name.encode("utf-8")).hexdigest(),
            "listed_at": "2026-10-01T12:00:00Z",
        }
    )
    raw_index_path = "state/raw/host-fingerprint/2026/09/20/index.json"
    _add_source(
        workspace,
        manifest_document,
        raw_index_path,
        raw_index.to_json().encode("ascii"),
        "raw_index",
        dependencies=[raw_path],
        covers=day,
    )
    compact_index = CompactIndex.model_validate(
        {
            "version": "2026-10-07",
            "ledger": "host-fingerprint",
            "period": "daily",
            "entries": [
                {
                    "covers": day,
                    "rows": 1,
                    "bytes": len(compact_bytes),
                    "state": "packed",
                    "lost_days": [],
                    "set_aside": 0,
                }
            ],
        }
    )
    compact_index_path = "state/compact/host-fingerprint/index/daily.json"
    _add_source(
        workspace,
        manifest_document,
        compact_index_path,
        compact_index.to_json().encode("ascii"),
        "compact_index",
        dependencies=[compact_path],
    )
    view_path = "frontend/public/console/band.json"
    view = ConsoleBand.model_validate(
        {
            "generated_at": "2026-10-01T12:00:00Z",
            "verdict": {"sentence": "Generated fixture.", "health": "green"},
            "size": {"sentence": "Generated fixture."},
        }
    )
    view_dependencies = [raw_path, compact_path, raw_index_path, compact_index_path]
    _add_source(
        workspace,
        manifest_document,
        view_path,
        view.to_json().encode("ascii"),
        "view",
        dependencies=view_dependencies,
    )
    source_documents = manifest_document["sources"]
    assert isinstance(source_documents, list)
    receipt_writes = {
        source["path"]: source["sha256"]
        for source in source_documents
        if source["path"] in view_dependencies
    }
    receipt = PublicationReceipt(
        version=PublicationReceipt.schema_version(),
        identity=HostWriterIdentity.model_validate(manifest_document["invocation"]),
        writes=receipt_writes,
    )
    receipt_path = "state/receipts/old-invocation.json"
    _add_source(
        workspace,
        manifest_document,
        receipt_path,
        receipt.to_json().encode("ascii"),
        "receipt",
        dependencies=list(receipt_writes),
    )
    return HistoryManifest.model_validate(manifest_document), receipt.to_json().encode("ascii")


def test_full_generated_raw_compact_index_receipt_view_batch_reconciles(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[2]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifest, old_receipt_bytes = _full_generated_history(workspace)
    config = _config_document(repo)
    limits = HistoryLimits.from_config(config)
    report = dry_run(manifest, workspace_root=workspace, config_document=config)
    assert report.historical_readiness == "ready"
    assert report.production_cutover_readiness == "blocked"

    names = {
        "manifest.json",
        "report.json",
        "candidate-maintenance-receipt.json",
        "consumer-replay.json",
        *(file.candidate_path for file in report.files if file.candidate_path is not None),
        *(
            "original-receipts/" + file.source.path
            for file in report.files
            if file.source.kind == "receipt"
        ),
    }
    bundle = workspace / Path(*report.bundle_root.split("/"))
    artifacts = {
        name: (bundle / Path(*name.split("/"))).read_bytes()
        for name in names
    }
    manifest_sha256 = hashlib.sha256(manifest.to_json().encode("ascii")).hexdigest()
    batch = _prepare_batch(
        manifest,
        report,
        artifacts,
        workspace=workspace,
        limits=limits,
        approved_manifest_sha256=manifest_sha256,
        approved_scope_hash=report.scope_hash,
        approved_report_evidence_hash=report.evidence_hash,
    )
    receipt_path = "state/receipts/old-invocation.json"
    _apply_prepared_batch(batch, workspace=workspace, limits=limits)

    assert (workspace / receipt_path).read_bytes() == old_receipt_bytes
    assert (workspace / batch.transaction_root / "events" / "complete.json").is_file()
    assert report.normalized_settled_keys == 1
