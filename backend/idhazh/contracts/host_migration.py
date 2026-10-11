"""What exact closed history may a read-only maintenance invocation plan to replace?"""

from __future__ import annotations

import calendar
import hashlib
from datetime import date, datetime
from pathlib import PurePosixPath
from typing import Annotated, ClassVar, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    PeriodStamp,
    RelPath,
    Sha256,
    Timestamp,
    compact_json,
)
from idhazh.contracts.file_envelope import Period, RowIdentity
from idhazh.contracts.host_output import CandidateFileEnvelope, HostWriterIdentity
from idhazh.contracts.publication_receipt import PublicationReceipt

MIGRATION_VERSION = "2026-10-11"
Nonnegative = Annotated[int, Field(strict=True, ge=0)]
Positive = Annotated[int, Field(strict=True, ge=1)]
FileStatus = Literal[
    "candidate_complete", "excluded_corrected", "deferred", "unresolved", "retained"
]
CandidateStatus = Literal["not_applicable", "candidate_complete", "frozen"]
ViewStatus = Literal["not_applicable", "deferred", "frozen"]
_CHANGELOG = (
    ChangelogEntry(
        version=MIGRATION_VERSION,
        change="Declare closed historical scopes and read-only replacement evidence.",
        why="Maintenance cannot silently expand its sources or invent missing readings.",
    ),
)


def period_days(covers: str, period: Period) -> tuple[date, date]:
    """The real UTC boundaries of a closed day, month or year."""
    if period is Period.DAILY:
        day = date.fromisoformat(covers)
        if day.isoformat() != covers:
            raise ValueError("closed day is not canonical")
        return day, day
    if period is Period.MONTHLY:
        first = date.fromisoformat(covers + "-01")
        return first, date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
    year = int(covers)
    if f"{year:04d}" != covers:
        raise ValueError("closed year is not canonical")
    return date(year, 1, 1), date(year, 12, 31)


class HistoryModel(Model):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def _portable_paths(self) -> Self:
        for name in ("path", "state_root", "isolated_root", "bundle_root", "candidate_path"):
            path = getattr(self, name, None)
            if path is not None and (
                "\\" in path
                or ":" in path
                or path != PurePosixPath(path).as_posix()
                or any(part in ("", ".", "..") for part in path.split("/"))
                or path.startswith("/")
            ):
                raise ValueError(f"{name} must be a canonical portable relative path")
        return self


class HistoryRoot(HistoryModel):
    name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]*$")]
    kind: Literal["production", "trial"]
    state_root: RelPath
    prefix: tuple[RelPath, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _host_prefix(self) -> Self:
        if self.prefix[-1] != "host-fingerprint" or any("/" in part for part in self.prefix):
            raise ValueError("root prefix must contain safe segments ending in host-fingerprint")
        if (self.kind == "production") != (self.prefix == ("host-fingerprint",)):
            raise ValueError("production and declared trial prefixes must be separate")
        return self


class ClosedHistoryPeriod(HistoryModel):
    root: str
    covers: PeriodStamp
    period: Period


class HistorySource(HistoryModel):
    root: str
    path: RelPath
    kind: Literal["raw", "compact", "raw_index", "compact_index", "view", "receipt", "set_aside"]
    sha256: Sha256
    bytes: Nonnegative
    covers: PeriodStamp | None = None
    period: Period | None = None
    dependencies: tuple[RelPath, ...] = ()


class HistoryManifest(HistoryModel, Contract):
    __schema_stem__: ClassVar[str] = "host-history-manifest"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    version: Literal["2026-10-11"]
    converted_at: Timestamp
    invocation: HostWriterIdentity
    isolated_root: RelPath
    range_start: DateStamp
    range_end: DateStamp
    roots: tuple[HistoryRoot, ...] = Field(min_length=1)
    closed_periods: tuple[ClosedHistoryPeriod, ...] = Field(min_length=1)
    sources: tuple[HistorySource, ...]

    @model_validator(mode="before")
    @classmethod
    def _stamp_current_version(cls, data: object) -> object:
        if not isinstance(data, dict) or "version" not in data:
            raise ValueError("manifest requires its explicit original schema version")
        return data

    @model_validator(mode="after")
    def _closed_scope(self) -> Self:
        start, end = date.fromisoformat(self.range_start), date.fromisoformat(self.range_end)
        converted = datetime.strptime(self.converted_at, "%Y-%m-%dT%H:%M:%SZ").date()
        if start > end or end >= converted:
            raise ValueError("range must contain only closed UTC dates before conversion")
        if not self.isolated_root.startswith("backend/var/"):
            raise ValueError("isolated_root must be a declared task root under backend/var")
        if self.invocation.producer != "utilities.migrate_host_fingerprints":
            raise ValueError("maintenance invocation requires the migration producer")
        roots = {root.name: root for root in self.roots}
        if len(roots) != len(self.roots):
            raise ValueError("duplicate root name")
        locations = [(root.state_root, root.prefix) for root in self.roots]
        if len(set(locations)) != len(locations):
            raise ValueError("duplicate declared history root")
        periods = {(p.root, p.covers, p.period) for p in self.closed_periods}
        if len(periods) != len(self.closed_periods):
            raise ValueError("duplicate closed period")
        for p in self.closed_periods:
            first, last = period_days(p.covers, p.period)
            if p.root not in roots or first < start or last > end:
                raise ValueError("closed period is outside the operator root/range list")
        source_paths = {source.path for source in self.sources}
        if len(source_paths) != len(self.sources):
            raise ValueError("duplicate manifested source path")
        for root in self.roots:
            if PurePosixPath(self.isolated_root).is_relative_to(
                root.state_root
            ) or PurePosixPath(root.state_root).is_relative_to(self.isolated_root):
                raise ValueError("isolated output overlaps a historical state root")
        for source in self.sources:
            if source.root not in roots:
                raise ValueError(f"{source.path}: undeclared root")
            if (
                source.kind in ("raw", "compact", "raw_index", "set_aside")
                and (source.root, source.covers, source.period) not in periods
            ):
                raise ValueError(f"{source.path}: source requires an explicitly closed period")
            if source.kind in ("raw", "raw_index") and source.period is not Period.DAILY:
                raise ValueError("raw sources and indexes require a closed day")
            if source.kind in ("raw", "set_aside") and source.dependencies:
                raise ValueError("raw and set-aside sources have no input dependencies")
            if source.kind in ("compact_index", "view", "receipt") and (
                source.covers is not None or source.period is not None
            ):
                raise ValueError(
                    "documents name periods through their validated contents/dependencies"
                )
            if PurePosixPath(source.path).is_relative_to(self.isolated_root):
                raise ValueError("source overlaps the isolated report root")
            if len(set(source.dependencies)) != len(source.dependencies):
                raise ValueError("duplicate source dependency")
            if any(path not in source_paths or path == source.path for path in source.dependencies):
                raise ValueError(f"{source.path}: unreconciled or self dependency")
        pending = {s.path: set(s.dependencies) for s in self.sources}
        while pending:
            ready = {path for path, dependencies in pending.items() if not dependencies}
            if not ready:
                raise ValueError("source dependency cycle")
            pending = {
                path: dependencies - ready
                for path, dependencies in pending.items()
                if path not in ready
            }
        return self

    def scope_hash(self) -> str:
        return hashlib.sha256(
            compact_json(self.model_dump(mode="json")).encode("ascii")
        ).hexdigest()


class RowMigration(HistoryModel):
    original_version: str
    original_identity: RowIdentity
    normalized_identity: RowIdentity
    original_key: tuple[str, ...]
    normalized_key: tuple[str, ...]
    dropped_values: dict[str, JsonValue]
    null_fields: tuple[str, ...]
    retained_average: float | None
    original_fingerprint: str | None
    fingerprint_version: Literal[1, 2] | None

    @model_validator(mode="after")
    def _preserved_rank(self) -> Self:
        if (
            self.original_identity != self.normalized_identity
            or self.original_key != self.normalized_key
        ):
            raise ValueError("normalization changed original identity or settlement key")
        return self


class HistoryFileReport(HistoryModel):
    source: HistorySource
    status: FileStatus
    candidate_path: RelPath | None
    old_physical_sha256: Sha256
    new_physical_sha256: Sha256 | None
    old_content_sha256: Sha256 | None = None
    new_content_sha256: Sha256 | None = None
    old_envelope: CandidateFileEnvelope | None = None
    new_envelope: CandidateFileEnvelope | None = None
    container: Literal["json", "parquet", "csv", "document", "unknown"]
    original_bytes: Nonnegative
    candidate_bytes: Nonnegative
    row_count: Nonnegative
    settled_key_count: Nonnegative
    rows: tuple[RowMigration, ...] = ()
    original_document: dict[str, JsonValue] | None = None
    candidate_document: dict[str, JsonValue] | None = None
    diagnosis: str | None = None

    @model_validator(mode="after")
    def _exact_source_and_candidate(self) -> Self:
        if (
            self.old_physical_sha256 != self.source.sha256
            or self.original_bytes != self.source.bytes
        ):
            raise ValueError("file inventory contradicts original source bytes")
        replacement = self.status == "candidate_complete"
        if replacement != (self.candidate_path is not None):
            raise ValueError("candidate status requires exactly one replacement path")
        if replacement:
            if (
                self.candidate_path != "candidates/" + self.source.path
                or self.new_physical_sha256 is None
                or self.candidate_bytes == 0
            ):
                raise ValueError("replacement path/hash/bytes contradict the source target")
        elif self.new_physical_sha256 is not None or self.candidate_bytes:
            raise ValueError("unwritten sources cannot claim replacement bytes")
        if self.row_count != len(self.rows) or self.settled_key_count != len(
            {row.original_key for row in self.rows}
        ):
            raise ValueError("row and settled-key inventory contradicts row reports")
        if self.old_envelope is not None:
            if self.source.kind not in ("raw", "compact") or self.old_content_sha256 != (
                self.old_envelope.content_sha256
            ):
                raise ValueError("original envelope contradicts file inventory")
            if replacement and (
                self.new_envelope is None
                or self.new_content_sha256 != self.new_envelope.content_sha256
            ):
                raise ValueError("replacement envelope/digest is missing")
        return self


class HistorySettlement(HistoryModel):
    root: str
    source_path: RelPath
    key: tuple[str, ...]
    identity: RowIdentity


class HistoryReport(HistoryModel, Contract):
    __schema_stem__: ClassVar[str] = "host-history-report"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = _CHANGELOG
    version: Literal["2026-10-11"]
    scope_hash: Sha256
    evidence_hash: Sha256
    bundle_root: RelPath
    manifest: HistoryManifest
    bounds: dict[str, Positive]
    inventory_complete: bool
    consumer_mode: Literal["candidate_reader", "migrated_consumers"]
    raw_status: CandidateStatus
    compact_status: CandidateStatus
    index_status: CandidateStatus
    derived_views_status: ViewStatus
    receipt_status_raw_compact_indexes: CandidateStatus
    receipt_status_derived_views: ViewStatus
    historical_readiness: Literal["blocked", "ready"]
    blocked_by: tuple[str, ...]
    affected_view_paths: tuple[RelPath, ...]
    deferred_receipt_paths: tuple[RelPath, ...]
    files: tuple[HistoryFileReport, ...]
    settlement: tuple[HistorySettlement, ...]
    original_settled_keys: Nonnegative
    normalized_settled_keys: Nonnegative
    maintenance_receipt_candidate: PublicationReceipt
    estimated_read_bytes: Nonnegative
    estimated_candidate_bytes: Nonnegative
    backup_policy: Literal["verified_source_bytes_before_replace; retain_original_receipts"]
    retirement_policy: Literal["no_source_retirement_in_dry_run"]

    @model_validator(mode="after")
    def _honest_readiness(self) -> Self:
        if self.scope_hash != self.manifest.scope_hash():
            raise ValueError("report scope_hash differs from the exact manifest")
        if self.original_settled_keys != self.normalized_settled_keys:
            raise ValueError("normalization changed settlement cardinality")
        if tuple(file.source for file in self.files) != self.manifest.sources:
            raise ValueError("report must reconcile every exact manifested source in order")
        if self.inventory_complete != all(file.status != "unresolved" for file in self.files):
            raise ValueError("unresolved sources contradict inventory completeness")
        views = tuple(file.source.path for file in self.files if file.source.kind == "view")
        if self.affected_view_paths != views:
            raise ValueError("affected view inventory differs from manifested views")
        paths = {source.path: source for source in self.manifest.sources}
        if self.normalized_settled_keys != len(self.settlement) or len(
            {(row.root, row.key) for row in self.settlement}
        ) != len(self.settlement):
            raise ValueError("settlement inventory contradicts root/key cardinality")
        if any(
            row.source_path not in paths
            or paths[row.source_path].root != row.root
            or paths[row.source_path].kind not in ("raw", "compact")
            for row in self.settlement
        ):
            raise ValueError("settlement names an unmanifested or foreign host source")
        if self.maintenance_receipt_candidate.identity.model_dump() != (
            self.manifest.invocation.model_dump()
        ):
            raise ValueError("candidate receipt must name the exact maintenance invocation")
        if self.consumer_mode == "candidate_reader" and self.historical_readiness != "blocked":
            raise ValueError("candidate reader cannot establish historical readiness")
        if self.historical_readiness == "ready" and (
            not self.inventory_complete
            or self.blocked_by
            or self.derived_views_status == "deferred"
            or self.receipt_status_derived_views == "deferred"
        ):
            raise ValueError("unresolved or deferred evidence blocks historical readiness")
        expected = hashlib.sha256(
            compact_json(
                self.model_dump(mode="json", exclude={"evidence_hash", "bundle_root"})
            ).encode("ascii")
        ).hexdigest()
        if expected != self.evidence_hash:
            raise ValueError("report evidence_hash differs from its exact validated bytes")
        if (
            self.bundle_root
            != f"{self.manifest.isolated_root}/{self.scope_hash}/{self.evidence_hash}"
        ):
            raise ValueError("bundle root does not name the exact scope and evidence generation")
        expected_writes = {
            file.source.path: file.new_physical_sha256
            for file in self.files
            if file.candidate_path is not None
        }
        if self.maintenance_receipt_candidate.writes != expected_writes:
            raise ValueError("candidate maintenance receipt does not cover exact replacement bytes")
        return self
