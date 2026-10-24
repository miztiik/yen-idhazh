"""Which complete payload may each feed-planning stage hand to the next?"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import UUID4, Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RunId,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.feed_ingest_candidate import (
    FeedIngestCandidate,
    NonEmpty,
    NonNegative,
    OperationalHistory,
    PositiveCount,
    reject_legacy_publisher_identity,
)
from idhazh.contracts.feed_ingest_diagnostics import FetchFailure, HarvestDiagnostics
from idhazh.contracts.feed_ingest_dispatch import FeedIngestDispatch
from idhazh.contracts.feed_ingest_editorial_selection import EditorialSelectionRow
from idhazh.contracts.feed_ingest_rejection import CandidateRejectionRecord
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.recorded_instant import RecordedInstant
from idhazh.contracts.seen import SeenRow

Finite = Annotated[float, Field(allow_inf_nan=False)]
HttpStatus = Annotated[StrictInt, Field(ge=100, le=599)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonEmptyList = Annotated[list[NonEmpty], Field(min_length=1)]


def _remove_optional_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)
    variants = schema.pop("anyOf", None)
    if variants is not None:
        schema.update(next(variant for variant in variants if variant.get("type") != "null"))


class PlannerStageContext(Model):
    """The captured clock, run, correlation and writer shared by one plan."""

    now: Timestamp
    captured_at: RecordedInstant
    date: DateStamp
    run_id: RunId
    correlation_id: UUID4
    writer: WriterIdentity

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        now = datetime.fromisoformat(self.now.replace("Z", "+00:00"))
        captured_at = datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
        if (
            now.replace(microsecond=0) != captured_at.replace(microsecond=0)
            or self.date != self.now[:10]
        ):
            raise ValueError("context clock, captured instant and UTC date must agree")
        if not self.run_id.startswith(f"{self.date}-") or self.writer.run_id != self.run_id:
            raise ValueError("context run and writer must match its UTC date")
        if self.writer.pipeline_name != "feed-ingest-plan" or self.writer.task_name != "plan":
            raise ValueError("context writer must identify the feed-ingest-plan task")
        return self


class PlannerStageRequest(Model):
    """Resolved optional controls saved with the parsed candidate batch."""

    freshness_hours: Finite | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )
    article_limit: PositiveCount | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )
    shards: PositiveCount | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )
    partition_strategy: Literal["bin-pack", "round-robin", "none"] | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_options(cls, value: object) -> object:
        if isinstance(value, dict) and any(
            key in value and value[key] is None
            for key in ("freshness_hours", "article_limit", "shards", "partition_strategy")
        ):
            raise ValueError("optional request values must be omitted or supplied")
        return value


class RecordedIdentity(Model):
    """A recorded value and the origin that supports it."""

    value: NonEmpty
    origin: NonEmpty


class PrimaryEvidence(Model):
    """Non-empty article evidence identifiers and their recorded origin."""

    ids: NonEmptyList
    origin: NonEmpty


class PlannerArticleEvidence(Model):
    """Article-specific evidence used by ranking without rewriting candidates."""

    publisher: RecordedIdentity | None
    parent_domain: RecordedIdentity | None
    operational: OperationalHistory | None
    primary_evidence: PrimaryEvidence | None
    estimated_work: NonNegative


class PlannerOpportunityEvidence(Model):
    """The recorded event and vertical opportunities offered to portfolio ranking."""

    covered_event_clusters: list[NonEmpty] | None
    underrepresented_verticals: list[NonEmpty] | None
    origin: NonEmpty | None

    @model_validator(mode="after")
    def validate_origin(self) -> Self:
        has_evidence = (
            self.covered_event_clusters is not None
            or self.underrepresented_verticals is not None
        )
        if has_evidence != (self.origin is not None):
            raise ValueError("opportunity origin must match recorded opportunity evidence")
        return self


class PreflightFreshness(Model):
    """Freshness measured before article retrieval from its published time."""

    timing_at: Timestamp
    timing_source: Literal["published_at"]
    age_hours: Positive
    recency_bonus: NonNegative


class PlannerHarvestObservation(Model):
    """The bounded fetch, extraction and freshness evidence for a candidate."""

    candidate_id: Sha256
    http_status: HttpStatus | None
    robots: Literal["allowed", "denied", "unknown"] | None
    fetch_failure: FetchFailure | None
    paywall: bool | None
    paywall_evidence: Literal["json-ld", "configured-marker", "none", "not-observed"]
    extraction: Literal["success", "empty", "failed", "not-attempted"]
    observed_at: Timestamp
    diagnostics: HarvestDiagnostics | None = None
    preflight_freshness: PreflightFreshness | None = Field(
        default=None,
        validate_default=False,
        exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_preflight(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("preflight_freshness", ...) is None:
            raise ValueError("preflight_freshness must be omitted or an object")
        return value


class PlannerSeenAvailable(Model):
    """A complete first-sight ledger read, including an empty result."""

    availability: Literal["available"]
    rows: list[SeenRow]


class PlannerSeenUnavailable(Model):
    """The first-sight ledger could not be read."""

    availability: Literal["unavailable"]


PlannerSeenEvidence = Annotated[
    PlannerSeenAvailable | PlannerSeenUnavailable,
    Field(discriminator="availability"),
]


class ParsedFeedBatch(Contract):
    """The complete harvested input and evidence for one immutable parse batch."""

    __schema_stem__: ClassVar[str] = "parsed-feed-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-24T20:04",
            change="Preserve curated publisher identity in parsed candidates.",
            why="Every later stage reads the source identity recorded at harvest.",
        ),
        ChangelogEntry(
            version="2026-10-24",
            change="Declare complete parsed candidate batches and their evidence.",
            why="Later planner stages read one validated snapshot by its server identity.",
        ),
    )
    version: Literal["2026-10-24T20:04"] = "2026-10-24T20:04"
    batch_id: UUID4
    config_sha256: Sha256
    context: PlannerStageContext
    request: PlannerStageRequest
    candidates: list[FeedIngestCandidate]
    observations: dict[Sha256, PlannerHarvestObservation]
    seen: PlannerSeenEvidence
    evidence: dict[Sha256, PlannerArticleEvidence]
    opportunity: PlannerOpportunityEvidence
    operational_history: dict[Slug, OperationalHistory | None]
    rejections: list[CandidateRejectionRecord]

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") == "2026-10-24":
            candidates = value.get("candidates")
            reject_legacy_publisher_identity(value, [
                candidate.get("source")
                for candidate in candidates
                if isinstance(candidate, dict)
            ] if isinstance(candidates, list) else [])
            return {**value, "version": "2026-10-24T20:04"}
        return value

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate identities must be distinct")
        expected_correlation = str(self.context.correlation_id)
        for candidate in self.candidates:
            if (
                candidate.run_id != self.context.run_id
                or candidate.correlation_id != expected_correlation
                or candidate.date != self.context.date
            ):
                raise ValueError("candidate identity must match the batch context")
        for rejection in self.rejections:
            if (
                rejection.date != self.context.date
                or rejection.correlation_id != expected_correlation
            ):
                raise ValueError("rejection identity must match the batch context")
        if set(self.observations) != set(candidate_ids):
            raise ValueError("observation keys must match candidate identities")
        if any(key != observation.candidate_id for key, observation in self.observations.items()):
            raise ValueError("observation identity must match its key")
        if not set(self.evidence).issubset(candidate_ids):
            raise ValueError("article evidence keys must identify candidates")
        return self


class SelectedFeedBatch(Contract):
    """The ranked choices and refusals produced from one parsed batch."""

    __schema_stem__: ClassVar[str] = "selected-feed-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-24T20:04",
            change="Preserve curated publisher identity in selected snapshots.",
            why="Partitioning reads the identity recorded with each selected article.",
        ),
        ChangelogEntry(
            version="2026-10-24",
            change="Declare selected feed batches linked to their parsed input.",
            why="Partitioning reads ranked choices without copying the original batch.",
        ),
    )
    version: Literal["2026-10-24T20:04"] = "2026-10-24T20:04"
    batch_id: UUID4
    config_sha256: Sha256
    parsed_batch_id: UUID4
    context: PlannerStageContext
    selections: list[EditorialSelectionRow]
    rejections: list[CandidateRejectionRecord]

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") == "2026-10-24":
            selections = value.get("selections")
            reject_legacy_publisher_identity(value, [
                selection.get("source")
                for selection in selections
                if isinstance(selection, dict)
            ] if isinstance(selections, list) else [])
            return {**value, "version": "2026-10-24T20:04"}
        return value

    @model_validator(mode="after")
    def validate_selections(self) -> Self:
        ids = [row.candidate_id for row in self.selections]
        ranks = [row.editorial_rank for row in self.selections]
        if len(ids) != len(set(ids)) or len(ranks) != len(set(ranks)):
            raise ValueError("selected identities and ranks must be distinct")
        for row in self.selections:
            if (
                row.date != self.context.date
                or row.correlation_id != str(self.context.correlation_id)
            ):
                raise ValueError("selection identity must match the batch context")
        for rejection in self.rejections:
            if (
                rejection.date != self.context.date
                or rejection.correlation_id != str(self.context.correlation_id)
            ):
                raise ValueError("rejection identity must match the batch context")
        rejected_ids = {
            row.candidate_id for row in self.rejections if row.candidate_id is not None
        }
        if rejected_ids.intersection(ids):
            raise ValueError("a candidate cannot be both selected and rejected")
        return self


class PartitionedFeedBatch(Contract):
    """The ranked selections assigned to workers with their measured work totals."""

    __schema_stem__: ClassVar[str] = "partitioned-feed-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-24T20:04",
            change="Preserve curated publisher identity in partitioned snapshots.",
            why="Saved dispatch rows retain the identity carried by selection.",
        ),
        ChangelogEntry(
            version="2026-10-24",
            change="Declare partitioned feed batches and worker assignments.",
            why="Persistence receives one validated dispatch snapshot after partitioning.",
        ),
    )
    version: Literal["2026-10-24T20:04"] = "2026-10-24T20:04"
    batch_id: UUID4
    config_sha256: Sha256
    selection_batch_id: UUID4
    context: PlannerStageContext
    strategy: Literal["bin-pack", "round-robin", "none"]
    dispatch_count: PositiveCount
    work: list[NonNegative]
    dispatches: list[FeedIngestDispatch]

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") == "2026-10-24":
            dispatches = value.get("dispatches")
            snapshots = []
            if isinstance(dispatches, list):
                for dispatch in dispatches:
                    if not isinstance(dispatch, dict):
                        continue
                    content, selection = dispatch.get("content"), dispatch.get("selection")
                    snapshots.extend([
                        content.get("source") if isinstance(content, dict) else None,
                        selection.get("source") if isinstance(selection, dict) else None,
                    ])
            reject_legacy_publisher_identity(value, snapshots)
            return {**value, "version": "2026-10-24T20:04"}
        return value

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        if len(self.work) != self.dispatch_count:
            raise ValueError("work must contain one total per dispatch")
        if self.strategy == "none" and self.dispatch_count != 1:
            raise ValueError("none requires one dispatch")
        ids = [dispatch.selection.candidate_id for dispatch in self.dispatches]
        ranks = [dispatch.selection.editorial_rank for dispatch in self.dispatches]
        if len(ids) != len(set(ids)) or len(ranks) != len(set(ranks)):
            raise ValueError("dispatch identities and ranks must be distinct")
        for dispatch in self.dispatches:
            if (
                dispatch.partition.strategy != self.strategy
                or dispatch.partition.dispatch_count != self.dispatch_count
                or dispatch.selection.date != self.context.date
                or dispatch.selection.correlation_id != str(self.context.correlation_id)
            ):
                raise ValueError("dispatch assignment must match the batch context and strategy")
        if self.strategy == "round-robin":
            ranked = sorted(self.dispatches, key=lambda dispatch: dispatch.selection.editorial_rank)
            if any(
                dispatch.partition.worker_assignment != index % self.dispatch_count
                for index, dispatch in enumerate(ranked)
            ):
                raise ValueError("round-robin assignments must follow editorial rank")
        return self
