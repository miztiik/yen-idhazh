"""Which selected content is assigned to one worker?"""

from typing import Any, ClassVar, Literal, Self

from pydantic import model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model
from idhazh.contracts.feed_ingest_candidate import (
    Count,
    FeedIngestCandidate,
    PUBLISHER_EXPOSURE_VERSION,
    PositiveCount,
    SOURCE_OPERATIONAL_SCORE_VERSION,
    reject_legacy_source_operational,
    reject_legacy_publisher_identity,
)
from idhazh.contracts.feed_ingest_editorial_selection import EditorialSelectionRow


class PartitionAssignment(Model):
    """The worker allocation, independent of the ledger writer's shard."""

    strategy: Literal["bin-pack", "round-robin", "none"]
    worker_assignment: Count
    dispatch_count: PositiveCount

    @model_validator(mode="after")
    def validate_worker(self) -> Self:
        if self.worker_assignment >= self.dispatch_count:
            raise ValueError("worker_assignment must be below dispatch_count")
        if self.strategy == "none" and (self.worker_assignment != 0 or self.dispatch_count != 1):
            raise ValueError("none requires one dispatch and worker zero")
        return self


class FeedIngestDispatch(Contract):
    """One selected article's content, unchanged rank, and worker allocation."""

    __schema_stem__: ClassVar[str] = "feed-ingest-dispatch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Carry the saved request-estimate trace in selections.",
            why="Dispatch preserves operational evidence with the unchanged rank.",
        ),
        ChangelogEntry(
            version="2026-10-24T23:00",
            change="Carry selections with separately recorded publisher exposure.",
            why="Dispatch preserves the selected day counts and evidence gaps.",
        ),
        ChangelogEntry(
            version="2026-10-24T20:04",
            change="Carry curated publisher identity in dispatch snapshots.",
            why="Dispatch keeps the reviewed source identity selected upstream.",
        ),
        ChangelogEntry(
            version="2026-10-24",
            change="Carry selections with separate source-reliability score evidence.",
            why="Dispatch preserves the selected ranking and original harvested content.",
        ),
        ChangelogEntry(
            version="2026-10-23",
            change="Earlier changes are available in git history.",
            why="Worker allocation must preserve selection and content identity.",
        ),
    )
    version: Literal["2026-10-25"] = "2026-10-25"
    content: FeedIngestCandidate
    selection: EditorialSelectionRow
    partition: PartitionAssignment

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") in (
            "2026-10-20", "2026-10-22", "2026-10-23", "2026-10-24",
            "2026-10-24T20:04", PUBLISHER_EXPOSURE_VERSION,
        ):
            content = value.get("content")
            selection = value.get("selection")
            snapshots = [
                content.get("source") if isinstance(content, dict) else None,
                selection.get("source") if isinstance(selection, dict) else None,
            ]
            reject_legacy_publisher_identity(value, snapshots)
            expected_selection_version = (
                value["version"] if value.get("version") in {
                    "2026-10-24", "2026-10-24T20:04", PUBLISHER_EXPOSURE_VERSION
                } else "2026-10-20"
            )
            if (
                isinstance(selection, dict)
                and selection.get("version", "2026-10-20") != expected_selection_version
            ):
                raise ValueError("historical dispatch requires its original selection version")
            reject_legacy_source_operational(
                value,
                selection.get("ratings") if isinstance(selection, dict) else None,
            )
            return {**value, "version": SOURCE_OPERATIONAL_SCORE_VERSION}
        return value

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        for field in (
            "candidate_id",
            "source_id",
            "vertical",
            "source",
            "canonical_url",
            "url_key",
            "labels",
        ):
            if getattr(self.content, field) != getattr(self.selection, field):
                raise ValueError(f"dispatch content and selection disagree on {field}")
        return self
