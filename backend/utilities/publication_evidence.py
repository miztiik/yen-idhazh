"""How does a utility retain and validate one invocation's completed output evidence?"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from idhazh.contracts.file_envelope import FileEnvelope, WriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, Write, contains, safe_file

ROOT = Path("backend") / "var" / "publication"


def receipt_path(repo: Path, identity: WriterIdentity, verb: str) -> Path:
    return repo / ROOT / identity.job / f"{verb}-{identity.shard}.json"


def save(repo: Path, identity: WriterIdentity, verb: str, evidence: Mapping[Path, str]) -> None:
    writes: dict[str, str] = {}
    for path, digest in evidence.items():
        relative = path.relative_to(repo).as_posix()
        if relative.startswith(("state/", "frontend/public/", "corpus/")):
            writes[relative] = digest
    target = receipt_path(repo, identity, verb)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        PublicationReceipt(
            version=PublicationReceipt.schema_version(), identity=identity, writes=writes
        ).to_json(),
        encoding="utf-8",
        newline="\n",
    )


def read(repo: Path, identity: WriterIdentity, verbs: Sequence[str]) -> dict[str, str]:
    writes: dict[str, str] = {}
    for verb in verbs:
        path = receipt_path(repo, identity, verb)
        if not path.is_file():
            continue
        receipt = PublicationReceipt.read(path)
        if receipt.identity != identity:
            raise IntegrityError("receipt belongs to another executed identity", (str(path),))
        identified(repo, identity, receipt.writes)
        # Verbs are in execution order: a later completed metadata write supersedes
        # this invocation's earlier bytes, but never another writer's identity.
        writes.update(receipt.writes)
    return writes


def identified(repo: Path, identity: WriterIdentity, hashes: Mapping[str, str]) -> None:
    """Raw envelopes must name the invocation that actually executed the producer."""
    from idhazh.ledger import json_lines, parquet

    fields = ("run_id", "attempt", "job", "shard", "git_sha")
    for path in hashes:
        if not path.startswith("state/raw/"):
            continue
        target = safe_file(repo, path, exists=True)
        try:
            metadata, _ = (parquet.read if target.suffix == ".parquet" else json_lines.read)(
                target.read_bytes()
            )
            actual = FileEnvelope.from_metadata(metadata).identity
        except (ValueError, OSError) as error:
            raise IntegrityError(f"invalid completed raw envelope: {error}", (path,)) from error
        if any(getattr(actual, field) != getattr(identity, field) for field in fields):
            raise IntegrityError("completed raw file belongs to another invocation", (path,))


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
