"""Which exact writer-owned files may the council's collecting job commit?"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, RelPath, Sha256
from idhazh.contracts.file_envelope import WriterIdentity


class PublicationReceipt(Contract):
    """One run's confirmed writes, not permission to write a directory."""

    __schema_stem__: ClassVar[str] = "publication-receipt"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-09",
            change="Declare exact completed publication writes.",
            why="A declared directory must not sweep in another writer's files.",
        ),
    )
    identity: WriterIdentity
    writes: dict[RelPath, Sha256] = Field(
        description="Repository-relative files and the SHA-256 of the exact bytes written."
    )
