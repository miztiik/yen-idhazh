"""The shard count recorded by a run manifest, without its private inputs."""

from typing import ClassVar

from pydantic import Field

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, Model, RunId


class RunShardsProvenance(Model):
    """The original file's existing envelope order, retained when its rows are packed."""

    written_at_ms: int = Field(ge=0)
    file_id: str = Field(pattern=r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")


class RunShards(Contract):
    __schema_stem__: ClassVar[str] = "run-shards"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Record only the manifest's date, run identity and shard count.",
            why="Hardware must check reported shards without publishing a whole manifest.",
        ),
    )

    date: DateStamp
    run_id: RunId
    shards: int | None = Field(
        default=None,
        ge=1,
        strict=True,
        description="RunRecord.shards, exactly as recorded. Null means it was not recorded.",
    )
