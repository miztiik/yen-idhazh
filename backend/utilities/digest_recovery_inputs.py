"""Which saved plan and worker bytes can safely supply one recovery assembly?"""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Tier
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.summary import Summary
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision
from idhazh.ledger.persist import load, read_registered_envelope
from idhazh.stages import common
from idhazh.telemetry.record import HEALTH_SUFFIX
from utilities.digest_recovery_refusal import RecoveryRefusalError, RefusalReason
from utilities.publication_git import Repository
from utilities.publication_request import Write, safe_file

type WorkerPayload = Article | Summary | EvalRow | ItemHealthRow | VisualDecision


@dataclass(frozen=True)
class RestoredInputs:
    """One validated source plan and the exact original file bytes restored beside its items."""

    plan: RunPlan
    plan_path: str
    plan_sha256: str


def unpack(archive: bytes) -> dict[str, bytes]:
    """Read one retained artifact; accept only unique, plain, flat file names."""
    files: dict[str, bytes] = {}
    try:
        zipped = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as error:
        raise RecoveryRefusalError(RefusalReason.NOT_A_ZIP_ARCHIVE) from error
    with zipped:
        for entry in zipped.infolist():
            mode = entry.external_attr >> 16
            name = entry.filename
            # A directory entry's name ends in a separator, so the separator checks refuse it too.
            if (
                not name
                or "/" in name
                or "\\" in name
                or name in {".", ".."}
                or ":" in name
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                or name in files
            ):
                raise RecoveryRefusalError(RefusalReason.UNSAFE_OR_DUPLICATE_FILE, (name,))
            try:
                files[name] = zipped.read(entry)
            except (zipfile.BadZipFile, zlib.error) as error:
                raise RecoveryRefusalError(RefusalReason.CORRUPT_FILE_BYTES, (name,)) from error
    return files


def select_plan(
    files: Mapping[str, bytes],
    scratch: Path,
    *,
    execution: str,
    attempt: int,
    commit: str,
) -> tuple[RunPlan, str]:
    """Select the source attempt's single plan through the strict native ledger reader."""
    found: list[tuple[RunPlan, str]] = []
    for name, data in files.items():
        if Path(name).suffix not in {".json", ".parquet"}:
            raise RecoveryRefusalError(RefusalReason.NON_LEDGER_PLAN_FILE, (name,))
        target = safe_file(scratch, name, exists=False)
        target.write_bytes(data)
        envelope = read_registered_envelope(target, ledger=LedgerName.RUN_PLAN)
        if Path(name).stem != str(envelope.file_id):
            raise RecoveryRefusalError(RefusalReason.PLAN_FILENAME_NOT_FILE_IDENTITY, (name,))
        if envelope.tier is not Tier.RAW:
            raise RecoveryRefusalError(RefusalReason.PLAN_NOT_RAW_OUTPUT, (name,))
        identity = envelope.identity
        if identity.run_id != f"{envelope.covers}-{execution}" or identity.attempt != attempt:
            continue
        if identity.git_sha != commit or identity.job != ServerJob.PLAN or identity.shard != 0:
            raise RecoveryRefusalError(RefusalReason.PLAN_WRITER_MISMATCH, (name,))
        # Loading validates every row as a RunPlan, which already refuses a repeated item identity.
        stored = load([target], model=RunPlan)
        if len(stored) != 1:
            raise RecoveryRefusalError(RefusalReason.PLAN_FILE_NOT_ONE_PLAN, (name,))
        plan = stored[0]
        if plan.run_id != identity.run_id or plan.date != envelope.covers or plan.shards is None:
            raise RecoveryRefusalError(RefusalReason.PLAN_RUN_DATE_OR_SHARDS_MISMATCH, (name,))
        found.append((plan, name))
    if len(found) != 1:
        raise RecoveryRefusalError(RefusalReason.NO_ONE_SOURCE_ATTEMPT_PLAN)
    return found[0]


def _validate_worker_payload[M: BaseModel](model: type[M], data: bytes, name: str) -> M:
    """Read one worker file as its contract, refusing with a typed reason when it is not."""
    try:
        return model.model_validate_json(data)
    except ValidationError as error:
        raise RecoveryRefusalError(RefusalReason.WORKER_PAYLOAD_INVALID, (name,)) from error


def worker_files(
    plan: RunPlan,
    archives: Mapping[str, bytes],
    *,
    failed_shards: frozenset[int] = frozenset(),
) -> dict[str, bytes]:
    """Validate named worker outputs; absent payloads remain absent, not regenerated."""
    if plan.shards is None:
        raise RecoveryRefusalError(RefusalReason.PLAN_HAS_NO_SHARD_COUNT)
    merged: dict[str, bytes] = {}
    contracts: dict[str, type[WorkerPayload]] = {
        ".article.json": Article,
        ".summary.json": Summary,
        ".eval.json": EvalRow,
        HEALTH_SUFFIX: ItemHealthRow,
        PAYLOAD_SUFFIX: VisualDecision,
    }
    expected_artifacts = {f"items-{shard}" for shard in range(plan.shards)}
    if set(archives) - expected_artifacts:
        raise RecoveryRefusalError(RefusalReason.UNDISPATCHED_SHARD_ARTIFACT)
    for shard in range(plan.shards):
        archive = archives.get(f"items-{shard}")
        if archive is None:
            if shard not in failed_shards and common.shard_of(
                plan, shard=shard, shards=plan.shards
            ):
                raise RecoveryRefusalError(RefusalReason.SUCCESSFUL_WORKER_ARTIFACT_MISSING)
            continue
        assigned = common.shard_of(plan, shard=shard, shards=plan.shards)
        names = {
            f"{item.item_id}{suffix}": (item, contract)
            for item in assigned
            for suffix, contract in contracts.items()
        }
        files = unpack(archive)
        for name, data in files.items():
            if name == common.INPUTS_PAYLOAD:
                _validate_worker_payload(PipelineInputs, data, name)
            elif name in names:
                item, contract = names[name]
                payload = _validate_worker_payload(contract, data, name)
                if payload.item_id != item.item_id:
                    raise RecoveryRefusalError(RefusalReason.PAYLOAD_NAMES_ANOTHER_ITEM, (name,))
                if payload.url_key != item.url_key:
                    raise RecoveryRefusalError(RefusalReason.PAYLOAD_ADDRESS_MISMATCH, (name,))
                if isinstance(payload, (EvalRow, ItemHealthRow)) and (
                    payload.run_id != plan.run_id or payload.date != plan.date
                ):
                    raise RecoveryRefusalError(RefusalReason.RECORD_FROM_ANOTHER_RUN, (name,))
                if isinstance(payload, ItemHealthRow) and (
                    payload.machine_shard != shard or payload.machine_job != ServerJob.WORK
                ):
                    raise RecoveryRefusalError(RefusalReason.RECORD_FROM_ANOTHER_SHARD, (name,))
            else:
                raise RecoveryRefusalError(RefusalReason.UNPLANNED_WORKER_FILE, (name,))
            if name in merged and merged[name] != data:
                raise RecoveryRefusalError(RefusalReason.SHARED_BYTES_DISAGREE, (name,))
            merged[name] = data
    for item in plan.items:
        article = f"{item.item_id}.article.json"
        if article not in merged and any(
            f"{item.item_id}{suffix}" in merged for suffix in contracts if suffix != ".article.json"
        ):
            raise RecoveryRefusalError(RefusalReason.SOURCE_ARTICLE_MISSING, (article,))
    return merged


def restore(
    repo: Path,
    scratch: Path,
    archives: Mapping[str, bytes],
    *,
    execution: str,
    attempt: int,
    commit: str,
    failed_shards: frozenset[int] = frozenset(),
) -> RestoredInputs:
    """Confirm the entire incoming set and all local baselines before copying any bytes."""
    if "plan" not in archives:
        raise RecoveryRefusalError(RefusalReason.NO_PLAN_ARTIFACT)
    plans = unpack(archives["plan"])
    plan, name = select_plan(plans, scratch, execution=execution, attempt=attempt, commit=commit)
    items = worker_files(
        plan,
        {name: data for name, data in archives.items() if name != "plan"},
        failed_shards=failed_shards,
    )
    if plan.items and not items:
        raise RecoveryRefusalError(RefusalReason.NO_WORKER_OUTPUT)
    plan_path = f"state/raw/run-plan/{plan.date.replace('-', '/')}/{name}"
    item_root = f"backend/var/run/{plan.date}/items"
    incoming = {
        plan_path: plans[name],
        **{f"{item_root}/{name}": data for name, data in items.items()},
    }
    # A dedicated, empty item directory prevents old unfinished work riding into recovery.
    item_dir = safe_file(repo, f"{item_root}/unused", exists=False).parent
    if item_dir.exists():
        extra = {path.name for path in item_dir.iterdir()} - items.keys()
        if extra:
            raise RecoveryRefusalError(
                RefusalReason.FOREIGN_ITEM_DIRECTORY_FILES, tuple(sorted(extra))
            )
    git = Repository(repo)
    head = git.git("rev-parse", "HEAD").strip()
    for path, data in incoming.items():
        target = safe_file(repo, path, exists=False)
        if git.index_entry(path) != git.entry(head, path):
            raise RecoveryRefusalError(RefusalReason.FOREIGN_STAGED_INPUT, (path,))
        if target.exists() and target.read_bytes() != data:
            raise RecoveryRefusalError(RefusalReason.FOREIGN_LOCAL_BYTES, (path,))
    for path, data in incoming.items():
        target = safe_file(repo, path, exists=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return RestoredInputs(plan, plan_path, hashlib.sha256(plans[name]).hexdigest())


def plan_import(
    repo: Path,
    restored: RestoredInputs,
    *,
    execution: str,
    attempt: int,
    commit: str,
    baseline: str,
) -> Write:
    """Authorize only the checked original plan file, never new planning or relabelled bytes."""
    path = safe_file(repo, restored.plan_path, exists=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != restored.plan_sha256:
        raise RecoveryRefusalError(RefusalReason.RESTORED_PLAN_BYTES_CHANGED, (restored.plan_path,))
    envelope = read_registered_envelope(path, ledger=LedgerName.RUN_PLAN)
    identity = envelope.identity
    if (
        identity.run_id != f"{restored.plan.date}-{execution}"
        or identity.attempt != attempt
        or identity.git_sha != commit
        or identity.job != ServerJob.PLAN
        or identity.shard != 0
        or load([path], model=RunPlan) != [restored.plan]
    ):
        raise RecoveryRefusalError(
            RefusalReason.RESTORED_PLAN_IDENTITY_CHANGED, (restored.plan_path,)
        )
    return Write(
        restored.plan_sha256,
        Repository(repo).entry(baseline, restored.plan_path),
        immutable=True,
        baseline_tip=baseline,
    )
