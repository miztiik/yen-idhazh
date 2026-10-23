"""Which content and independent labels belong to one offered feed entry?"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import Field, StrictInt, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    RunId,
    Sha256,
    Slug,
    Timestamp,
    Url,
    derive_url_key,
)
from idhazh.contracts.feed_ingest_planning_observations import PlanningObservations
from idhazh.contracts.sources import SourceForm
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, SourceTier

NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]
PlanningStage = Literal[
    "harvest-feeds",
    "screen-article-candidates",
    "curate-article-portfolio",
    "partition-article-shards",
    "seal-article-ledger",
]


def derive_candidate_id(run_id: str, source_id: str, entry_ordinal: int) -> str:
    """Hash validated run/source/zero-based ordinal with newline separators."""
    from pydantic import TypeAdapter

    run = TypeAdapter(RunId).validate_python(run_id)
    source = TypeAdapter(Slug).validate_python(source_id)
    ordinal = TypeAdapter(Count).validate_python(entry_ordinal)
    return hashlib.sha256(f"{run}\n{source}\n{ordinal}".encode()).hexdigest()


class SourceSnapshot(Model):
    """Which configured source facts were used, without consulting today's registry?"""

    source_id: Slug
    feed_url: Url
    title: NonEmpty
    vertical: Slug
    kind: SourceKind
    tier: SourceTier
    form: SourceForm
    status: LifecycleStatus
    weight: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    applied_tier_weight: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class ArticleLabels(Model):
    """Which independent labels are known, and which matcher supplied them?"""

    assigned_desk: Slug | None
    lenses: list[Slug] | None
    event_types: list[Slug] | None
    event_cluster_id: NonEmpty | None
    entities: list[Slug] | None
    origin: NonEmpty | None
    matcher_version: NonEmpty | None

    @model_validator(mode="after")
    def validate_origin(self) -> Self:
        if (self.origin is None) != (self.matcher_version is None):
            raise ValueError("label origin and matcher_version must be available together")
        if (
            any(
                value is not None
                for value in (
                    self.assigned_desk,
                    self.lenses,
                    self.event_types,
                    self.event_cluster_id,
                    self.entities,
                )
            )
            and self.origin is None
        ):
            raise ValueError("known labels require origin and matcher_version")
        return self


class PenaltyEvidence(Model):
    """Whether a portfolio term had evidence, and its measured contribution."""

    available: bool
    value: NonNegative | None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.available != (self.value is not None):
            raise ValueError("penalty availability must match its value")
        return self


class ScoreEvidence(Model):
    """Which ratings and separate portfolio penalties decided a greedy choice?"""

    base_article_score: Finite
    marginal_score: Finite
    source: PenaltyEvidence
    source_kind: PenaltyEvidence
    domain: PenaltyEvidence
    vertical: PenaltyEvidence
    desk: PenaltyEvidence
    lens: PenaltyEvidence
    event_type: PenaltyEvidence
    event_cluster: PenaltyEvidence
    entity: PenaltyEvidence
    coverage: PenaltyEvidence
    source_allowance: Count
    bonus_uncovered_event_cluster: bool
    bonus_underrepresented_vertical: bool
    bonus_unique_evidence: bool
    carrier_outlets: list[NonEmpty]
    representative_url_key: Sha256 | None
    replacement_url_key: Sha256 | None
    exploration_slot: bool
    cap_relaxations: list[Literal["distinct_sources", "source_share"]]


class PolicyIdentity(Model):
    """Which resolved candidate policy and committed configuration were used?"""

    policy_version: NonEmpty
    config_sha256: Sha256
    min_words_article: PositiveCount
    min_words_abstract: PositiveCount
    max_age_hours: Positive
    recency_half_life_hours: Positive
    recency_weight: NonNegative
    source_authority_weight: NonNegative
    base_source_allowance: Count
    bonus_uncovered_event_cluster: Count
    bonus_underrepresented_vertical: Count
    bonus_unique_evidence: Count
    lambda_source: NonNegative
    lambda_source_kind: NonNegative
    lambda_domain: NonNegative
    lambda_vertical: NonNegative
    lambda_desk: NonNegative
    lambda_lens: NonNegative
    lambda_event_type: NonNegative
    lambda_event_cluster: NonNegative
    lambda_entity: NonNegative
    lambda_coverage: NonNegative


class FeedIngestCandidate(Contract):
    """The validated harvested content of one entry, before editorial selection."""

    __schema_stem__: ClassVar[str] = "feed-ingest-candidate"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-23",
            change="Retain headline matches and partial optional salience observations.",
            why="Planning evidence stays separate from later article classification.",
        ),
        ChangelogEntry(
            version="2026-10-20",
            change="Declare harvested candidates and label evidence.",
            why="Stage boundaries retain content and independent evidence.",
        ),
    )
    version: Literal["2026-10-23"] = "2026-10-23"
    date: DateStamp
    correlation_id: NonEmpty
    run_id: RunId
    candidate_id: Sha256
    entry_ordinal: Count
    source_id: Slug
    vertical: Slug
    source: SourceSnapshot
    canonical_url: Url
    url_key: Sha256
    title: NonEmpty
    categories: list[str]
    article_text: str
    word_count: Count
    author: str | None
    published_at: Timestamp | None
    fetched_at: Timestamp
    labels: ArticleLabels
    policy: PolicyIdentity
    planning_observations: PlanningObservations | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") == "2026-10-20":
            return {**value, "version": "2026-10-23"}
        return value

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.source_id != self.source.source_id or self.vertical != self.source.vertical:
            raise ValueError("source_id and vertical must match the source snapshot")
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must match canonical_url")
        if self.candidate_id != derive_candidate_id(
            self.run_id, self.source.source_id, self.entry_ordinal
        ):
            raise ValueError("candidate_id must match run/source/entry ordinal")
        if self.date != self.fetched_at[:10]:
            raise ValueError("date must match the UTC fetch day")
        return self
