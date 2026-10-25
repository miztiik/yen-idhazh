"""Which bounded native ledger inputs support one saved feed-health revision?"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, ClassVar, Literal, Self
from uuid import UUID

from pydantic import UUID4, Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    Model,
    Sha256,
    Timestamp,
)
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_ingest_candidate import NonEmpty, PositiveCount
from idhazh.contracts.feed_ingest_observations import DocumentObservationRecord

Count = Annotated[StrictInt, Field(ge=0)]
Ledger = Literal["feed-health", "document-observations", "ingest-observations"]
IndexKind = Literal["raw", "daily", "monthly", "yearly"]
Tier = Literal["raw", "compact"]
Period = Literal["daily", "monthly", "yearly"]
GapReason = Literal["missing", "lost", "unreadable", "set-aside"]


def _relative_posix_path(value: str) -> str:
    parts = value.split("/")
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("state evidence paths must be relative POSIX paths")
    return value


class FeedHealthStateIndexIdentity(Model):
    """One exact registered index file read before any named Parquet file."""

    ledger: Ledger
    kind: IndexKind
    path: NonEmpty
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        _relative_posix_path(self.path)
        tier = "raw" if self.kind == "raw" else "compact"
        prefix = (
            f"state/{tier}/feed-health/"
            if self.ledger == "feed-health"
            else f"state/{tier}/feed-ingest-plan/{self.ledger}/"
        )
        if not self.path.startswith(prefix):
            raise ValueError("index path matches its native ledger and tier")
        return self


class FeedHealthStateFileIdentity(Model):
    """A Parquet file validated after its named day changed."""

    ledger: Ledger
    tier: Tier
    period: Period | None
    path: NonEmpty
    file_id: UUID
    content_sha256: Sha256
    bytes: Count
    row_count: Count

    @model_validator(mode="after")
    def validate_path(self) -> Self:
        _relative_posix_path(self.path)
        if (self.tier == "raw") != (self.period is None):
            raise ValueError("raw files have no compact period and compact files name one")
        prefix = (
            f"state/{self.tier}/feed-health/"
            if self.ledger == "feed-health"
            else f"state/{self.tier}/feed-ingest-plan/{self.ledger}/"
        )
        if not self.path.startswith(prefix):
            raise ValueError("Parquet path matches its native ledger and tier")
        if self.file_id.version != 8:
            raise ValueError("native file identity must be UUIDv8")
        if not self.path.endswith(f"/{self.file_id}.parquet"):
            raise ValueError("Parquet path ends with its native file identifier")
        return self


class FeedHealthStateInputIdentity(Model):
    """The cheap index fingerprint and verified files for one ledger day."""

    fingerprint: Sha256
    indexes: list[FeedHealthStateIndexIdentity]
    files: list[FeedHealthStateFileIdentity]

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        index_paths = [item.path for item in self.indexes]
        file_paths = [item.path for item in self.files]
        file_ids = [item.file_id for item in self.files]
        if not self.indexes or len(index_paths) != len(set(index_paths)):
            raise ValueError("day identity names distinct native indexes")
        if len(file_paths) != len(set(file_paths)) or len(file_ids) != len(set(file_ids)):
            raise ValueError("day identity names each native file once")
        indexed_ledgers = {item.ledger for item in self.indexes}
        if any(item.ledger not in indexed_ledgers for item in self.files):
            raise ValueError("each named Parquet file belongs to an identified native ledger")
        return self


class FeedHealthStateLifecycleDay(Model):
    """One represented lifecycle day and the last complete contribution retained for it."""

    input_day: DateStamp
    read_status: Literal["available", "gap"]
    gap_reason: GapReason | None
    input_identity: FeedHealthStateInputIdentity | None
    rows: list[FeedHealthRow]

    @model_validator(mode="after")
    def validate_day(self) -> Self:
        if self.read_status == "available":
            if self.input_identity is None or self.gap_reason is not None:
                raise ValueError("an available lifecycle day has a verified identity and no gap")
        elif self.gap_reason is None:
            raise ValueError("an unreadable lifecycle day records its gap reason")
        if any(row.date != self.input_day for row in self.rows):
            raise ValueError("feed-health rows retain their native represented day")
        if self.input_identity is not None and (
            any(item.ledger != "feed-health" for item in self.input_identity.indexes)
            or any(item.ledger != "feed-health" for item in self.input_identity.files)
        ):
            raise ValueError("lifecycle evidence names only the feed-health ledger")
        return self


class FeedHealthStateRequestDay(Model):
    """One closed request-evidence day and its retained causal operation facts."""

    input_day: DateStamp
    read_status: Literal["available", "gap"]
    gap_reason: GapReason | None
    input_identity: FeedHealthStateInputIdentity | None
    rows: list[DocumentObservationRecord]

    @model_validator(mode="after")
    def validate_day(self) -> Self:
        if self.read_status == "available":
            if self.input_identity is None or self.gap_reason is not None:
                raise ValueError("an available request day has a verified identity and no gap")
        elif self.gap_reason is None:
            raise ValueError("an unreadable request day records its gap reason")
        if self.input_identity is not None and (
            any(
                item.ledger not in {"document-observations", "ingest-observations"}
                for item in self.input_identity.indexes
            )
            or any(
                item.ledger not in {"document-observations", "ingest-observations"}
                for item in self.input_identity.files
            )
        ):
            raise ValueError("request evidence names only current or migrated observation ledgers")
        if any(row.occurred_at[:10] != self.input_day for row in self.rows):
            raise ValueError("document observations retain their native occurrence day")
        return self


class FeedHealthStateSnapshotReference(Model):
    """One named snapshot file in the bounded native head index."""

    snapshot_role: Literal["latest", "previous"]
    path: NonEmpty
    file_id: UUID
    content_sha256: Sha256
    bytes: Count
    row_count: Count
    state_revision: PositiveCount
    parent_revision: PositiveCount | None

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        _relative_posix_path(self.path)
        if not self.path.startswith("state/raw/feed-ingest-plan/feed-health-state/"):
            raise ValueError("snapshot path belongs to the feed-health-state raw ledger")
        if not self.path.endswith(f"/{self.file_id}.parquet"):
            raise ValueError("snapshot path must end with its native file identifier")
        if self.file_id.version != 8:
            raise ValueError("native snapshot file identity must be UUIDv8")
        if (self.state_revision == 1) != (self.parent_revision is None):
            raise ValueError("the first snapshot has no parent and later revisions name one")
        if self.parent_revision is not None and self.parent_revision + 1 != self.state_revision:
            raise ValueError("snapshot revision follows its actual parent")
        if self.row_count != 1:
            raise ValueError("each snapshot file contains exactly one complete state row")
        return self


class FeedHealthStateHeadIndex(Contract):
    """The two independently readable Parquet snapshots retained by the ledger."""

    __schema_stem__: ClassVar[str] = "feed-health-state-head-index"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25T11:21",
            change="Name only the latest and previous complete state snapshots.",
            why="A reader can fall back without scanning or trusting state payloads in JSON.",
        ),
    )

    version: Literal["2026-10-25T11:21"] = "2026-10-25T11:21"
    ledger: Literal["feed-health-state"] = "feed-health-state"
    latest: FeedHealthStateSnapshotReference
    previous: FeedHealthStateSnapshotReference | None

    @model_validator(mode="after")
    def validate_head(self) -> Self:
        if self.latest.snapshot_role != "latest":
            raise ValueError("head index latest reference names the latest slot")
        if self.previous is not None:
            if self.previous.snapshot_role != "previous":
                raise ValueError("head index previous reference names the previous slot")
            if self.previous.state_revision >= self.latest.state_revision:
                raise ValueError("previous snapshot revision is older than latest")
            if self.latest.parent_revision != self.previous.state_revision:
                raise ValueError("latest snapshot parent is the previous saved revision")
            if (
                self.previous.path == self.latest.path
                or self.previous.file_id == self.latest.file_id
            ):
                raise ValueError("latest and previous snapshots are independent files")
        elif self.latest.parent_revision is not None:
            raise ValueError("a noninitial latest snapshot retains its previous revision")
        return self


class FeedHealthStateSnapshot(Contract):
    """One independently readable latest or previous feed-health snapshot."""

    __schema_stem__: ClassVar[str] = "feed-health-state"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25T11:21",
            change="Declare bounded lifecycle and causal request evidence snapshots.",
            why="A selection reuses a versioned state read without replaying ledger history.",
        ),
    )

    version: Literal["2026-10-25T11:21"] = "2026-10-25T11:21"
    snapshot_role: Literal["latest", "previous"]
    state_revision: PositiveCount
    parent_revision: PositiveCount | None
    written_at_utc: Timestamp
    selection_batch_id: UUID4
    selection_started_at_utc: Timestamp
    code_revision: CommitSha
    policy_version: DateStamp
    policy_sha256: Sha256
    lifecycle_window_days: PositiveCount
    lifecycle_window_start: DateStamp | None
    lifecycle_window_end: DateStamp | None
    lifecycle_days: list[FeedHealthStateLifecycleDay]
    request_window_days: PositiveCount
    request_window_start: DateStamp
    request_window_end: DateStamp
    request_days: list[FeedHealthStateRequestDay]

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        if (self.state_revision == 1) != (self.parent_revision is None):
            raise ValueError("the first snapshot has no parent and later revisions name one")
        if self.parent_revision is not None and self.parent_revision >= self.state_revision:
            raise ValueError("parent revision must be older than the snapshot")
        if self.parent_revision is not None and self.parent_revision + 1 != self.state_revision:
            raise ValueError("snapshot revision follows its actual parent")

        lifecycle_dates = [day.input_day for day in self.lifecycle_days]
        if (
            len(lifecycle_dates) > self.lifecycle_window_days
            or lifecycle_dates != sorted(set(lifecycle_dates))
        ):
            raise ValueError(
                "lifecycle days are distinct, ascending and within the configured window"
            )
        if any(day > self.selection_started_at_utc[:10] for day in lifecycle_dates):
            raise ValueError("lifecycle inputs do not follow the selection start clock")
        expected_start = lifecycle_dates[0] if lifecycle_dates else None
        expected_end = lifecycle_dates[-1] if lifecycle_dates else None
        if (self.lifecycle_window_start, self.lifecycle_window_end) != (
            expected_start,
            expected_end,
        ):
            raise ValueError("lifecycle bounds match the retained represented-day inputs")

        start = date.fromisoformat(self.request_window_start)
        end = date.fromisoformat(self.request_window_end)
        selection_day = date.fromisoformat(self.selection_started_at_utc[:10])
        if end != selection_day - timedelta(days=1):
            raise ValueError("request evidence ends on the last closed UTC day before selection")
        if (end - start).days + 1 != self.request_window_days:
            raise ValueError("request window bounds match its configured closed-day count")
        request_dates = [day.input_day for day in self.request_days]
        expected_dates = [
            (start + timedelta(days=index)).isoformat()
            for index in range(self.request_window_days)
        ]
        if request_dates != expected_dates:
            raise ValueError("request days name every closed UTC day exactly once")
        return self
