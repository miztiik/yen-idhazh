"""Prepare and journal a bounded host-history replacement; live apply stays gated."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from idhazh.atomic_write import write_atomic_bytes
from idhazh.contracts.base import compact_json
from idhazh.contracts.host_migration import HistoryManifest, HistoryReport
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.telemetry.host_history_files import HistoryLimits
from idhazh.telemetry.host_history_paths import preflight_history, preflight_path
from idhazh.telemetry.host_output_verify import _read_bytes, _safe_path

SHA256 = re.compile(r"^[0-9a-f]{64}$")
APPLY_BLOCKERS = (
    "verified_d16_approval_record_not_machine_representable",
    "operator_controlled_writer_compactor_publisher_quiet_window_provider_missing",
)
_JOURNAL_VERSION = 1


class HistoryApplyBlockedError(RuntimeError):
    """The live historical writer is intentionally unavailable without D16 gates."""


@dataclass(frozen=True)
class _Replacement:
    path: str
    kind: str
    old_sha256: str
    old_bytes: int
    new_bytes: bytes

    @property
    def new_sha256(self) -> str:
        return hashlib.sha256(self.new_bytes).hexdigest()


@dataclass(frozen=True)
class _ApplyBatch:
    manifest: HistoryManifest | None
    report: HistoryReport | None
    manifest_sha256: str
    scope_hash: str
    report_evidence_hash: str
    transaction_id: str
    transaction_root: str
    replacements: tuple[_Replacement, ...]
    evidence: Mapping[str, bytes]


def apply_history(*_args: Any, **_kwargs: Any) -> None:
    """Fail closed until D16 supplies a verifiable approval and a quiet-window lease."""
    raise HistoryApplyBlockedError(
        "historical apply is disabled: " + ", ".join(APPLY_BLOCKERS)
    )


def _require_temporary_fixture_workspace(workspace: Path) -> None:
    """Keep journal writes inside generated temporary fixtures until real gates exist."""
    blocked = HistoryApplyBlockedError(
        "transaction writes are disabled outside a generated temporary fixture root: "
        + ", ".join(APPLY_BLOCKERS)
    )
    temporary_path = Path(tempfile.gettempdir()).absolute()
    repository_root = Path(__file__).resolve().parents[3]
    workspace_path = workspace.absolute()
    if (
        workspace_path == temporary_path
        or not workspace_path.is_relative_to(temporary_path)
        or workspace_path == repository_root
        or workspace_path.is_relative_to(repository_root)
    ):
        raise blocked
    try:
        temporary_root = _safe_path(temporary_path, temporary_path)
        workspace_root = _safe_path(workspace_path, workspace_path)
    except (OSError, RuntimeError, ValueError) as error:
        raise blocked from error
    if (
        workspace_root == temporary_root
        or not workspace_root.is_relative_to(temporary_root)
        or workspace_root == repository_root
        or workspace_root.is_relative_to(repository_root)
        or not workspace_root.is_dir()
    ):
        raise blocked
    current = workspace_root
    while current != temporary_root:
        try:
            (current / ".git").lstat()
        except FileNotFoundError:
            current = current.parent
            continue
        except OSError as error:
            raise blocked from error
        raise blocked


def _json_bytes(document: object) -> bytes:
    text = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n"
    return text.encode("ascii")


def _relative_parts(value: str) -> tuple[str, ...]:
    if (
        not value
        or "\\" in value
        or ":" in value
        or value.startswith("/")
        or value != PurePosixPath(value).as_posix()
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValueError("transaction path must be a canonical relative POSIX path")
    return tuple(value.split("/"))


def _sha256(value: str, name: str) -> None:
    if not SHA256.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256")


def _path(workspace: Path, relative: str) -> Path:
    return workspace.joinpath(*_relative_parts(relative))


def _mkdir_checked(workspace: Path, directory: Path) -> None:
    if not directory.is_relative_to(workspace):
        raise ValueError("transaction directory is outside the workspace")
    relative = directory.relative_to(workspace)
    current = workspace
    for part in relative.parts:
        current = current / part
        preflight_path(workspace, current)
        try:
            current.mkdir()
        except FileExistsError:
            info = current.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("transaction path ancestor is not a directory") from None
        preflight_path(workspace, current)


def _maybe_read(path: Path, *, workspace: Path, cap: int) -> bytes | None:
    try:
        return _read_bytes(path, root=workspace, cap=cap)
    except FileNotFoundError:
        return None


def _write_once(path: Path, data: bytes, *, workspace: Path, cap: int) -> None:
    if len(data) > cap:
        raise ValueError("transaction artifact exceeds its byte limit")
    _mkdir_checked(workspace, path.parent)
    preflight_path(workspace, path)
    existing = _maybe_read(path, workspace=workspace, cap=cap)
    if existing is not None:
        if existing != data:
            raise ValueError(f"immutable transaction artifact conflicts: {path.name}")
        return
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.pending")
    preflight_path(workspace, temporary)
    try:
        write_atomic_bytes(temporary, data)
        if _read_bytes(temporary, root=workspace, cap=cap) != data:
            raise ValueError("transaction temporary bytes failed verification")
        try:
            os.link(temporary, path)
        except FileExistsError:
            if _read_bytes(path, root=workspace, cap=cap) != data:
                raise ValueError("immutable transaction path raced with different bytes") from None
        if _read_bytes(path, root=workspace, cap=cap) != data:
            raise ValueError("immutable transaction artifact failed physical verification")
    finally:
        temporary.unlink(missing_ok=True)


def _assert_exact_binding(
    manifest: HistoryManifest,
    report: HistoryReport,
    *,
    approved_manifest_sha256: str,
    approved_scope_hash: str,
    approved_report_evidence_hash: str,
) -> tuple[str, str]:
    """Bind the engine to the exact D16 manifest, scope and report, never a re-stamped scope."""
    manifest_bytes = manifest.to_json().encode("ascii")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    scope_hash = manifest.scope_hash()
    _sha256(approved_manifest_sha256, "approved manifest hash")
    _sha256(approved_scope_hash, "approved scope hash")
    _sha256(approved_report_evidence_hash, "approved D16 report evidence hash")
    if (
        manifest_sha256 != approved_manifest_sha256
        or scope_hash != approved_scope_hash
    ):
        raise ValueError("manifest or scope differs from the exact D16 approval")
    validated = HistoryReport.model_validate(report.model_dump(mode="json"))
    if validated.manifest.to_json().encode("ascii") != manifest_bytes:
        raise ValueError("D16 report does not name the exact supplied manifest bytes")
    if validated.scope_hash != approved_scope_hash:
        raise ValueError("D16 report scope differs from the exact approval")
    if validated.evidence_hash != approved_report_evidence_hash:
        raise ValueError("D16 report evidence differs from the exact approval")
    if (
        validated.historical_readiness != "ready"
        or not validated.inventory_complete
        or validated.consumer_mode != "migrated_consumers"
        or validated.blocked_by
        or validated.deferred_receipt_paths
    ):
        raise ValueError("D16 historical readiness is not complete for this exact scope")
    return manifest_sha256, scope_hash


def _prepare_batch(
    manifest: HistoryManifest,
    report: HistoryReport,
    artifacts: Mapping[str, bytes],
    *,
    workspace: Path,
    limits: HistoryLimits,
    approved_manifest_sha256: str,
    approved_scope_hash: str,
    approved_report_evidence_hash: str,
) -> _ApplyBatch:
    """Validate the exact D16 dry-run bundle and create a fixed, bounded write set."""
    workspace = workspace.absolute()
    _safe_path(workspace, workspace)
    limits.check_manifest(manifest)
    manifest_sha256, scope_hash = _assert_exact_binding(
        manifest,
        report,
        approved_manifest_sha256=approved_manifest_sha256,
        approved_scope_hash=approved_scope_hash,
        approved_report_evidence_hash=approved_report_evidence_hash,
    )
    if artifacts.get("manifest.json") != manifest.to_json().encode("ascii"):
        raise ValueError("dry-run bundle manifest bytes do not match the approved manifest")
    if artifacts.get("report.json") != report.to_json().encode("ascii"):
        raise ValueError("dry-run bundle report bytes do not match the D16 report")
    if report.consumer_replay is None:
        raise ValueError("D16 approval requires migrated-consumer replay evidence")
    views = [file for file in report.files if file.source.kind == "view"]
    if len(views) != 1 or report.consumer_replay.view_path != views[0].source.path:
        raise ValueError("D16 replay must name exactly one manifested published view")
    replay_bytes = artifacts.get("consumer-replay.json")
    expected_replay = compact_json(report.consumer_replay.model_dump(mode="json")).encode("ascii")
    if replay_bytes is None:
        raise ValueError("D16 migrated-consumer replay artifact is missing")
    if replay_bytes != expected_replay:
        raise ValueError("D16 migrated-consumer replay differs from its report")

    replacements: list[_Replacement] = []
    expected_artifacts = {
        "manifest.json",
        "report.json",
        "candidate-maintenance-receipt.json",
        "consumer-replay.json",
    }
    for file in report.files:
        source = file.source
        if file.status in ("unresolved", "deferred"):
            raise ValueError(f"{source.path}: unresolved or deferred source blocks apply")
        if source.kind in ("raw", "compact") and file.status not in (
            "candidate_complete",
            "excluded_corrected",
        ):
            raise ValueError(f"{source.path}: raw/compact source has no validated final state")
        if source.kind in ("raw_index", "compact_index", "view") and (
            file.status != "candidate_complete"
        ):
            raise ValueError(f"{source.path}: index/view must have an exact replacement candidate")
        if file.status == "candidate_complete":
            candidate = file.candidate_path
            if candidate is None or candidate != "candidates/" + source.path:
                raise ValueError(
                    f"{source.path}: candidate path differs from the exact source path"
                )
            data = artifacts.get(candidate)
            if (
                data is None
                or file.new_physical_sha256 is None
                or len(data) != file.candidate_bytes
                or hashlib.sha256(data).hexdigest() != file.new_physical_sha256
            ):
                raise ValueError(f"{source.path}: staged candidate bytes differ from D16 evidence")
            if len(data) > limits.verification.max_file_bytes:
                raise ValueError(f"{source.path}: candidate exceeds the file byte limit")
            replacements.append(
                _Replacement(
                    path=source.path,
                    kind=source.kind,
                    old_sha256=source.sha256,
                    old_bytes=source.bytes,
                    new_bytes=data,
                )
            )
            expected_artifacts.add(candidate)
        elif file.candidate_path is not None or file.new_physical_sha256 is not None:
            raise ValueError(f"{source.path}: non-replacement source claims candidate bytes")
        if source.kind == "receipt":
            archive = "original-receipts/" + source.path
            old_receipt = artifacts.get(archive)
            if (
                file.status != "retained"
                or old_receipt is None
                or len(old_receipt) != source.bytes
                or hashlib.sha256(old_receipt).hexdigest() != source.sha256
            ):
                raise ValueError(f"{source.path}: original receipt is not preserved exactly")
            expected_artifacts.add(archive)
    if not replacements:
        raise ValueError("D16 report has no exact candidate replacements")
    kinds = {replacement.kind for replacement in replacements}
    if "view" in kinds and (
        report.consumer_replay.view_path not in report.affected_view_paths
        or report.consumer_replay.view_sha256
        != next(item.new_sha256 for item in replacements if item.kind == "view")
    ):
        raise ValueError("regenerated view differs from migrated-consumer replay evidence")
    if artifacts.get("candidate-maintenance-receipt.json") != (
        report.maintenance_receipt_candidate.to_json().encode("ascii")
    ):
        raise ValueError("candidate maintenance receipt differs from the D16 report")
    receipt = PublicationReceipt.model_validate(
        json.loads(artifacts["candidate-maintenance-receipt.json"])
    )
    if receipt != report.maintenance_receipt_candidate:
        raise ValueError("candidate maintenance receipt failed contract validation")
    if set(artifacts) != expected_artifacts:
        raise ValueError("dry-run bundle contains missing or unmanifested transaction artifacts")
    if sum(len(data) for data in artifacts.values()) > limits.max_bundle_bytes:
        raise ValueError("D16 bundle and journal evidence exceed the bundle byte limit")
    transaction_id = hashlib.sha256(
        f"{manifest_sha256}\0{scope_hash}\0{report.evidence_hash}".encode("ascii")
    ).hexdigest()
    transaction_root = (
        f"{manifest.isolated_root}/d17-transactions/{transaction_id}"
    )
    _relative_parts(transaction_root)
    preflight_history(manifest, workspace=workspace)
    candidate_names = {
        file.candidate_path for file in report.files if file.candidate_path is not None
    }
    evidence_names = expected_artifacts - candidate_names
    return _ApplyBatch(
        manifest=manifest,
        report=report,
        manifest_sha256=manifest_sha256,
        scope_hash=scope_hash,
        report_evidence_hash=report.evidence_hash,
        transaction_id=transaction_id,
        transaction_root=transaction_root,
        replacements=tuple(replacements),
        evidence={name: artifacts[name] for name in sorted(evidence_names)},
    )


def _transaction_plan(
    batch: _ApplyBatch, *, max_files: int, max_bytes: int
) -> bytes:
    if len(batch.replacements) > max_files:
        raise ValueError("transaction exceeds the file-count bound")
    if sum(len(item.new_bytes) for item in batch.replacements) + sum(
        len(data) for data in batch.evidence.values()
    ) > max_bytes:
        raise ValueError("transaction exceeds the staged-byte bound")
    return _json_bytes(
        {
            "version": _JOURNAL_VERSION,
            "transaction_id": batch.transaction_id,
            "manifest_sha256": batch.manifest_sha256,
            "scope_hash": batch.scope_hash,
            "report_evidence_hash": batch.report_evidence_hash,
            "files": [
                {
                    "index": index,
                    "path": item.path,
                    "kind": item.kind,
                    "old_sha256": item.old_sha256,
                    "old_bytes": item.old_bytes,
                    "new_sha256": item.new_sha256,
                    "new_bytes": len(item.new_bytes),
                    "backup": f"backups/{index:05d}.bin",
                    "stage": f".d17-{batch.transaction_id[:12]}-{index:05d}.stage",
                }
                for index, item in enumerate(batch.replacements)
            ],
            "evidence": [
                {
                    "path": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data),
                }
                for name, data in sorted(batch.evidence.items())
            ],
        }
    )


def _event_bytes(batch: _ApplyBatch, phase: str, index: int | None = None) -> bytes:
    item = batch.replacements[index] if index is not None else None
    return _json_bytes(
        {
            "version": _JOURNAL_VERSION,
            "transaction_id": batch.transaction_id,
            "manifest_sha256": batch.manifest_sha256,
            "scope_hash": batch.scope_hash,
            "report_evidence_hash": batch.report_evidence_hash,
            "phase": phase,
            "index": index,
            "path": item.path if item else None,
            "old_sha256": item.old_sha256 if item else None,
            "new_sha256": item.new_sha256 if item else None,
        }
    )


def _record_event(
    batch: _ApplyBatch,
    phase: str,
    *,
    workspace: Path,
    cap: int,
    index: int | None = None,
    interrupt: Callable[[str], None] | None = None,
) -> None:
    suffix = f"-{index:05d}" if index is not None else ""
    name = f"{phase}{suffix}.json"
    target = _path(workspace, f"{batch.transaction_root}/events/{name}")
    data = _event_bytes(batch, phase, index)
    before = _maybe_read(target, workspace=workspace, cap=cap)
    _write_once(target, data, workspace=workspace, cap=cap)
    if before is None and interrupt is not None:
        interrupt(f"journal:{phase}" + (f":{index}" if index is not None else ""))


def _phase_exists(batch: _ApplyBatch, phase: str, *, workspace: Path, cap: int) -> bool:
    target = _path(workspace, f"{batch.transaction_root}/events/{phase}.json")
    return _maybe_read(target, workspace=workspace, cap=cap) is not None


def _check_existing_events(batch: _ApplyBatch, *, workspace: Path, cap: int) -> None:
    events = _path(workspace, f"{batch.transaction_root}/events")
    if not events.exists():
        return
    allowed = {
        "plan-created.json",
        "backups-verified.json",
        "staged-verified.json",
        "evidence-verified.json",
        "reconciled.json",
        "complete.json",
        "rollback-started.json",
        "rolled-back.json",
        *(
            f"{phase}-{index:05d}.json"
            for phase in ("planned", "replaced", "verified", "restored", "rollback-verified")
            for index in range(len(batch.replacements))
        ),
    }
    _safe_path(workspace, events)
    entries = list(events.iterdir())
    if len(entries) > len(allowed) or any(entry.name not in allowed for entry in entries):
        raise ValueError("transaction journal contains an unknown or unbounded event")
    for name in allowed.intersection(entry.name for entry in entries):
        match = re.fullmatch(
            r"(planned|replaced|verified|restored|rollback-verified)-(\d{5})\.json",
            name,
        )
        if match:
            phase, raw_index = match.groups()
            index = int(raw_index)
            event_path = f"{batch.transaction_root}/events/{name}"
            existing = _read_bytes(_path(workspace, event_path), root=workspace, cap=cap)
            if existing != _event_bytes(batch, phase, index):
                raise ValueError("transaction journal event differs from the immutable plan")
        else:
            phase = name.removesuffix(".json")
            existing = _read_bytes(
                _path(workspace, f"{batch.transaction_root}/events/{name}"),
                root=workspace,
                cap=cap,
            )
            if existing != _event_bytes(batch, phase):
                raise ValueError("transaction journal phase differs from the immutable plan")


def _validate_batch_paths(batch: _ApplyBatch, *, workspace: Path) -> None:
    workspace = workspace.absolute()
    _safe_path(workspace, workspace)
    _sha256(batch.transaction_id, "transaction id")
    _sha256(batch.manifest_sha256, "manifest hash")
    _sha256(batch.scope_hash, "scope hash")
    _sha256(batch.report_evidence_hash, "report evidence hash")
    expected_id = hashlib.sha256(
        f"{batch.manifest_sha256}\0{batch.scope_hash}\0{batch.report_evidence_hash}".encode(
            "ascii"
        )
    ).hexdigest()
    if batch.transaction_id != expected_id:
        raise ValueError("transaction id does not bind the exact manifest, scope and evidence")
    if batch.report is not None and batch.report.evidence_hash != batch.report_evidence_hash:
        raise ValueError("transaction report evidence hash differs from the validated report")
    if batch.manifest is not None and batch.transaction_root != (
        f"{batch.manifest.isolated_root}/d17-transactions/{batch.transaction_id}"
    ):
        raise ValueError("transaction root is not the task-owned root for this manifest")
    tx_parts = _relative_parts(batch.transaction_root)
    tx_path = _path(workspace, batch.transaction_root)
    preflight_path(workspace, tx_path)
    paths: set[str] = set()
    addresses: set[tuple[int, int]] = set()
    for item in batch.replacements:
        parts = _relative_parts(item.path)
        if item.path in paths:
            raise ValueError("transaction repeats a manifested source path")
        paths.add(item.path)
        if parts[: len(tx_parts)] == tx_parts or tx_parts[: len(parts)] == parts:
            raise ValueError("transaction journal overlaps a manifested source")
        _sha256(item.old_sha256, "original source hash")
        if item.old_bytes < 0 or len(item.new_bytes) == 0:
            raise ValueError("transaction source/candidate sizes are invalid")
        _sha256(item.new_sha256, "candidate hash")
        target = _path(workspace, item.path)
        preflight_path(workspace, target)
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("transaction source must be a regular file")
        address = (info.st_dev, info.st_ino)
        if address in addresses:
            raise ValueError("transaction sources alias the same physical file")
        addresses.add(address)
        stage = target.with_name(f".d17-{batch.transaction_id[:12]}-{len(paths) - 1:05d}.stage")
        preflight_path(workspace, stage)
    for relative in batch.evidence:
        _relative_parts(relative)


def _backup_path(batch: _ApplyBatch, index: int, workspace: Path) -> Path:
    return _path(workspace, f"{batch.transaction_root}/backups/{index:05d}.bin")


def _stage_path(batch: _ApplyBatch, index: int, workspace: Path) -> Path:
    item = batch.replacements[index]
    target = _path(workspace, item.path)
    return target.with_name(f".d17-{batch.transaction_id[:12]}-{index:05d}.stage")


def _old_bytes(
    batch: _ApplyBatch, index: int, *, workspace: Path, cap: int
) -> bytes:
    item = batch.replacements[index]
    backup = _maybe_read(_backup_path(batch, index, workspace), workspace=workspace, cap=cap)
    if (
        backup is None
        or len(backup) != item.old_bytes
        or hashlib.sha256(backup).hexdigest() != item.old_sha256
    ):
        raise ValueError(f"{item.path}: verified source backup is missing or corrupt")
    return backup


def _ensure_backups_and_stages(
    batch: _ApplyBatch,
    *,
    workspace: Path,
    file_cap: int,
    interrupt: Callable[[str], None] | None,
) -> None:
    for index, item in enumerate(batch.replacements):
        target = _path(workspace, item.path)
        current = _read_bytes(target, root=workspace, cap=file_cap)
        old_matches = (
            len(current) == item.old_bytes
            and hashlib.sha256(current).hexdigest() == item.old_sha256
        )
        new_matches = current == item.new_bytes
        if not old_matches and not new_matches:
            raise ValueError(f"{item.path}: source is neither exact old nor exact new bytes")
        backup_path = _backup_path(batch, index, workspace)
        backup = _maybe_read(backup_path, workspace=workspace, cap=file_cap)
        if backup is None:
            if not old_matches:
                raise ValueError(f"{item.path}: replacement exists without its verified backup")
            _write_once(backup_path, current, workspace=workspace, cap=file_cap)
            backup = _read_bytes(backup_path, root=workspace, cap=file_cap)
            if (
                len(backup) != item.old_bytes
                or hashlib.sha256(backup).hexdigest() != item.old_sha256
            ):
                raise ValueError(f"{item.path}: source-byte backup failed verification")
            if interrupt is not None:
                interrupt(f"backup:{index}")
        if len(backup) != item.old_bytes or hashlib.sha256(backup).hexdigest() != item.old_sha256:
            raise ValueError(f"{item.path}: verified source backup is corrupt")
        if old_matches and current != backup:
            raise ValueError(f"{item.path}: source differs from its exact original backup")
        stage = _stage_path(batch, index, workspace)
        staged = _maybe_read(stage, workspace=workspace, cap=file_cap)
        if old_matches:
            if staged is None:
                _write_once(stage, item.new_bytes, workspace=workspace, cap=file_cap)
                staged = _read_bytes(stage, root=workspace, cap=file_cap)
                if interrupt is not None:
                    interrupt(f"stage:{index}")
            if staged != item.new_bytes:
                raise ValueError(f"{item.path}: destination-local staged output is corrupt")
            stage_info = stage.stat()
            if (stage_info.st_dev, stage_info.st_ino) in addresses_for(batch, workspace):
                raise ValueError(f"{item.path}: destination-local stage aliases a source")
        elif staged is not None and staged != item.new_bytes:
            raise ValueError(f"{item.path}: stale destination-local stage conflicts")


def addresses_for(batch: _ApplyBatch, workspace: Path) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for item in batch.replacements:
        info = _path(workspace, item.path).stat()
        result.add((info.st_dev, info.st_ino))
    return result


def _preflight_current_states(
    batch: _ApplyBatch, *, workspace: Path, file_cap: int
) -> None:
    states: list[str] = []
    for index, item in enumerate(batch.replacements):
        current = _read_bytes(_path(workspace, item.path), root=workspace, cap=file_cap)
        backup = _old_bytes(batch, index, workspace=workspace, cap=file_cap)
        if current == item.new_bytes:
            states.append("new")
        elif current == backup:
            states.append("old")
        else:
            raise ValueError(
                f"{item.path}: restart refuses bytes other than exact old or exact new"
            )
    if len(states) != len(batch.replacements):
        raise ValueError("transaction state inventory is incomplete")


def _run_transaction(
    batch: _ApplyBatch,
    *,
    workspace: Path,
    max_files: int,
    file_cap: int,
    max_bytes: int,
    reconcile: Callable[[], None],
    interrupt: Callable[[str], None] | None = None,
) -> None:
    """Run the journal only for generated temporary fixtures; live writes stay blocked."""
    _require_temporary_fixture_workspace(workspace)
    workspace = workspace.absolute()
    _validate_batch_paths(batch, workspace=workspace)
    plan = _transaction_plan(batch, max_files=max_files, max_bytes=max_bytes)
    if len(plan) > file_cap:
        raise ValueError("immutable transaction plan exceeds its byte bound")
    root = _path(workspace, batch.transaction_root)
    plan_path = root / "plan.json"
    existing_plan = _maybe_read(plan_path, workspace=workspace, cap=file_cap)
    if existing_plan is not None and existing_plan != plan:
        raise ValueError("immutable transaction plan conflicts with this exact D16 batch")
    _mkdir_checked(workspace, root)
    _write_once(plan_path, plan, workspace=workspace, cap=file_cap)
    _check_existing_events(batch, workspace=workspace, cap=file_cap)
    if _phase_exists(batch, "complete", workspace=workspace, cap=file_cap):
        _preflight_current_states(batch, workspace=workspace, file_cap=file_cap)
        if any(
            _read_bytes(_path(workspace, item.path), root=workspace, cap=file_cap) != item.new_bytes
            for item in batch.replacements
        ):
            raise ValueError("completed transaction no longer has exact replacement bytes")
        reconcile()
        return
    if _phase_exists(batch, "rolled-back", workspace=workspace, cap=file_cap):
        raise ValueError("transaction was rolled back and cannot be completed")
    if _phase_exists(batch, "rollback-started", workspace=workspace, cap=file_cap):
        raise ValueError("transaction rollback is in progress; resume rollback instead")

    _record_event(batch, "plan-created", workspace=workspace, cap=file_cap, interrupt=interrupt)
    for name, data in batch.evidence.items():
        _write_once(
            _path(workspace, f"{batch.transaction_root}/evidence/{name}"),
            data,
            workspace=workspace,
            cap=max(file_cap, len(data)),
        )
        if _read_bytes(
            _path(workspace, f"{batch.transaction_root}/evidence/{name}"),
            root=workspace,
            cap=max(file_cap, len(data)),
        ) != data:
            raise ValueError(f"{name}: immutable D16 evidence copy failed verification")
    _record_event(
        batch,
        "evidence-verified",
        workspace=workspace,
        cap=file_cap,
        interrupt=interrupt,
    )
    _ensure_backups_and_stages(
        batch,
        workspace=workspace,
        file_cap=file_cap,
        interrupt=interrupt,
    )
    _record_event(batch, "backups-verified", workspace=workspace, cap=file_cap, interrupt=interrupt)
    _record_event(batch, "staged-verified", workspace=workspace, cap=file_cap, interrupt=interrupt)
    _preflight_current_states(batch, workspace=workspace, file_cap=file_cap)
    for index in range(len(batch.replacements)):
        _record_event(
            batch,
            "planned",
            index=index,
            workspace=workspace,
            cap=file_cap,
            interrupt=interrupt,
        )

    for index, item in enumerate(batch.replacements):
        target = _path(workspace, item.path)
        stage = _stage_path(batch, index, workspace)
        current = _read_bytes(target, root=workspace, cap=file_cap)
        if current != item.new_bytes:
            if interrupt is not None:
                interrupt(f"before-replace:{index}")
            # This exact byte/hash check is deliberately adjacent to os.replace.
            current = _read_bytes(target, root=workspace, cap=file_cap)
            old = _old_bytes(batch, index, workspace=workspace, cap=file_cap)
            if current != old or len(current) != item.old_bytes or (
                hashlib.sha256(current).hexdigest() != item.old_sha256
            ):
                raise ValueError(f"{item.path}: source hash drifted immediately before replacement")
            if _read_bytes(stage, root=workspace, cap=file_cap) != item.new_bytes:
                raise ValueError(f"{item.path}: destination-local staged output changed")
            stage.replace(target)
            if interrupt is not None:
                interrupt(f"after-replace-before-journal:{index}")
        if _read_bytes(target, root=workspace, cap=file_cap) != item.new_bytes:
            raise ValueError(f"{item.path}: replacement failed exact-byte verification")
        _record_event(
            batch,
            "replaced",
            index=index,
            workspace=workspace,
            cap=file_cap,
            interrupt=interrupt,
        )
        if _read_bytes(target, root=workspace, cap=file_cap) != item.new_bytes:
            raise ValueError(f"{item.path}: verified replacement changed")
        _record_event(
            batch,
            "verified",
            index=index,
            workspace=workspace,
            cap=file_cap,
            interrupt=interrupt,
        )
    _preflight_current_states(batch, workspace=workspace, file_cap=file_cap)
    reconcile()
    _record_event(batch, "reconciled", workspace=workspace, cap=file_cap, interrupt=interrupt)
    _record_event(batch, "complete", workspace=workspace, cap=file_cap, interrupt=interrupt)


def _rollback_transaction(
    batch: _ApplyBatch,
    *,
    workspace: Path,
    max_files: int,
    file_cap: int,
    max_bytes: int,
    interrupt: Callable[[str], None] | None = None,
) -> None:
    """Restore only exact new bytes from verified backups; never overwrite a third state."""
    _require_temporary_fixture_workspace(workspace)
    workspace = workspace.absolute()
    _validate_batch_paths(batch, workspace=workspace)
    plan = _transaction_plan(batch, max_files=max_files, max_bytes=max_bytes)
    root = _path(workspace, batch.transaction_root)
    existing_plan = _maybe_read(root / "plan.json", workspace=workspace, cap=file_cap)
    if existing_plan is None or existing_plan != plan:
        raise ValueError("rollback has no exact immutable transaction plan")
    _check_existing_events(batch, workspace=workspace, cap=file_cap)
    if _phase_exists(batch, "rolled-back", workspace=workspace, cap=file_cap):
        for index, item in enumerate(batch.replacements):
            current = _read_bytes(_path(workspace, item.path), root=workspace, cap=file_cap)
            backup = _old_bytes(batch, index, workspace=workspace, cap=file_cap)
            if current != backup:
                raise ValueError("rolled-back source bytes changed after completion")
        return

    _preflight_current_states(batch, workspace=workspace, file_cap=file_cap)
    backups = [
        _old_bytes(batch, index, workspace=workspace, cap=file_cap)
        for index in range(len(batch.replacements))
    ]
    _record_event(
        batch,
        "rollback-started",
        workspace=workspace,
        cap=file_cap,
        interrupt=interrupt,
    )
    for index in reversed(range(len(batch.replacements))):
        item = batch.replacements[index]
        target = _path(workspace, item.path)
        backup = backups[index]
        current = _read_bytes(target, root=workspace, cap=file_cap)
        if current != backup:
            if current != item.new_bytes:
                raise ValueError(
                    f"{item.path}: rollback refuses bytes other than exact old or exact new"
                )
            restore = target.with_name(
                f".d17-{batch.transaction_id[:12]}-{index:05d}.restore"
            )
            existing_restore = _maybe_read(restore, workspace=workspace, cap=file_cap)
            if existing_restore is None:
                _write_once(restore, backup, workspace=workspace, cap=file_cap)
            elif existing_restore != backup:
                raise ValueError(f"{item.path}: destination-local rollback stage is corrupt")
            current = _read_bytes(target, root=workspace, cap=file_cap)
            if current != item.new_bytes:
                raise ValueError(f"{item.path}: source drifted immediately before rollback")
            restore.replace(target)
            if interrupt is not None:
                interrupt(f"after-restore-before-journal:{index}")
        if _read_bytes(target, root=workspace, cap=file_cap) != backup:
            raise ValueError(f"{item.path}: restored source bytes failed exact verification")
        _record_event(
            batch,
            "restored",
            index=index,
            workspace=workspace,
            cap=file_cap,
            interrupt=interrupt,
        )
        _record_event(
            batch,
            "rollback-verified",
            index=index,
            workspace=workspace,
            cap=file_cap,
            interrupt=interrupt,
        )
    _record_event(batch, "rolled-back", workspace=workspace, cap=file_cap, interrupt=interrupt)


def _reconcile_installed(batch: _ApplyBatch, *, workspace: Path, limits: HistoryLimits) -> None:
    """Re-read exact installed bytes and rerun the named host readers/index reconciliation."""
    manifest, report = batch.manifest, batch.report
    if manifest is None or report is None:
        raise ValueError("full reconciliation requires the validated D16 manifest and report")
    report_files = {item.source.path: item for item in report.files}
    replacements = {item.path: item for item in batch.replacements}
    source_hashes = {source.path: source.sha256 for source in manifest.sources}
    rebound_sources = []
    for source in manifest.sources:
        entry = report_files[source.path]
        replacement = replacements.get(source.path)
        digest = replacement.new_sha256 if replacement else source.sha256
        size = len(replacement.new_bytes) if replacement else source.bytes
        data = _read_bytes(
            _path(workspace, source.path),
            root=workspace,
            cap=limits.verification.max_file_bytes,
        )
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"{source.path}: installed bytes differ from the complete batch")
        if source.kind == "receipt":
            archived = _read_bytes(
                _path(
                    workspace,
                    f"{batch.transaction_root}/evidence/original-receipts/{source.path}",
                ),
                root=workspace,
                cap=limits.max_bundle_bytes,
            )
            if (
                len(archived) != source.bytes
                or hashlib.sha256(archived).hexdigest() != source.sha256
            ):
                raise ValueError(f"{source.path}: original invocation receipt archive is corrupt")
            original = PublicationReceipt.model_validate(json.loads(archived))
            if set(original.writes) != set(source.dependencies) or any(
                source_hashes.get(path) != digest
                for path, digest in original.writes.items()
            ):
                raise ValueError(f"{source.path}: archived receipt does not prove original bytes")
        rebound_sources.append(source.model_copy(update={"sha256": digest, "bytes": size}))
        if entry.status == "candidate_complete" and replacement is None:
            raise ValueError(f"{source.path}: candidate source is missing from the journal")
    maintenance_bytes = _read_bytes(
        _path(
            workspace,
            f"{batch.transaction_root}/evidence/candidate-maintenance-receipt.json",
        ),
        root=workspace,
        cap=limits.max_bundle_bytes,
    )
    maintenance = PublicationReceipt.model_validate(json.loads(maintenance_bytes))
    expected_writes = {
        item.path: item.new_sha256 for item in batch.replacements
    }
    if maintenance != report.maintenance_receipt_candidate or maintenance.writes != expected_writes:
        raise ValueError("maintenance receipt does not reconcile exact replacement hashes")
    for file in report.files:
        if file.source.kind == "view" and file.candidate_path is not None:
            replacement = replacements[file.source.path]
            if (
                report.consumer_replay is None
                or report.consumer_replay.view_path != file.source.path
                or report.consumer_replay.view_sha256 != replacement.new_sha256
                or report.consumer_replay.view_bytes != len(replacement.new_bytes)
            ):
                raise ValueError("regenerated published view differs from consumer replay")

    # Old receipts are archived, not rewritten to claim current hashes. The
    # maintenance receipt above is the current physical-byte evidence.
    body = manifest.model_dump(mode="json")
    body["sources"] = [
        source.model_dump(mode="json")
        for source in rebound_sources
        if source.kind != "receipt"
    ]
    body["legacy_raw_evidence"] = []
    reconciled_manifest = HistoryManifest.model_validate(body)
    from idhazh.telemetry.host_history_migration import prepare_history

    reconciled = prepare_history(
        reconciled_manifest,
        workspace=workspace,
        limits=limits,
    )
    if (
        reconciled.report.normalized_settled_keys != report.normalized_settled_keys
        or reconciled.report.settlement != report.settlement
    ):
        raise ValueError("installed history changed settled identities, rank or cardinality")
    reconciled_files = {item.source.path: item for item in reconciled.report.files}
    for source in reconciled_manifest.sources:
        if source.kind in ("raw", "compact") and (
            reconciled_files[source.path].status != "excluded_corrected"
        ):
            raise ValueError(f"{source.path}: installed host file is not replacement-schema data")
        if source.kind in ("raw_index", "compact_index"):
            generated = reconciled.artifacts.get("candidates/" + source.path)
            installed = _read_bytes(
                _path(workspace, source.path),
                root=workspace,
                cap=limits.verification.max_file_bytes,
            )
            if generated is None or generated != installed:
                raise ValueError(
                    f"{source.path}: installed index rows/bytes/markers do not reconcile"
                )


def _apply_prepared_batch(
    batch: _ApplyBatch,
    *,
    workspace: Path,
    limits: HistoryLimits,
    interrupt: Callable[[str], None] | None = None,
) -> None:
    """Internal orchestration, reachable only after an external verified D16 gate."""
    if batch.manifest is None or batch.report is None:
        raise ValueError("application batch lacks its validated D16 evidence")
    _run_transaction(
        batch,
        workspace=workspace,
        max_files=limits.max_sources,
        file_cap=limits.verification.max_file_bytes,
        max_bytes=limits.max_bundle_bytes,
        reconcile=lambda: _reconcile_installed(batch, workspace=workspace, limits=limits),
        interrupt=interrupt,
    )


def _rollback_prepared_batch(
    batch: _ApplyBatch,
    *,
    workspace: Path,
    limits: HistoryLimits,
    interrupt: Callable[[str], None] | None = None,
) -> None:
    _rollback_transaction(
        batch,
        workspace=workspace,
        max_files=limits.max_sources,
        file_cap=limits.verification.max_file_bytes,
        max_bytes=limits.max_bundle_bytes,
        interrupt=interrupt,
    )
