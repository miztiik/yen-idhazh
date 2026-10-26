"""Which current, server-owned payload crosses a planner stage in memory?"""

from __future__ import annotations

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
from idhazh.contracts.feed_health_state import FeedHealthStateRow
from idhazh.contracts.feed_ingest_candidate import FeedIngestCandidate
from idhazh.contracts.feed_ingest_diagnostics import FetchFailure, HarvestDiagnostics
from idhazh.contracts.feed_ingest_discovered_article import DiscoveredArticleRow
from idhazh.contracts.feed_ingest_selected_article import (
    Code,
    Count,
    NonNegative,
    PositiveCount,
    SelectedArticleRow,
)
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.recorded_instant import RecordedInstant

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Strategy = Literal["bin-pack", "round-robin", "none"]


def _remove_optional_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)
    variants = schema.pop("anyOf", None)
    if variants is not None:
        schema.update(next(variant for variant in variants if variant.get("type") != "null"))


class PlannerStageContext(Model):
    """The trusted clocks and execution context, never new-family file metadata."""

    now: Timestamp
    captured_at: RecordedInstant
    date: DateStamp
    run_id: RunId
    correlation_id: UUID4
    writer: WriterIdentity

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if (
            self.now[:19] != self.captured_at[:19]
            or self.date != self.now[:10]
            or self.writer.run_id != self.run_id
            or not self.run_id.startswith(f"{self.date}-")
        ):
            raise ValueError("stage context must retain its original UTC clock and run")
        return self


class PlannerStageRequest(Model):
    """Only supplied execution controls; null is not an omitted option."""

    freshness_hours: Positive | None = Field(
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
    partition_strategy: Strategy | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_options(cls, value: object) -> object:
        if isinstance(value, dict) and any(field is None for field in value.values()):
            raise ValueError("stage options must be omitted rather than null")
        return value


class PreflightFreshness(Model):
    """The actual pre-request publication age and recency contribution."""

    timing_at: Timestamp
    timing_source: Literal["published_at"]
    age_hours: Positive
    recency_bonus: NonNegative


class PlannerHarvestObservation(Model):
    """Transient fetch and extraction facts for one admitted candidate."""

    candidate_id: Sha256
    http_status: Annotated[StrictInt, Field(ge=100, le=599)] | None
    robots: Literal["allowed", "denied", "unknown"] | None
    fetch_failure: FetchFailure | None
    paywall: bool | None
    paywall_evidence: Literal["json-ld", "configured-marker", "none", "not-observed"]
    extraction: Literal["success", "empty", "failed", "not-attempted"]
    observed_at: Timestamp
    diagnostics: HarvestDiagnostics | None = None
    preflight_freshness: PreflightFreshness | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_preflight(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("preflight_freshness", ...) is None:
            raise ValueError("preflight_freshness must be omitted rather than null")
        return value


class PlannerSeenAvailable(Model):
    """A bounded first-sight read, with globally keyed discovery rows."""

    availability: Literal["available"]
    rows: list[DiscoveredArticleRow]


class PlannerSeenUnavailable(Model):
    """No reliable first-sight evidence was available."""

    availability: Literal["unavailable"]


PlannerSeenEvidence = Annotated[
    PlannerSeenAvailable | PlannerSeenUnavailable, Field(discriminator="availability"),
]

class RecordedIdentity(Model):
    """A genuine supplied identity and its source, never an inferred publisher."""

    value: Code
    origin: Code


class PrimaryEvidence(Model):
    """Supplied evidence identities used by the retained numeric allowance control."""

    ids: Annotated[list[Code], Field(min_length=1)]
    origin: Code


class PlannerArticleEvidence(Model):
    """Only the transient domain, evidence and work inputs the lean selector reads."""

    parent_domain: RecordedIdentity | None
    primary_evidence: PrimaryEvidence | None
    estimated_work: NonNegative


class PlannerRejectionCount(Model):
    """Transient grouped exclusions that become health counts, not article ledgers."""

    feed_id: Slug
    subject: Literal["feed", "article"]
    stage: Code
    reason_code: Code
    attribution: Literal["feed", "pipeline", "unknown"] | None
    count: Count


class PlannerHealthDay(Model):
    """One named represented UTC day and its observed coverage."""

    day: DateStamp
    complete: bool


class PlannerRequestFeed(Model):
    """Known spend for one feed; missing accounting remains null."""

    feed_id: Slug
    feed_requests: Count | None
    article_requests: Count | None
    robots_requests: Count | None
    counts_complete: bool


class PlannerRequestReport(Model):
    """The closed-UTC-day request-spend view, never another committed authority."""

    from_day: DateStamp
    through_day: DateStamp
    complete: bool
    feeds: list[PlannerRequestFeed]


class SelectedArticleContent(SelectedArticleRow):
    """The selected row plus artifact-only text, held only inside StageStore."""

    article_text: str


class ParsedFeedBatch(Contract):
    """The complete current parsed input, held in the bounded memory-only store."""

    __schema_stem__: ClassVar[str] = "parsed-feed-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Replace audit batches with current-only transient planner facts.",
            why="StageStore retains complete input without archived intermediate payloads.",
        ),
    )

    version: Literal["2026-10-25"] = "2026-10-25"
    batch_id: UUID4
    config_sha256: Sha256
    context: PlannerStageContext
    request: PlannerStageRequest
    candidates: list[FeedIngestCandidate]
    observations: dict[Sha256, PlannerHarvestObservation]
    seen: PlannerSeenEvidence
    evidence: dict[Sha256, PlannerArticleEvidence]
    history_rows: list[FeedHealthStateRow]
    history_days: list[PlannerHealthDay]
    work_rows: list[FeedHealthStateRow]
    exclusions: list[PlannerRejectionCount]

    @model_validator(mode="after")
    def validate_complete_input(self) -> Self:
        ids = {candidate.candidate_id for candidate in self.candidates}
        if len(ids) != len(self.candidates):
            raise ValueError("parsed candidate identities must be distinct")
        if any(
            candidate.run_id != self.context.run_id
            or candidate.correlation_id != str(self.context.correlation_id)
            for candidate in self.candidates
        ):
            raise ValueError("parsed candidates must belong to their batch run")
        if set(self.observations) != ids or any(
            key != observation.candidate_id for key, observation in self.observations.items()
        ):
            raise ValueError("parsed observations must match the complete candidate batch")
        return self


class SelectedFeedBatch(Contract):
    """One lean selection plus its own finalized work and shared report."""

    __schema_stem__: ClassVar[str] = "selected-feed-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Keep lean selected content and run health only in memory.",
            why="Committed selected rows use the explicit metadata-only projection.",
        ),
    )

    version: Literal["2026-10-25"] = "2026-10-25"
    batch_id: UUID4
    config_sha256: Sha256
    context: PlannerStageContext
    parsed_batch_id: UUID4
    selection_started_at_utc: Timestamp
    evaluated_at: Timestamp
    articles: list[SelectedArticleContent]
    health_rows: list[FeedHealthStateRow]
    exclusions: list[PlannerRejectionCount]
    request_report: PlannerRequestReport


class PartitionedFeedBatch(SelectedFeedBatch):
    """The same selected objects with measured partition assignment, never a new selection."""

    __schema_stem__: ClassVar[str] = "partitioned-feed-batch"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Partition the same current selected content without dispatch audit rows.",
            why="The selected artifact is the only text-bearing persisted planner handoff.",
        ),
    )

    selection_batch_id: UUID4
    strategy: Strategy
    dispatch_count: PositiveCount
    work: list[NonNegative]


class StageReferenceRequest(Model):
    """A server-owned current batch identity, never a caller path."""

    batch_id: UUID4


class PartitionArticlesRequest(StageReferenceRequest):
    """Optional partition controls applied without selecting again."""

    strategy: Strategy | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )
    shards: PositiveCount | None = Field(
        default=None, validate_default=False, exclude_if=lambda value: value is None,
        json_schema_extra=_remove_optional_default,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_options(cls, value: object) -> object:
        if isinstance(value, dict) and any(field is None for field in value.values()):
            raise ValueError("partition options must be omitted rather than null")
        return value
