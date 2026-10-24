"""Source-level observations and proof that a planning attempt is complete."""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal, Self
from uuid import UUID

from pydantic import Field, StrictInt, field_validator, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RunId,
    SchemaVersion,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.feed_ingest_candidate import SourceSnapshot, reject_legacy_publisher_identity
from idhazh.contracts.feed_ingest_rejection import DropReason, RejectionStage
from idhazh.contracts.taxonomy import LifecycleStatus

Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]
FiniteFraction = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class DropReasonCount(Model):
    """A count of terminal drops, separated by subject and deciding stage."""

    subject: Literal["feed", "article"]
    stage: RejectionStage
    reason: DropReason
    count: PositiveCount


class CompletedFile(Model):
    """The identity and digest of one durable output file."""

    file_id: UUID
    content_sha256: Sha256
    row_count: PositiveCount

    @field_validator("file_id")
    @classmethod
    def require_uuid_v8(cls, value: UUID) -> UUID:
        if value.version != 8:
            raise ValueError("file_id must be a version 8 UUID")
        return value


class LogicalLedgerCommitment(Model):
    """An ordered unique record set, independent of its storage files."""

    version: Literal["2026-10-22"] = "2026-10-22"
    row_schema_version: SchemaVersion
    row_count: Count
    content_sha256: Sha256


class LedgerCompletionEvidence(Model):
    """Durable output evidence, including known-empty ledgers."""

    ledger: Literal[
        "article-assessments",
        "diversity",
        "editorial-selections",
        "dispatches",
        "rejections",
    ]
    row_count: Count
    files: list[CompletedFile]
    logical: LogicalLedgerCommitment | None = None

    @model_validator(mode="after")
    def validate_file_counts(self) -> Self:
        if sum(file.row_count for file in self.files) != self.row_count:
            raise ValueError("ledger row_count must equal the sum of its file row counts")
        if (self.row_count == 0) != (len(self.files) == 0):
            raise ValueError("an empty ledger has no files; a nonempty ledger has file evidence")
        if len({file.file_id for file in self.files}) != len(self.files):
            raise ValueError("ledger file identities must be distinct")
        if self.logical is not None and self.logical.row_count > self.row_count:
            raise ValueError("unique logical rows cannot exceed written rows")
        return self


class SourceRunRecord(Contract):
    """One source's operational and planning observations for a run attempt."""

    __schema_stem__: ClassVar[str] = "feed-ingest-source-run"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-24T20:04",
            change="Record curated publisher identity in source snapshots.",
            why="New observations preserve reviewed identity without rewriting history.",
        ),
        ChangelogEntry(
            version="2026-10-22T20:30",
            change="Count configured planner exclusions by their typed terminal reason.",
            why="Source audit counts must include each pre-fetch refusal accurately.",
        ),
        ChangelogEntry(
            version="2026-10-22T18:15",
            change="Count extraction errors and empty extraction separately from fetch errors.",
            why="Source failure counts must retain the operation that failed.",
        ),
        ChangelogEntry(
            version="2026-10-22T10:05",
            change="Commit unique attempt records independently of storage files.",
            why="Verified planning evidence must survive compaction without inventing old proof.",
        ),
        ChangelogEntry(
            version="2026-10-22",
            change="Earlier changes are available in git history.",
            why="The contract changelog keeps its four newest changes and one history pointer.",
        ),
    )
    version: Literal["2026-10-24T20:04"] = "2026-10-24T20:04"

    date: DateStamp
    correlation_id: str = Field(min_length=1)
    run_id: RunId
    attempt: PositiveCount
    source_id: Slug
    source: SourceSnapshot
    status: LifecycleStatus
    fetch_status: Literal[
        "not_requested", "success", "http_failure", "network_failure", "timeout"
    ]
    parse_status: Literal["not_attempted", "success", "empty", "failure"]
    parsed_count: Count | None
    harvested_count: Count | None
    fresh_count: Count | None
    duplicate_count: Count | None
    eligible_count: Count | None
    normalized_count: Count | None
    selected_count: Count | None
    published_count: Count | None
    lead_count: Count | None
    drop_reasons: list[DropReasonCount]
    fetch_duration_ms: Count | None
    parse_duration_ms: Count | None
    last_failure_at: Timestamp | None
    last_failure_reason: DropReason | None
    history_success_fraction: FiniteFraction | None
    history_success_attempts: Count | None
    history_window_days: PositiveCount | None
    observation_phase: Literal["plan_complete", "publication_complete"]
    observed_at: Timestamp
    expected_source_count: Count | None = None
    completion_evidence: list[LedgerCompletionEvidence] | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") in {
            "2026-10-20", "2026-10-22", "2026-10-22T10:05", "2026-10-22T18:15", "2026-10-22T20:30"
        }:
            reject_legacy_publisher_identity(value, [value.get("source")])
            legacy_reasons = {"ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER"}
            drop_reasons = value.get("drop_reasons", [])
            uses_new_reason = value.get("last_failure_reason") in legacy_reasons or (
                isinstance(drop_reasons, list)
                and any(
                    isinstance(item, dict) and item.get("reason") in legacy_reasons
                    for item in drop_reasons
                )
            )
            if uses_new_reason:
                raise ValueError(
                    "planner exclusions require the declared source-run "
                    "contract version"
                )
            return {**value, "version": "2026-10-24T20:04"}
        return value

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.source_id != self.source.source_id:
            raise ValueError("source_id must match the recorded source snapshot")
        if self.status != self.source.status:
            raise ValueError("status must match the recorded source lifecycle")
        if self.date != self.run_id[:10]:
            raise ValueError("date must match the original run UTC day")
        if self.fetch_status == "not_requested":
            if self.fetch_duration_ms is not None:
                raise ValueError("an unrequested fetch has no fetch duration")
        elif self.fetch_duration_ms is None:
            raise ValueError("an attempted fetch records its duration")
        if self.fetch_status != "success" and self.parse_status != "not_attempted":
            raise ValueError("only a successful fetch can be parsed")
        if self.parse_status == "not_attempted":
            if self.parse_duration_ms is not None or self.parsed_count is not None:
                raise ValueError("an unattempted parse has no duration or parsed count")
        elif self.parse_duration_ms is None:
            raise ValueError("an attempted parse records its duration")
        if self.parse_status in {"success", "empty"} and self.parsed_count is None:
            raise ValueError("a successful parse records its parsed count")
        if self.parse_status == "empty" and self.parsed_count != 0:
            raise ValueError("an empty feed has a known parsed count of zero")
        if self.parse_status == "success" and self.parsed_count == 0:
            raise ValueError("a successful nonempty parse has at least one parsed entry")
        if (self.last_failure_at is None) != (self.last_failure_reason is None):
            raise ValueError("last failure time and reason must be available together")
        history_values = (
            self.history_success_fraction,
            self.history_success_attempts,
            self.history_window_days,
        )
        if any(value is not None for value in history_values) and any(
            value is None for value in history_values
        ):
            raise ValueError("success fraction, its attempts, and its window are recorded together")
        if self.history_success_attempts == 0 and self.history_success_fraction is not None:
            raise ValueError("a success fraction needs at least one measured attempt")
        if len({(drop.subject, drop.stage, drop.reason) for drop in self.drop_reasons}) != len(
            self.drop_reasons
        ):
            raise ValueError("drop reason counts must have distinct subject/stage/reason keys")
        if self.observation_phase == "plan_complete":
            if self.published_count is not None or self.lead_count is not None:
                raise ValueError("a plan-complete observation has no publication counts")
            if self.expected_source_count is None or self.completion_evidence is None:
                raise ValueError("a complete plan records expected sources and file evidence")
        if self.observation_phase == "publication_complete":
            if self.published_count is None or self.lead_count is None:
                raise ValueError("a publication-complete observation records publication counts")
            if self.expected_source_count is None or self.completion_evidence is None:
                raise ValueError("a complete publication observation retains completion evidence")
        if self.published_count is not None and self.lead_count is not None:
            if self.lead_count > self.published_count:
                raise ValueError("lead_count is a subset of published_count")
        if self.completion_evidence is not None:
            ledgers = [entry.ledger for entry in self.completion_evidence]
            if len(set(ledgers)) != len(ledgers):
                raise ValueError("completion evidence has one entry per ledger")
            if set(ledgers) != {
                "article-assessments",
                "diversity",
                "editorial-selections",
                "dispatches",
                "rejections",
            }:
                raise ValueError("completion evidence covers every required planning ledger")
        return self
