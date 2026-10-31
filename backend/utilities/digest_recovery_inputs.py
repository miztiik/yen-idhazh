"""Which saved plan and worker bytes can safely supply one recovery assembly?"""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, Write, safe_file

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
        raise IntegrityError("source artifact is not a readable ZIP archive") from error
    with zipped:
        for entry in zipped.infolist():
            mode = entry.external_attr >> 16
            name = entry.filename
            if (
                not name
                or "/" in name
                or "\\" in name
                or name in {".", ".."}
                or ":" in name
                or entry.is_dir()
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                or name in files
            ):
                raise IntegrityError("artifact contains an unsafe or duplicate file", (name,))
            try:
                files[name] = zipped.read(entry)
            except zipfile.BadZipFile as error:
                raise IntegrityError("source artifact has corrupt file bytes", (name,)) from error
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
            raise IntegrityError("plan artifact contains a non-ledger file", (name,))
        target = safe_file(scratch, name, exists=False)
        target.write_bytes(data)
        envelope = read_registered_envelope(target, ledger=LedgerName.RUN_PLAN)
        if Path(name).stem != str(envelope.file_id):
            raise IntegrityError("plan filename does not match its native file identity", (name,))
        if envelope.tier is not Tier.RAW:
            raise IntegrityError("plan artifact is not raw planning output", (name,))
        identity = envelope.identity
        if identity.run_id != f"{envelope.covers}-{execution}" or identity.attempt != attempt:
            continue
        if identity.git_sha != commit or identity.job != ServerJob.PLAN or identity.shard != 0:
            raise IntegrityError("source plan has mismatched writer identity", (name,))
        stored = load([target], model=RunPlan)
        if len(stored) != 1:
            raise IntegrityError("source plan file must contain one plan", (name,))
        plan = stored[0]
        if plan.run_id != identity.run_id or plan.date != envelope.covers or plan.shards is None:
            raise IntegrityError(
                "source plan has mismatched run, date or missing shard count", (name,)
            )
        if len({item.item_id for item in plan.items}) != len(plan.items):
            raise IntegrityError("source plan repeats an item identity", (name,))
        found.append((plan, name))
    if len(found) != 1:
        raise IntegrityError("artifact must retain exactly one compatible source-attempt plan")
    return found[0]


def worker_files(
    plan: RunPlan,
    archives: Mapping[str, bytes],
    *,
    failed_shards: frozenset[int] = frozenset(),
) -> dict[str, bytes]:
    """Validate named worker outputs; absent payloads remain absent, not regenerated."""
    if plan.shards is None:
        raise IntegrityError("source plan has no dispatched shard count")
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
        raise IntegrityError("items artifact names an undispatched shard")
    for shard in range(plan.shards):
        archive = archives.get(f"items-{shard}")
        if archive is None:
            if shard not in failed_shards and common.shard_of(
                plan, shard=shard, shards=plan.shards
            ):
                raise IntegrityError("successful worker has no retained items artifact")
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
                PipelineInputs.model_validate_json(data)
            elif name in names:
                item, contract = names[name]
                payload = contract.model_validate_json(data)
                if payload.item_id != item.item_id:
                    raise IntegrityError("worker payload identifies another planned item", (name,))
                if payload.url_key != item.url_key:
                    raise IntegrityError(
                        "worker payload does not match its planned address", (name,)
                    )
                if isinstance(payload, (EvalRow, ItemHealthRow)) and (
                    payload.run_id != plan.run_id or payload.date != plan.date
                ):
                    raise IntegrityError("worker record belongs to another source run", (name,))
                if isinstance(payload, ItemHealthRow) and (
                    payload.machine_shard != shard or payload.machine_job != ServerJob.WORK
                ):
                    raise IntegrityError("worker record belongs to another shard", (name,))
            else:
                raise IntegrityError("artifact contains an unplanned worker file", (name,))
            if name in merged and merged[name] != data:
                raise IntegrityError("worker artifacts disagree on shared bytes", (name,))
            merged[name] = data
    for item in plan.items:
        article = f"{item.item_id}.article.json"
        if article not in merged and any(
            f"{item.item_id}{suffix}" in merged for suffix in contracts if suffix != ".article.json"
        ):
            raise IntegrityError("worker output has no saved source article", (article,))
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
        raise IntegrityError("source run has no retained plan artifact")
    plans = unpack(archives["plan"])
    plan, name = select_plan(plans, scratch, execution=execution, attempt=attempt, commit=commit)
    items = worker_files(
        plan,
        {name: data for name, data in archives.items() if name != "plan"},
        failed_shards=failed_shards,
    )
    if plan.items and not items:
        raise IntegrityError("source run has no retained worker output")
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
            raise IntegrityError(
                "recovery item directory contains foreign files", tuple(sorted(extra))
            )
    git = Repository(repo)
    head = git.git("rev-parse", "HEAD").strip()
    for path, data in incoming.items():
        target = safe_file(repo, path, exists=False)
        if git.index_entry(path) != git.entry(head, path):
            raise IntegrityError("restore would touch foreign staged input", (path,))
        if target.exists() and target.read_bytes() != data:
            raise IntegrityError("restore would replace foreign local bytes", (path,))
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
        raise IntegrityError("restored source plan bytes changed", (restored.plan_path,))
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
        raise IntegrityError(
            "restored plan no longer matches source identity", (restored.plan_path,)
        )
    return Write(
        restored.plan_sha256,
        Repository(repo).entry(baseline, restored.plan_path),
        immutable=True,
        baseline_tip=baseline,
    )
