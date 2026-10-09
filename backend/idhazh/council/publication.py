"""Which exact writes did this collecting job finish inside its declared paths?"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from idhazh import atomic_write, file_writes, ledger
from idhazh.contracts.file_envelope import Format, Tier, WriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import session
from idhazh.ledger import paths


def receipt_path(identity: WriterIdentity) -> Path:
    """One named receipt across the dates this attempt settles."""
    return session.COUNCIL_ROOT / identity.run_id / f"publication-{identity.attempt}.json"


def inside(path: str, prefixes: Sequence[str]) -> bool:
    return any(PurePosixPath(path).is_relative_to(prefix) for prefix in prefixes)


@contextmanager
def scope(*, state_dir: Path, prefixes: Sequence[str]) -> Iterator[None]:
    """A tenant can confirm only writes inside its own declaration."""
    state = state_dir.resolve()

    def check(path: Path, data: bytes) -> None:
        resolved = path.resolve()
        if resolved.is_relative_to(state):
            relative = PurePosixPath("state", *resolved.relative_to(state).parts).as_posix()
            if not inside(relative, prefixes):
                raise ValueError(f"{relative} is outside this writer's declared publication paths")

    with file_writes.observe(check):
        yield


@contextmanager
def record(
    *,
    state_dir: Path,
    identity: WriterIdentity,
    prefixes: Sequence[str],
    destination: Path,
) -> Iterator[None]:
    """Keep confirmed writes even if a later tenant fails; never infer them from a result.

    Only this named receipt is read. Older dates of the same run contribute
    their exact files; a new write of one file replaces its earlier digest.
    """
    state = state_dir.resolve()
    receipt = PublicationReceipt.model_validate({"identity": identity, "writes": {}})
    if destination.exists():
        receipt = PublicationReceipt.from_json(destination.read_text(encoding="utf-8"))
        if receipt.identity != identity:
            raise ValueError("the publication receipt belongs to another writer")

    def remember(path: Path, data: bytes) -> None:
        resolved = path.resolve()
        if not resolved.is_relative_to(state):
            return
        relative = PurePosixPath("state", *resolved.relative_to(state).parts).as_posix()
        if not inside(relative, prefixes):
            raise ValueError(f"{relative} is outside the collecting job's declared paths")
        if resolved.is_relative_to(state / paths.RAW_DIRNAME):
            envelope = ledger.read_footer(resolved).envelope
            writer = envelope.identity
            if writer.model_copy(update={"producer": identity.producer}) != identity:
                raise ValueError(f"{relative} belongs to another raw-file writer")
            expected = ledger.raw_path(
                state,
                envelope.ledger,
                envelope.covers,
                envelope.file_id,
                fmt=Format(resolved.suffix.removeprefix(".")),
            )
            if envelope.tier is not Tier.RAW or resolved != expected:
                raise ValueError(f"{relative} is not the declared raw ledger file")
        receipt.writes[relative] = hashlib.sha256(data).hexdigest()

    try:
        with file_writes.observe(remember):
            yield
    finally:
        atomic_write.write_atomic(destination, receipt.to_json())
