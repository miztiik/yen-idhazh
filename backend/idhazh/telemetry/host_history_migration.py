"""Prepare truthful historical replacement and reconciliation candidates without source writes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from idhazh.contracts.base import Contract, compact_json
from idhazh.contracts.file_envelope import FileEnvelope, Format, Period, RowIdentity, Tier
from idhazh.contracts.host_migration import (
    MIGRATION_VERSION,
    FileStatus,
    HistoryFileReport,
    HistoryManifest,
    HistoryReport,
    HistorySettlement,
    RowMigration,
)
from idhazh.contracts.host_output import (
    HOST_OUTPUT_VERSION,
    HostStoredRow,
    LegacyHostFingerprintRow,
)
from idhazh.contracts.ledger_index import CompactIndex, RawDayIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.ledger import json_lines, parquet, paths
from idhazh.ledger.keys import HOST_FINGERPRINT_KEY
from idhazh.ledger.persist import StoredRow
from idhazh.ledger.raw_files import settle_rows
from idhazh.telemetry.host_history_files import (
    HistoryFile,
    HistoryLimits,
    decode_history,
    read_history,
)
from idhazh.telemetry.host_history_paths import preflight_history
from idhazh.telemetry.host_output_verify import host_output_columns

LEGACY_CPU_FIELDS = ("cores", "threads", "mhz_max", "mhz_at_probe")
INDEX_VERSIONS = frozenset(
    {
        "2026-09-27",
        "2026-09-30",
        "2026-10-01",
        "2026-10-01T16:50",
        "2026-10-02",
        "2026-10-03",
        "2026-10-04",
        "2026-10-07",
    }
)


@dataclass(frozen=True)
class PreparedHistory:
    report: HistoryReport
    artifacts: dict[str, bytes]


def _identity(row: dict[str, Any]) -> RowIdentity:
    return RowIdentity.model_validate({key: row[key] for key in RowIdentity.model_fields})


def _record(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row[key]) for key in HOST_FINGERPRINT_KEY)


def _row_reports(file: HistoryFile) -> tuple[RowMigration, ...]:
    result: list[RowMigration] = []
    for original, normalized in zip(file.original_rows, file.rows, strict=True):
        new = normalized.model_dump(mode="json")
        result.append(
            RowMigration(
                original_version=original["version"],
                original_identity=_identity(original),
                normalized_identity=_identity(new),
                original_key=_record(original),
                normalized_key=_record(new),
                identity_repaired=_identity(original) != _identity(new),
                dropped_values={key: original[key] for key in LEGACY_CPU_FIELDS if key in original},
                null_fields=tuple(key for key, value in new.items() if value is None),
                retained_average=normalized.cpu_observed_mhz,
                original_fingerprint=original["fingerprint"],
                fingerprint_version=normalized.fingerprint_version,
            )
        )
    return tuple(result)


def _replace_file(file: HistoryFile) -> tuple[HistoryFileReport, bytes | None]:
    env = file.envelope
    source = file.source
    status: FileStatus = "retained"
    data: bytes | None = None
    candidate: str | None = None
    new_env: FileEnvelope | None = None
    diagnosis: str | None = None
    if env is not None:
        if file.container is None:
            raise ValueError("host envelope requires a decoded container")
        if env.row_schema_version == HOST_OUTPUT_VERSION:
            status = "excluded_corrected"
            diagnosis = "Already corrected; exact produced bytes are outside the rewrite set."
        else:
            status = "candidate_complete"
            new = env.model_dump()
            new.update(
                version=HOST_OUTPUT_VERSION,
                row_schema_version=HOST_OUTPUT_VERSION,
                content_sha256=hashlib.sha256(
                    json_lines.rows_bytes(row.model_dump(mode="json") for row in file.rows)
                ).hexdigest(),
                writer="idhazh.ledger.parquet"
                if file.container is Format.PARQUET
                else "idhazh.ledger.json_lines",
                writer_version=parquet.engine_version()
                if file.container is Format.PARQUET
                else json_lines.engine_version(),
            )
            new_env = FileEnvelope.model_validate(new)
            rows = [row.model_dump(mode="json") for row in file.rows]
            data = (
                parquet.render(
                    host_output_columns(HOST_OUTPUT_VERSION),
                    rows,
                    envelope=new_env.as_metadata(),
                    compression=new_env.compression,
                )
                if file.container is Format.PARQUET
                else json_lines.render(rows, envelope=new_env.as_metadata())
            )
            candidate = "candidates/" + source.path
    elif source.kind == "set_aside":
        status, diagnosis = (
            "unresolved",
            "Present set-aside source is not readable historical evidence.",
        )
    elif source.kind == "view":
        status, diagnosis = (
            "deferred",
            "Actual migrated machine/console consumer bytes are not available.",
        )
    return HistoryFileReport(
        source=source,
        status=status,
        candidate_path=candidate,
        old_physical_sha256=source.sha256,
        new_physical_sha256=hashlib.sha256(data).hexdigest() if data is not None else None,
        old_content_sha256=env.content_sha256 if env else None,
        new_content_sha256=new_env.content_sha256 if new_env else None,
        old_envelope=env,
        new_envelope=new_env,
        container=file.container.value
        if file.container
        else "csv"
        if source.kind == "view" and source.path.endswith(".csv")
        else "unknown"
        if source.kind == "set_aside"
        else "document",
        original_bytes=len(file.data),
        candidate_bytes=len(data) if data is not None else 0,
        row_count=len(file.rows),
        settled_key_count=len({_record(row) for row in file.original_rows}),
        rows=_row_reports(file),
        original_document=file.document,
        diagnosis=diagnosis,
    ), data


def _index_candidate(
    file: HistoryFile,
    sources: dict[str, HistoryFile],
    reports: dict[str, HistoryFileReport],
    manifest: HistoryManifest,
) -> bytes:
    document = file.document
    if document is None:
        raise ValueError("index source requires a decoded original document")
    if document["version"] not in INDEX_VERSIONS:
        raise ValueError(f"{file.source.path}: unknown original index version")
    source = file.source
    root = next(root for root in manifest.roots if root.name == source.root)
    registry = paths.overlay_registry(root.prefix[:-1])
    dependencies = set(source.dependencies)
    if source.kind == "raw_index":
        index = RawDayIndex.model_validate(document)
        expected = paths.raw_root(
            Path(root.state_root), LedgerName.HOST_FINGERPRINT, registry=registry
        ).joinpath(
            *index.date.split("-"),
            "index.json",
        )
        names = {str(expected.parent / name) for name in index.files}
        # Persisted paths are POSIX, independent of the local Path implementation.
        names = {Path(name).as_posix() for name in names}
        if (
            source.path != expected.as_posix()
            or index.date != source.covers
            or (index.ledger is not LedgerName.HOST_FINGERPRINT or names != dependencies)
        ):
            raise ValueError("raw index path/identity/dependencies contradict declared files")
        if index.content_sha256 != hashlib.sha256("\n".join(index.files).encode()).hexdigest():
            raise ValueError("raw index filename digest mismatch")
        sizes: list[int] = []
        for position, name in enumerate(index.files):
            path = (expected.parent / name).as_posix()
            held = sources[path]
            if held.source.kind != "raw" or held.source.root != source.root:
                raise ValueError("raw index dependency is not its own raw host source")
            if index.bytes is not None and index.bytes[position] != len(held.data):
                raise ValueError("raw index original bytes contradict source")
            report = reports[path]
            sizes.append(report.candidate_bytes if report.candidate_path else report.original_bytes)
        return (
            RawDayIndex.model_validate(index.model_dump() | {"bytes": sizes})
            .to_json()
            .encode("ascii")
        )
    compact_index = CompactIndex.model_validate(document)
    expected = paths.compact_index_path(
        Path(root.state_root), LedgerName.HOST_FINGERPRINT, compact_index.period, registry=registry
    )
    if (
        source.path != expected.as_posix()
        or compact_index.ledger is not LedgerName.HOST_FINGERPRINT
    ):
        raise ValueError("compact index path/ledger contradicts source root")
    closed = {(p.root, p.covers, p.period) for p in manifest.closed_periods}
    listed: set[str] = set()
    entries = []
    for entry in compact_index.entries:
        if (source.root, entry.covers, compact_index.period) not in closed:
            raise ValueError("compact index entry is not an explicitly closed period")
        matches = [
            held
            for held in sources.values()
            if held.source.kind == "compact"
            and held.source.root == source.root
            and held.source.covers == entry.covers
            and held.source.period == compact_index.period
        ]
        if not entry.names_file:
            if matches:
                raise ValueError("empty/lost index entry has a manifested compact file")
            entries.append(entry.model_dump())
            continue
        if len(matches) != 1:
            raise ValueError(f"{source.path}: packed index entry has missing/ambiguous source")
        held = matches[0]
        listed.add(held.source.path)
        if entry.rows != len(held.rows) or entry.bytes != len(held.data):
            raise ValueError("compact index original rows/bytes contradict source")
        if set(entry.lost_days).intersection(row.date for row in held.rows):
            raise ValueError("compact index lost days contradict actual compact rows")
        if len({_record(row) for row in held.original_rows}) != len(held.rows):
            raise ValueError("compact period contains unsettled duplicate keys")
        report = reports[held.source.path]
        entries.append(
            entry.model_dump()
            | {
                "bytes": report.candidate_bytes if report.candidate_path else report.original_bytes,
            }
        )
    if listed != dependencies:
        raise ValueError("compact index dependencies differ from its complete packed inventory")
    return (
        CompactIndex.model_validate(compact_index.model_dump() | {"entries": entries})
        .to_json()
        .encode("ascii")
    )


def _settlement_order(file: HistoryFile) -> tuple[int, int, str, int, str]:
    env = file.envelope
    if env is None:
        raise ValueError("settlement source requires its original envelope")
    return (
        1 if env.tier is Tier.RAW else 0,
        {Period.YEARLY: 0, Period.MONTHLY: 1, Period.DAILY: 2, None: 3}[env.period],
        env.covers,
        env.written_at_ms,
        str(env.file_id),
    )


def _reconcile_compact_inputs(file: HistoryFile, inputs: list[HistoryFile]) -> None:
    env = file.envelope
    if env is None or env.built_from != len(inputs):
        raise ValueError("declared compact dependencies require the complete original built_from")
    groups = [
        [
            StoredRow(identity=_identity(raw), row=row)
            for raw, row in zip(held.original_rows, held.rows, strict=True)
        ]
        for held in sorted(inputs, key=_settlement_order)
    ]
    original_by_row = {
        id(row): raw
        for held in inputs
        for raw, row in zip(held.original_rows, held.rows, strict=True)
    }
    expected = {
        _record(row.row.model_dump()): (
            row.row.model_dump(),
            {
                key: original_by_row[id(row.row)][key]
                for key in LEGACY_CPU_FIELDS
                if key in original_by_row[id(row.row)]
            },
        )
        for row in settle_rows(groups, HOST_FINGERPRINT_KEY)
    }
    actual = {
        _record(raw): (row.model_dump(), {key: raw[key] for key in LEGACY_CPU_FIELDS if key in raw})
        for raw, row in zip(file.original_rows, file.rows, strict=True)
    }
    if len(actual) != len(file.rows) or actual != expected:
        raise ValueError("compact original rows contradict whole-row dependency settlement")


def _settlement(
    files: tuple[HistoryFile, ...],
    manifest: HistoryManifest,
    *,
    original: bool = False,
) -> tuple[HistorySettlement, ...]:
    result: list[HistorySettlement] = []
    for root in manifest.roots:
        ordered = sorted(
            (f for f in files if f.source.root == root.name and f.envelope is not None),
            key=_settlement_order,
        )
        rows: list[list[StoredRow[Contract]]] = []
        for file in ordered:
            group: list[StoredRow[Contract]] = []
            for raw, corrected in zip(file.original_rows, file.rows, strict=True):
                if original and raw["version"] != HOST_OUTPUT_VERSION:
                    payload = {
                        key: value
                        for key, value in raw.items()
                        if key not in RowIdentity.model_fields or key in ("run_id", "job", "shard")
                    }
                    row: Contract = LegacyHostFingerprintRow.model_validate(payload)
                else:
                    row = HostStoredRow.model_validate(raw) if original else corrected
                group.append(StoredRow(identity=_identity(raw), row=row))
            rows.append(group)
        settled = settle_rows(rows, HOST_FINGERPRINT_KEY)
        locations = {
            id(row.row): file.source.path
            for file, group in zip(ordered, rows, strict=True)
            for row in group
        }
        for held in settled:
            result.append(
                HistorySettlement(
                    root=root.name,
                    source_path=locations[id(held.row)],
                    key=_record(held.row.model_dump()),
                    identity=held.identity,
                )
            )
    return tuple(result)


def prepare_history(
    manifest: HistoryManifest, *, workspace: Path, limits: HistoryLimits
) -> PreparedHistory:
    limits.check_manifest(manifest)
    preflight_history(manifest, workspace=workspace)
    roots = {root.name: root for root in manifest.roots}
    files = tuple(
        read_history(
            source,
            roots[source.root],
            workspace=workspace,
            limits=limits.history_verification,
        )
        for source in manifest.sources
    )
    if sum(len(file.rows) for file in files) > limits.max_history_rows:
        raise ValueError("complete inventory exceeds max_history_rows")
    by_path = {file.source.path: file for file in files}
    reports: dict[str, HistoryFileReport] = {}
    artifacts: dict[str, bytes] = {}
    for file in files:
        report, data = _replace_file(file)
        reports[file.source.path] = report
        if data is not None:
            if report.candidate_path is None:
                raise ValueError("replacement bytes require their isolated candidate path")
            checked = decode_history(
                file.source.model_copy(
                    update={"sha256": report.new_physical_sha256, "bytes": len(data)}
                ),
                roots[file.source.root],
                data=data,
                limits=limits.history_verification,
            )
            if checked.rows != file.rows:
                raise ValueError("replacement codec changed corrected rows")
            artifacts[report.candidate_path] = data
        if file.envelope is not None and file.envelope.tier is Tier.COMPACT:
            if not any(
                s.kind == "compact_index" and file.source.path in s.dependencies
                for s in manifest.sources
            ):
                raise ValueError("every compact file requires its manifested index entry")
            inputs: list[HistoryFile] = []
            for dependency in file.source.dependencies:
                original = by_path[dependency]
                if (
                    original.envelope is None
                    or original.source.root != file.source.root
                    or (
                        original.envelope.covers != file.envelope.covers
                        and not original.envelope.covers.startswith(file.envelope.covers + "-")
                    )
                ):
                    raise ValueError("compact dependency belongs to another root/period")
                inputs.append(original)
            if inputs:
                _reconcile_compact_inputs(file, inputs)
    for file in files:
        if file.source.kind not in ("raw_index", "compact_index"):
            continue
        data = _index_candidate(file, by_path, reports, manifest)
        previous = reports[file.source.path]
        candidate = "candidates/" + file.source.path
        reports[file.source.path] = HistoryFileReport.model_validate(
            previous.model_dump()
            | {
                "status": "candidate_complete",
                "candidate_path": candidate,
                "new_physical_sha256": hashlib.sha256(data).hexdigest(),
                "candidate_bytes": len(data),
                "candidate_document": json.loads(data),
            }
        )
        artifacts[candidate] = data
    deferred_receipts: list[str] = []
    for file in files:
        if file.source.kind == "view":
            if not file.source.path.startswith("frontend/public/") or not file.source.dependencies:
                raise ValueError("affected published view needs explicit host dependencies")
            if any(
                by_path[path].source.kind not in ("raw", "compact", "raw_index", "compact_index")
                or by_path[path].source.root != file.source.root
                for path in file.source.dependencies
            ):
                raise ValueError("view depends on foreign or non-host sources")
        if file.source.kind != "receipt":
            continue
        if file.document is None or file.document["version"] != PublicationReceipt.schema_version():
            raise ValueError("unrecognized original receipt version")
        receipt = PublicationReceipt.model_validate(file.document)
        if set(receipt.writes) != set(file.source.dependencies):
            raise ValueError("old receipt writes differ from exact manifested dependencies")
        for path, digest in receipt.writes.items():
            if by_path[path].source.sha256 != digest:
                raise ValueError("old receipt physical hashes contradict original sources")
        if any(by_path[path].source.kind == "view" for path in receipt.writes):
            deferred_receipts.append(file.source.path)
        artifacts["original-receipts/" + file.source.path] = file.data
    settlements = _settlement(files, manifest)
    original_settlements = _settlement(files, manifest, original=True)
    if settlements != original_settlements:
        raise ValueError("normalization changed whole-row settlement, rank or cardinality")
    views = tuple(file.source.path for file in files if file.source.kind == "view")
    unresolved = tuple(file.source.path for file in files if file.source.kind == "set_aside")
    writes = {
        path: report.new_physical_sha256
        for path, report in reports.items()
        if report.candidate_path is not None and report.new_physical_sha256 is not None
    }
    maintenance = PublicationReceipt(
        version=PublicationReceipt.schema_version(),
        identity=manifest.invocation,
        writes=writes,
    )
    artifacts["candidate-maintenance-receipt.json"] = maintenance.to_json().encode("ascii")
    artifacts["manifest.json"] = manifest.to_json().encode("ascii")
    payload: dict[str, Any] = {
        "version": MIGRATION_VERSION,
        "scope_hash": manifest.scope_hash(),
        "evidence_hash": "0" * 64,
        "bundle_root": manifest.isolated_root + "/" + manifest.scope_hash(),
        "manifest": manifest,
        "bounds": limits.report_bounds(),
        "inventory_complete": not unresolved,
        "consumer_mode": "candidate_reader",
        "raw_status": "candidate_complete"
        if any(f.source.kind == "raw" for f in files)
        else "not_applicable",
        "compact_status": "candidate_complete"
        if any(f.source.kind == "compact" for f in files)
        else "not_applicable",
        "index_status": "candidate_complete"
        if any(f.source.kind in ("raw_index", "compact_index") for f in files)
        else "not_applicable",
        "derived_views_status": "deferred" if views else "not_applicable",
        "receipt_status_raw_compact_indexes": "candidate_complete" if writes else "not_applicable",
        "receipt_status_derived_views": "deferred" if views else "not_applicable",
        "historical_readiness": "blocked",
        "blocked_by": (
            "actual_migrated_consumers_rerun_required",
            *(("derived_views_deferred",) if views else ()),
            *(("set_aside_sources_unresolved",) if unresolved else ()),
        ),
        "affected_view_paths": views,
        "deferred_receipt_paths": tuple(deferred_receipts),
        "files": tuple(reports[file.source.path] for file in files),
        "settlement": settlements,
        "original_settled_keys": len(original_settlements),
        "normalized_settled_keys": len(settlements),
        "maintenance_receipt_candidate": maintenance,
        "estimated_read_bytes": 2 * sum(len(f.data) for f in files),
        "estimated_candidate_bytes": sum(len(data) for data in artifacts.values()),
        "backup_policy": "verified_source_bytes_before_replace; retain_original_receipts",
        "retirement_policy": "no_source_retirement_in_dry_run",
    }
    provisional = HistoryReport.model_construct(**payload)
    evidence = provisional.model_dump(mode="json", exclude={"evidence_hash", "bundle_root"})
    evidence_hash = hashlib.sha256(compact_json(evidence).encode("ascii")).hexdigest()
    final_report = HistoryReport.model_validate(
        provisional.model_dump()
        | {
            "evidence_hash": evidence_hash,
            "bundle_root": manifest.isolated_root
            + "/"
            + manifest.scope_hash()
            + "/"
            + evidence_hash,
        }
    )
    artifacts["report.json"] = final_report.to_json().encode("ascii")
    if sum(len(data) for data in artifacts.values()) > limits.max_bundle_bytes:
        raise ValueError("complete dry-run bundle exceeds max_bundle_bytes")
    return PreparedHistory(final_report, artifacts)
