"""How does a utility retain and validate one invocation's completed output evidence?"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from idhazh import ledger
from idhazh.atomic_write import write_atomic
from idhazh.contracts.file_envelope import FileEnvelope, Format, Tier, WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, Write, contains, safe_file

ROOT = Path("backend") / "var" / "publication"


def receipt_path(repo: Path, identity: WriterIdentity, verb: str) -> Path:
    return repo / ROOT / identity.task_key / f"{verb}-{identity.shard}.json"


def save(repo: Path, identity: WriterIdentity, verb: str, evidence: Mapping[Path, str]) -> None:
    writes: dict[str, str] = {}
    for path, digest in evidence.items():
        relative = path.relative_to(repo).as_posix()
        if relative.startswith(("state/", "frontend/public/", "corpus/")):
            writes[relative] = digest
    write_atomic(
        receipt_path(repo, identity, verb),
        PublicationReceipt(
            version=PublicationReceipt.schema_version(), identity=identity, writes=writes
        ).to_json(),
    )


def read(
    repo: Path, identity: WriterIdentity, verbs: Sequence[str], *,
    excluded: tuple[str, ...] = (),
) -> dict[str, str]:
    writes: dict[str, str] = {}
    for verb in verbs:
        path = receipt_path(repo, identity, verb)
        if not path.is_file():
            continue
        receipt = read_receipt(path, identity)
        denied = tuple(
            name for name in receipt.writes if any(contains(scope, name) for scope in excluded)
        )
        if denied:
            raise IntegrityError("receipt used a raw prefix reserved for another writer", denied)
        identified(repo, identity, receipt.writes)
        # Verbs are in execution order: a later completed metadata write supersedes
        # this invocation's earlier bytes, but never another writer's identity.
        writes.update(receipt.writes)
    return writes


def read_receipt(path: Path, identity: WriterIdentity) -> PublicationReceipt:
    receipt = PublicationReceipt.read(path)
    if receipt.identity != identity:
        raise IntegrityError("receipt belongs to another executed identity", (path.name,))
    return receipt


def identified(repo: Path, identity: WriterIdentity, hashes: Mapping[str, str]) -> None:
    """Raw envelopes must name the invocation that actually executed the producer."""
    fields = ("run_id", "attempt", "job", "pipeline_name", "task_name", "shard", "git_sha")
    for path in hashes:
        if not path.startswith("state/raw/"):
            continue
        target = safe_file(repo, path, exists=True)
        try:
            actual = ledger.read_envelope(target).identity
        except (ValueError, OSError) as error:
            raise IntegrityError(f"invalid completed raw envelope: {error}", (path,)) from error
        if any(getattr(actual, field) != getattr(identity, field) for field in fields):
            raise IntegrityError("completed raw file belongs to another invocation", (path,))


def verified_raw(
    root: Path, relative: str, data: bytes, *, name: LedgerName, date: str,
    identity: WriterIdentity,
) -> tuple[FileEnvelope, list[dict[str, object]]]:
    """Verify the exact named Parquet's envelope, row digest and writer."""
    from idhazh.ledger import json_lines, parquet
    from idhazh.ledger.filenames import file_id, unit_id

    meta, rows = parquet.read(data)
    envelope = FileEnvelope.from_metadata(meta).validate_container(Format.PARQUET)
    expected_unit = unit_id(
        ledger=name, covers=date, run_id=identity.run_id, job=identity.job,
        pipeline_name=identity.pipeline_name, task_name=identity.task_name,
        shard=identity.shard, producer=identity.producer,
    )
    expected_file = file_id(
        unit=expected_unit, attempt=identity.attempt, written_at_ms=envelope.written_at_ms,
    )
    want = ledger.raw_path(root, name, date, expected_file).relative_to(root).as_posix()
    if (
        relative != want or envelope.tier is not Tier.RAW or envelope.ledger != name
        or envelope.covers != date or envelope.identity != identity
        or envelope.unit_id != expected_unit or envelope.file_id != expected_file
        or len(rows) != 1
        or hashlib.sha256(json_lines.rows_bytes(rows)).hexdigest() != envelope.content_sha256
    ):
        raise IntegrityError(
            "completed raw file does not match its exact path or writer", (relative,),
        )
    return envelope, rows


def confirmed(
    git: Repository,
    hashes: Mapping[str, str],
    *,
    source: str,
    permissions: tuple[str, ...],
    mutable: tuple[str, ...] = (),
    code_source: str | None = None,
) -> dict[str, Write]:
    writes: dict[str, Write] = {}
    git.prime(source, set(hashes))
    for path, digest in hashes.items():
        if not any(contains(scope, path) for scope in permissions):
            raise IntegrityError("completed output exceeds declared authority", (path,))
        safe_file(git.repo, path, exists=True)
        tip = code_source if code_source and not path.startswith("state/") else source
        writes[path] = Write(
            digest,
            git.entry(tip, path),
            not any(contains(scope, path) for scope in mutable),
            baseline_tip=tip,
        )
    return writes
