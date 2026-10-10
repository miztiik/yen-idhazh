"""Which exact bytes did a completed producer write?"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, RelPath, Sha256
from idhazh.contracts.file_envelope import WriterIdentity


class PublicationReceipt(Contract):
    """Evidence of completed writes, never authority to publish their paths."""

    identity: WriterIdentity
    writes: dict[RelPath, Sha256] = Field(default_factory=dict)

    __schema_stem__: ClassVar[str] = "publication-receipt"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-09", change="Declare exact completed-write evidence.",
            why="Publication checks completed bytes independently of declared permissions.",
        ),
    )
