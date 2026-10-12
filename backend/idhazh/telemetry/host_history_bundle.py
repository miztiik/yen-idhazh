"""Publish only an isolated, immutable dry-run bundle after the complete source batch validates."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from idhazh import day_partition, ledger
from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.base import ServerJob, compact_json
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.host_migration import (
    ConsumerReplayEvidence,
    HistoryFileReport,
    HistoryManifest,
    HistoryReport,
)
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.console import ConsoleConfig
from idhazh.contracts.knobs.run import RunConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry.host_history_files import HistoryLimits, read_source
from idhazh.telemetry.host_history_migration import prepare_history
from idhazh.telemetry.host_history_paths import preflight_path, preflight_targets
from idhazh.telemetry.host_output_verify import _read_bytes, _safe_path
from idhazh.telemetry.publish import console_band


def dry_run(
    manifest: HistoryManifest, *, workspace_root: Path, config_document: dict[str, Any]
) -> HistoryReport:
    """No apply mode: source reads only, with exact retry/conflict checks on bundle bytes."""
    workspace = _safe_path(workspace_root.absolute(), workspace_root.absolute())
    limits = HistoryLimits.from_config(config_document)
    prepared = prepare_history(manifest, workspace=workspace, limits=limits)
    report, artifacts = _replay_migrated_consumers(
        prepared.report,
        prepared.artifacts,
        workspace=workspace,
    )
    bundle = workspace / report.bundle_root
    targets = [(bundle / name, data) for name, data in artifacts.items()]
    # Check the whole finite batch, including existing partial retries, before
    # creating its root. A malformed final source cannot leave a success bundle.
    preflight_targets(
        manifest, workspace=workspace, targets=tuple(target for target, _ in targets)
    )
    for target, data in targets:
        if (
            target.exists()
            and _read_bytes(target, root=workspace, cap=limits.max_bundle_bytes) != data
        ):
            raise ValueError("isolated dry-run bundle conflicts with the exact scoped evidence")
    for source in manifest.sources:
        read_source(source, workspace=workspace, limits=limits.verification)
    # The report is the completion marker and always comes last.
    targets.sort(key=lambda target: target[0].name == "report.json")
    for target, data in targets:
        if target.exists():
            if _read_bytes(target, root=workspace, cap=limits.max_bundle_bytes) != data:
                raise ValueError("existing bundle bytes changed after complete-batch preflight")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        preflight_path(workspace, target)
        staging = target.with_name("." + str(uuid4()) + ".pending")
        try:
            write_atomic_bytes(staging, data)
            try:
                os.link(staging, target)
            except FileExistsError:
                if _read_bytes(target, root=workspace, cap=limits.max_bundle_bytes) != data:
                    raise ValueError(
                        "isolated immutable bundle path raced with different bytes"
                    ) from None
        finally:
            staging.unlink(missing_ok=True)
        if _read_bytes(target, root=workspace, cap=limits.max_bundle_bytes) != data:
            raise ValueError("isolated candidate physical verification failed")
    return report


def _replay_migrated_consumers(
    report: HistoryReport,
    artifacts: dict[str, bytes],
    *,
    workspace: Path,
) -> tuple[HistoryReport, dict[str, bytes]]:
    """Run the real ledger and console consumers over only candidate bytes."""
    views = [file for file in report.files if file.source.kind == "view"]
    if not views:
        return report, artifacts
    if len(views) != 1 or views[0].source.path != "frontend/public/console/band.json":
        raise ValueError("consumer replay supports exactly the manifested console band view")
    view = views[0]
    candidate_files = [
        file
        for file in report.files
        if file.candidate_path is not None and file.source.kind != "view"
    ]
    with tempfile.TemporaryDirectory(prefix=".d16-consumer-", dir=workspace.parent) as raw_temp:
        consumer = Path(raw_temp)
        state = workspace / "state"
        if state.is_dir():
            shutil.copytree(state, consumer / "state")
        else:
            (consumer / "state").mkdir(parents=True)
        public = workspace / "frontend" / "public"
        if public.is_dir():
            shutil.copytree(public, consumer / "frontend" / "public")
        else:
            (consumer / "frontend" / "public").mkdir(parents=True)
        for file in candidate_files:
            if file.candidate_path is None:
                raise ValueError("consumer candidate is missing its isolated path")
            data = artifacts.get(file.candidate_path)
            if data is None:
                raise ValueError("consumer candidate bytes are missing from the dry-run batch")
            target = consumer / file.candidate_path.removeprefix("candidates/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        digest = consumer / "frontend" / "public" / "digest"
        digest.mkdir(parents=True, exist_ok=True)
        days = day_partition.days_in_window(
            report.manifest.range_end, max(ConsoleConfig().window_presets)
        )
        rows = ledger.load_days(
            consumer / "state",
            LedgerName.HOST_FINGERPRINT,
            days,
            model=HostFingerprintRow,
        )
        work_rows = [row for row in rows if row.job is ServerJob.WORK]
        console_band.publish(
            state_root=consumer / "state",
            digest_root=digest,
            generated_at=report.manifest.converted_at,
            today=date.fromisoformat(report.manifest.range_end),
            console=ConsoleConfig(),
            run=RunConfig(),
            collect=CollectConfig(),
        )
        view_target = consumer / view.source.path
        if not view_target.is_file():
            raise ValueError("console consumer did not generate the manifested view")
        view_bytes = view_target.read_bytes()
        json.loads(view_bytes)
        view_candidate = f"candidates/{view.source.path}"
        artifacts[view_candidate] = view_bytes
        replay = ConsumerReplayEvidence(
            reader="idhazh.ledger.load_days",
            publisher="idhazh.telemetry.publish.console_band.publish",
            input_mode="materialized_candidate_state",
            candidate_source_count=len(candidate_files),
            host_rows_read=len(rows),
            work_rows_read=len(work_rows),
            view_path=view.source.path,
            view_sha256=hashlib.sha256(view_bytes).hexdigest(),
            view_bytes=len(view_bytes),
        )
    view_report = HistoryFileReport.model_validate(
        view.model_dump(mode="python")
        | {
            "status": "candidate_complete",
            "candidate_path": view_candidate,
            "new_physical_sha256": replay.view_sha256,
            "candidate_bytes": replay.view_bytes,
            "candidate_document": json.loads(artifacts[view_candidate]),
        }
    )
    files = tuple(
        view_report if file.source.path == view.source.path else file
        for file in report.files
    )
    writes = {
        file.source.path: file.new_physical_sha256
        for file in files
        if file.candidate_path is not None and file.new_physical_sha256 is not None
    }
    maintenance = report.maintenance_receipt_candidate.model_copy(update={"writes": writes})
    artifacts["candidate-maintenance-receipt.json"] = maintenance.to_json().encode("ascii")
    deferred_receipts = report.deferred_receipt_paths
    remaining_blockers = tuple(
        blocker
        for blocker in report.blocked_by
        if blocker not in ("actual_migrated_consumers_rerun_required", "derived_views_deferred")
    )
    if deferred_receipts:
        remaining_blockers += ("derived_receipts_deferred",)
    provisional = report.model_copy(
        update={
            "consumer_mode": "migrated_consumers",
            "derived_views_status": "candidate_complete",
            "receipt_status_derived_views": (
                "deferred" if deferred_receipts else "candidate_complete"
            ),
            "historical_readiness": "ready" if not remaining_blockers else "blocked",
            "blocked_by": remaining_blockers,
            "files": files,
            "maintenance_receipt_candidate": maintenance,
            "consumer_replay": replay,
            "estimated_candidate_bytes": sum(len(data) for data in artifacts.values()),
        }
    )
    evidence = provisional.model_dump(mode="json", exclude={"evidence_hash", "bundle_root"})
    evidence_hash = hashlib.sha256(compact_json(evidence).encode("ascii")).hexdigest()
    final = HistoryReport.model_validate(
        provisional.model_dump()
        | {
            "evidence_hash": evidence_hash,
            "bundle_root": (
                f"{report.manifest.isolated_root}/{report.scope_hash}/{evidence_hash}"
            ),
        }
    )
    artifacts["report.json"] = final.to_json().encode("ascii")
    artifacts["consumer-replay.json"] = compact_json(
        replay.model_dump(mode="json")
    ).encode("ascii")
    return final, artifacts
