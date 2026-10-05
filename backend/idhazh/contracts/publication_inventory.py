"""Which UTC days and named files can a static build publish without walking an archive?"""

from __future__ import annotations

from datetime import date
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, RelPath, records_json


class PublicationEntry(Model):
    """The measured bytes and published item count of one named file."""

    root: Literal["public", "state"] = "public"
    path: RelPath
    bytes: int = Field(ge=0, description="Bytes in the named file, excluding the inventory itself.")
    items: int = Field(ge=0, description="Published items in a digest.json; zero for other files.")


class PublicationInventory(Contract):
    """The named inventory at the public root, beside the digest directory."""

    def to_json(self) -> str:
        """Keep each file entry and changelog record on one line."""
        return records_json(
            self.model_dump(mode="json"), record_lists=frozenset({"entries", "changelog"})
        )

    __schema_stem__: ClassVar[str] = "publication-inventory"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-03T13:33",
            change="Use root-qualified entries as the only file list.",
            why="Readers filter one list instead of keeping duplicate path lists in step.",
        ),
        ChangelogEntry(
            version="2026-10-03T13:24",
            change="Include state-prefixed discovery paths in the shared files list.",
            why="The static reader uses one list to discover public and feed-health files.",
        ),
        ChangelogEntry(
            version="2026-10-03T13:18",
            change="Distinguish public files from named state files.",
            why="Feed-health day files need named discovery without mixing the two data roots.",
        ),
        ChangelogEntry(
            version="2026-10-03T13:10",
            change="Record bytes and items per file, with running publication totals.",
            why="Weight and item counters read one named inventory instead of historical payloads.",
        ),
        ChangelogEntry(
            version="2026-10-03",
            change="Declare published UTC days and public-root-relative file names.",
            why="Static builds read a named inventory instead of walking an archive.",
        ),
    )

    changelog: list[ChangelogEntry] = Field(
        default_factory=lambda: list(PublicationInventory.__changelog__),
        description="Shape changes, newest first, with the version this inventory carries.",
    )
    dates: list[DateStamp] = Field(description="Published UTC days, newest first and unique.")
    entries: list[PublicationEntry] = Field(default_factory=list)
    total_bytes: int = Field(default=0, ge=0, description="Bytes across all inventoried files.")
    total_items: int = Field(
        default=0, ge=0, description="Published items across all digest entries."
    )

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        if not self.changelog or self.changelog[0].version != self.version:
            raise ValueError("version must match the newest changelog entry")
        for day in self.dates:
            date.fromisoformat(day)
        if self.dates != sorted(set(self.dates), reverse=True):
            raise ValueError("dates must be unique and sorted newest first")
        if [(entry.root, entry.path) for entry in self.entries] != sorted(
            {(entry.root, entry.path) for entry in self.entries}
        ):
            raise ValueError("entries must be unique and sorted by root and path")
        public = [entry for entry in self.entries if entry.root == "public"]
        if self.total_bytes != sum(entry.bytes for entry in public):
            raise ValueError("total_bytes must equal the sum of entry bytes")
        if self.total_items != sum(entry.items for entry in public):
            raise ValueError("total_items must equal the sum of entry items")
        files = {entry.path for entry in public}
        digests = {f"digest/{day.replace('-', '/')}/digest.json" for day in self.dates}
        for entry in self.entries:
            if entry.root == "public" and entry.path == "publication.json":
                raise ValueError("publication.json cannot inventory itself")
            if entry.items and (entry.root != "public" or entry.path not in digests):
                raise ValueError("only a published digest.json may count items")
        for day in self.dates:
            path = f"digest/{day.replace('-', '/')}/digest.json"
            if path not in files:
                raise ValueError(f"published day {day} must name its digest.json")
        return self


class LegacyPublicationInventory(Model):
    """The first inventory shape, read only by the explicit named-file migration."""

    version: str
    changelog: list[ChangelogEntry]
    dates: list[DateStamp]
    files: list[RelPath]
    entries: list[PublicationEntry] = Field(default_factory=list)
    state_files: list[RelPath] = Field(default_factory=list)
    total_bytes: int = 0
    total_items: int = 0
