"""Publish only an isolated, immutable dry-run bundle after the complete source batch validates."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.host_migration import HistoryManifest, HistoryReport
from idhazh.telemetry.host_history_files import HistoryLimits, read_source
from idhazh.telemetry.host_history_migration import prepare_history
from idhazh.telemetry.host_history_paths import preflight_path, preflight_targets
from idhazh.telemetry.host_output_verify import _read_bytes, _safe_path


def dry_run(
    manifest: HistoryManifest, *, workspace_root: Path, config_document: dict[str, Any]
) -> HistoryReport:
    """No apply mode: source reads only, with exact retry/conflict checks on bundle bytes."""
    workspace = _safe_path(workspace_root.absolute(), workspace_root.absolute())
    limits = HistoryLimits.from_config(config_document)
    prepared = prepare_history(manifest, workspace=workspace, limits=limits)
    report = prepared.report
    bundle = workspace / report.bundle_root
    targets = [(bundle / name, data) for name, data in prepared.artifacts.items()]
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
