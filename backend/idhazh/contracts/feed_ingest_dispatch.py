"""Which selected content is assigned to one worker?"""

from typing import Any, ClassVar, Literal, Self

from pydantic import model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model
from idhazh.contracts.feed_ingest_candidate import (
    Count,
    FeedIngestCandidate,
    PositiveCount,
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
            change="Carry candidate headline matches and salience observations.",
            why="Dispatch retains the planning evidence without changing selection scores.",
        ),
        ChangelogEntry(
            version="2026-10-22",
            change="Allow content and later selection to retain separate dates and policies.",
            why="Their shared article identity does not make their stage evidence identical.",
        ),
        ChangelogEntry(
            version="2026-10-20",
            change="Earlier changes are available in git history.",
            why="Worker allocation must preserve selection and content identity.",
        ),
    )
    version: Literal["2026-10-24T20:04"] = "2026-10-24T20:04"
    content: FeedIngestCandidate
    selection: EditorialSelectionRow
    partition: PartitionAssignment

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") in (
            "2026-10-20", "2026-10-22", "2026-10-23", "2026-10-24"
        ):
            content = value.get("content")
            selection = value.get("selection")
            snapshots = [
                content.get("source") if isinstance(content, dict) else None,
                selection.get("source") if isinstance(selection, dict) else None,
            ]
            reject_legacy_publisher_identity(value, snapshots)
            expected_selection_version = "2026-10-24" if value.get("version") == "2026-10-24" else "2026-10-20"
            if isinstance(selection, dict) and selection.get("version", "2026-10-20") != expected_selection_version:
                raise ValueError("historical dispatch requires its original selection version")
            return {**value, "version": "2026-10-24T20:04"}
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
