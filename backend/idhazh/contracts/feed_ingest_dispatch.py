"""Which selected content is assigned to one worker?"""

from typing import ClassVar, Literal, Self

from pydantic import model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model
from idhazh.contracts.feed_ingest_candidate import Count, FeedIngestCandidate, PositiveCount
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
            version="2026-10-20",
            change="Declare selected article dispatches.",
            why="Worker allocation must preserve selection and content identity.",
        ),
    )
    version: Literal["2026-10-20"] = "2026-10-20"
    content: FeedIngestCandidate
    selection: EditorialSelectionRow
    partition: PartitionAssignment

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        for field in (
            "date",
            "correlation_id",
            "candidate_id",
            "source_id",
            "vertical",
            "source",
            "canonical_url",
            "url_key",
            "labels",
            "policy",
        ):
            if getattr(self.content, field) != getattr(self.selection, field):
                raise ValueError(f"dispatch content and selection disagree on {field}")
        return self
