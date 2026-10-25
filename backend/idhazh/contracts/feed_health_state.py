"""Which bounded native ledger inputs support one saved feed-health revision?"""

from __future__ import annotations

import hashlib
import json
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
    Slug,
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
GapReason = Literal[
    "missing", "lost", "unreadable", "set-aside", "index-identity-unavailable",
]


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
    """One exact index and its stable membership for this named day."""

    ledger: Ledger
    kind: IndexKind
    path: NonEmpty
    content_sha256: Sha256
    day_membership_sha256: Sha256

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
    file_sha256: Sha256 | None
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
        parts = self.path[len(prefix):].split("/")
        if self.tier == "raw":
            if (
                len(parts) != 4
                or parts[3] != f"{self.file_id}.parquet"
            ):
                raise ValueError("raw Parquet path names its native UTC day and file identifier")
            try:
                input_day = date(*map(int, parts[:3])).isoformat()
            except ValueError as error:
                raise ValueError("raw Parquet path names a real UTC day") from error
            if "/".join(parts[:3]) != input_day.replace("-", "/"):
                raise ValueError("raw Parquet path names a canonical UTC day")
        elif self.period == "yearly":
            if (
                len(parts) != 3
                or parts[0] != "yearly"
                or not parts[2].endswith(".parquet")
                or parts[1] != parts[2].removesuffix(".parquet")
                or len(parts[1]) != 4
                or not parts[1].isdigit()
            ):
                raise ValueError("compact Parquet path names its native yearly coverage")
            try:
                date(int(parts[1]), 1, 1)
            except ValueError as error:
                raise ValueError("compact Parquet path names a real yearly coverage") from error
        elif self.period == "monthly":
            if (
                len(parts) != 3
                or parts[0] != "monthly"
                or not parts[2].endswith(".parquet")
            ):
                raise ValueError("compact Parquet path names its native monthly coverage")
            cover = f"{parts[1]}-{parts[2].removesuffix('.parquet')}"
            try:
                valid_cover = date.fromisoformat(f"{cover}-01").strftime("%Y-%m") == cover
            except ValueError:
                valid_cover = False
            if not valid_cover:
                raise ValueError("compact Parquet path names a real monthly coverage")
        elif self.period == "daily":
            if (
                len(parts) != 4
                or parts[0] != "daily"
                or not parts[3].endswith(".parquet")
            ):
                raise ValueError("compact Parquet path names its native daily coverage")
            cover = f"{parts[1]}/{parts[2]}/{parts[3].removesuffix('.parquet')}"
            try:
                valid_cover = date(*map(int, cover.split("/"))).strftime("%Y/%m/%d") == cover
            except ValueError:
                valid_cover = False
            if not valid_cover:
                raise ValueError("compact Parquet path names a real daily coverage")
        if (self.tier == "compact") != (self.file_sha256 is not None):
            raise ValueError("compact file identities retain their indexed byte digest")
        return self


class FeedHealthStateInputIdentity(Model):
    """The day-specific cheap index fingerprint and verified files."""

    input_day: DateStamp
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
    """One represented lifecycle day and its last verified contribution."""

    input_day: DateStamp
    read_status: Literal["available", "gap"]
    gap_reason: GapReason | None
    input_identity: FeedHealthStateInputIdentity | None
    observed_fingerprint: Sha256 | None
    rows: list[FeedHealthRow]

    @model_validator(mode="after")
    def validate_day(self) -> Self:
        if self.read_status == "available":
            if (
                self.input_identity is None
                or self.gap_reason is not None
                or self.observed_fingerprint != self.input_identity.fingerprint
            ):
                raise ValueError("an available lifecycle day has a verified current contribution")
        elif self.gap_reason is None:
            raise ValueError("an unreadable lifecycle day records its gap reason")
        if self.input_identity is None and self.rows:
            raise ValueError("retained lifecycle rows name their verified contribution")
        if any(row.date != self.input_day for row in self.rows):
            raise ValueError("feed-health rows retain their native represented day")
        if self.input_identity is not None and self.input_identity.input_day != self.input_day:
            raise ValueError("lifecycle identity names its represented input day")
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
    observed_fingerprint: Sha256 | None
    rows: list[DocumentObservationRecord]

    @model_validator(mode="after")
    def validate_day(self) -> Self:
        if self.read_status == "available":
            if (
                self.input_identity is None
                or self.gap_reason is not None
                or self.observed_fingerprint != self.input_identity.fingerprint
            ):
                raise ValueError("an available request day has a verified current contribution")
        elif self.gap_reason is None:
            raise ValueError("an unreadable request day records its gap reason")
        if self.input_identity is None and self.rows:
            raise ValueError("retained request rows name their verified contribution")
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
        if self.input_identity is not None and self.input_identity.input_day != self.input_day:
            raise ValueError("request identity names its closed input day")
        return self


class FeedHealthStateInventorySource(Model):
    """One configured source in the complete roster used for this revision."""

    source_id: Slug
    endpoint_key: Sha256
    publisher_id: Slug | None
    registry_status: Literal["draft", "active", "retired"]


class FeedHealthStateReliability(Model):
    """The existing feed-delivery aggregate retained for one source."""

    success_fraction: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    productive: Count
    attempted: PositiveCount
    window_days: PositiveCount
    from_day: DateStamp | None
    through_day: DateStamp | None
    production_factor: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]

    @model_validator(mode="after")
    def validate_reliability(self) -> Self:
        if self.productive > self.attempted:
            raise ValueError("productive feed reads do not exceed attempted reads")
        if self.success_fraction != self.productive / self.attempted:
            raise ValueError("success fraction matches the settled feed rows")
        if self.production_factor < self.success_fraction:
            raise ValueError("production factor does not fall below measured success")
        if (self.from_day is None) != (self.through_day is None):
            raise ValueError("reliability evidence bounds are available together")
        if (
            self.from_day is not None
            and self.through_day is not None
            and self.from_day > self.through_day
        ):
            raise ValueError("reliability evidence starts after it ends")
        return self


class FeedHealthStateLifecycleResult(Model):
    """The current feed-lifecycle result and its explicit input availability."""

    input_status: Literal["complete", "partial", "unavailable"]
    lifecycle: Literal["eligible", "resting", "retired", "unknown"]
    strikes: Count | None
    rested_runs: Count | None
    robots_permission: Literal["allowed", "denied", "unverified"]
    reliability: FeedHealthStateReliability | None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.lifecycle == "unknown" and (self.strikes is not None or self.rested_runs is not None):
            raise ValueError("unknown lifecycle does not claim strike or rest counts")
        return self


class FeedHealthStateRequestResult(Model):
    """The saved, qualified request aggregate for one source."""

    input_status: Literal["complete", "partial", "unavailable"]
    qualification_status: Literal["qualified", "insufficient_support", "unavailable"]
    measured_target_requests: Count | None
    measured_source_wasted_requests: Count | None
    observed_attempted_opportunities: Count | None
    observed_measured_opportunities: Count | None
    measured_coverage: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None
    request_waste_ratio: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None
    request_component_weight: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    request_component_penalty: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None

    @model_validator(mode="after")
    def validate_request_result(self) -> Self:
        if (self.measured_target_requests is None) != (
            self.measured_source_wasted_requests is None
        ):
            raise ValueError("measured request totals and waste are available together")
        if (
            self.measured_target_requests is not None
            and self.measured_source_wasted_requests is not None
            and self.measured_source_wasted_requests > self.measured_target_requests
        ):
            raise ValueError("wasted requests cannot exceed measured requests")
        if (
            self.observed_attempted_opportunities is not None
            and self.observed_measured_opportunities is not None
            and self.observed_measured_opportunities > self.observed_attempted_opportunities
        ):
            raise ValueError("measured opportunities cannot exceed attempted opportunities")
        if self.input_status != "complete":
            if self.qualification_status == "qualified":
                raise ValueError("incomplete request inputs cannot qualify a source")
            if self.request_waste_ratio is not None or self.request_component_penalty is not None:
                raise ValueError("incomplete request inputs carry no score")
        if self.qualification_status == "qualified":
            if (
                self.measured_target_requests is None
                or self.measured_target_requests == 0
                or self.measured_coverage is None
                or self.request_waste_ratio is None
                or self.request_component_penalty is None
            ):
                raise ValueError("qualified request evidence has complete positive support")
            if self.request_component_penalty != (
                self.request_waste_ratio * self.request_component_weight
            ):
                raise ValueError("request penalty matches the normalized configured weight")
        elif self.request_waste_ratio is not None or self.request_component_penalty is not None:
            raise ValueError("unqualified request evidence has no estimate or score")
        return self


class FeedHealthStateSourceResult(Model):
    """The per-source lifecycle and request results used by the next selection."""

    source_id: Slug
    endpoint_key: Sha256
    lifecycle: FeedHealthStateLifecycleResult
    requests: FeedHealthStateRequestResult


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
        root = "state/raw/feed-ingest-plan/feed-health-state/"
        if not self.path.startswith(root):
            raise ValueError("snapshot path belongs to the feed-health-state raw ledger")
        parts = self.path[len(root):].split("/")
        if len(parts) != 4 or any(not part.isdigit() for part in parts[:3]):
            raise ValueError("snapshot path follows the native raw UTC day layout")
        try:
            partition_day = date(*map(int, parts[:3])).isoformat()
        except ValueError as error:
            raise ValueError("snapshot path names a real raw UTC day") from error
        if "/".join(parts[:3]) != partition_day.replace("-", "/"):
            raise ValueError("snapshot path names a canonical raw UTC day")
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
            version="2026-10-25T13:50",
            change="Align the head stamp with native snapshot path validation.",
            why="Both bounded snapshot readers use the shared state contract version.",
        ),
        ChangelogEntry(
            version="2026-10-25T13:25",
            change="Require date-partitioned raw snapshot paths and explicit identity gaps.",
            why="Snapshots use the native writer and unverifiable compact inputs remain unknown.",
        ),
        ChangelogEntry(
            version="2026-10-25T13:03",
            change="Retain independent bounded copies of the complete snapshot head.",
            why="One damaged index cannot hide the previous valid snapshot.",
        ),
    )

    version: Literal["2026-10-25T13:50"] = "2026-10-25T13:50"
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
            version="2026-10-25T13:50",
            change="Match saved input identities to native raw and compact paths.",
            why="Changed-day checks must follow the existing ledger readers.",
        ),
        ChangelogEntry(
            version="2026-10-25T13:25",
            change="Save bounded source results and exact day-input identities.",
            why="Selections reuse saved results without scanning cached history.",
        ),
        ChangelogEntry(
            version="2026-10-25T13:03",
            change="Retain source results, complete roster and stable day memberships.",
            why="A selection reads saved source results without replaying native history.",
        ),
    )

    version: Literal["2026-10-25T13:50"] = "2026-10-25T13:50"
    state_revision: PositiveCount
    parent_revision: PositiveCount | None
    written_at_utc: Timestamp
    selection_batch_id: UUID4
    selection_started_at_utc: Timestamp
    code_revision: CommitSha
    policy_version: DateStamp
    policy_sha256: Sha256
    lifecycle_window_days: PositiveCount
    lifecycle_availability: Literal["complete", "partial", "unavailable"]
    lifecycle_window_start: DateStamp | None
    lifecycle_window_end: DateStamp | None
    lifecycle_days: list[FeedHealthStateLifecycleDay]
    request_window_days: PositiveCount
    request_availability: Literal["complete", "partial", "unavailable"]
    request_window_start: DateStamp
    request_window_end: DateStamp
    request_days: list[FeedHealthStateRequestDay]
    source_inventory_complete: bool
    source_inventory_sha256: Sha256 | None
    source_inventory: list[FeedHealthStateInventorySource]
    source_results: list[FeedHealthStateSourceResult]

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
        lifecycle_available = sum(day.read_status == "available" for day in self.lifecycle_days)
        expected_lifecycle_status = (
            "complete"
            if len(self.lifecycle_days) == self.lifecycle_window_days
            and lifecycle_available == len(self.lifecycle_days)
            else "partial" if lifecycle_available else "unavailable"
        )
        if self.lifecycle_availability != expected_lifecycle_status:
            raise ValueError("lifecycle availability matches represented-day evidence")

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
        request_available = sum(day.read_status == "available" for day in self.request_days)
        expected_request_status = (
            "complete" if request_available == self.request_window_days
            else "partial" if request_available else "unavailable"
        )
        if self.request_availability != expected_request_status:
            raise ValueError("request availability matches closed-day evidence")
        if not self.source_inventory_complete:
            if self.source_inventory_sha256 is not None or self.source_inventory or self.source_results:
                raise ValueError("an unavailable source roster has no invented members or results")
        else:
            if self.source_inventory_sha256 is None:
                raise ValueError("a complete source roster has an explicit digest, including when empty")
            inventory_ids = [item.source_id for item in self.source_inventory]
            result_ids = [item.source_id for item in self.source_results]
            if inventory_ids != sorted(set(inventory_ids)):
                raise ValueError("source roster is sorted and contains each source once")
            inventory_json = json.dumps(
                [
                    {
                        "source_id": item.source_id,
                        "endpoint_key": item.endpoint_key,
                        "publisher_id": item.publisher_id,
                        "registry_status": item.registry_status,
                    }
                    for item in self.source_inventory
                ],
                ensure_ascii=True,
                separators=(",", ":"),
            )
            inventory_sha256 = hashlib.sha256(inventory_json.encode("utf-8")).hexdigest()
            if inventory_sha256 != self.source_inventory_sha256:
                raise ValueError("source roster digest matches its canonical inventory")
            if result_ids != inventory_ids:
                raise ValueError("source results match the complete source roster")
            endpoints = {item.source_id: item.endpoint_key for item in self.source_inventory}
            if any(endpoints[item.source_id] != item.endpoint_key for item in self.source_results):
                raise ValueError("source results retain the configured endpoint identity")
        if self.request_availability != "complete" and any(
            item.requests.qualification_status == "qualified"
            for item in self.source_results
        ):
            raise ValueError("request gaps cannot qualify retained source results")
        if any(
            item.lifecycle.input_status != self.lifecycle_availability
            or item.requests.input_status != self.request_availability
            for item in self.source_results
        ):
            raise ValueError("source results retain each component's input availability")
        return self
