"""Which selected metadata is committed, and which text travels only in the artifact?"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final, Literal, Self

from pydantic import Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    DateStamp,
    RunId,
    Sha256,
    Slug,
    Url,
    derive_url_key,
)
from idhazh.contracts.feed_ingest_discovered_article import (
    PlannerModel,
    PlannerPayload,
    PlannerRow,
)
from idhazh.contracts.recorded_instant import RecordedInstant

# Counts cross JavaScript's JSON boundary without losing integer identity.
MAX_SAFE_JSON_INTEGER = 2**53 - 1
Count = Annotated[StrictInt, Field(ge=0, le=MAX_SAFE_JSON_INTEGER)]
PositiveCount = Annotated[StrictInt, Field(ge=1, le=MAX_SAFE_JSON_INTEGER)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Weight = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Code = Annotated[str, Field(min_length=1)]
SELECTED_ARTICLE_VERSION: Final[Literal["2026-10-26"]] = "2026-10-26"
SELECTED_ARTICLE_CHANGELOG: Final = (
    ChangelogEntry(
        version=SELECTED_ARTICLE_VERSION,
        change="Require source or selection provenance and a UTC instant; no legacy provenance.",
        why="Unknown source dates must not change the age used for admission.",
    ),
)


class SelectedArticleAdjustment(PlannerModel):
    """One actual signed score term; null means unavailable rather than zero."""

    term: Code
    value: Finite | None


class SelectedArticleRatings(PlannerModel):
    """The chosen scores and their measured components, without witness trees."""

    base_article_score: Finite
    marginal_score: Finite
    adjustments: list[SelectedArticleAdjustment]
    recency_score: Finite
    feed_authority_score: Finite


class SelectedArticleMetadata(PlannerModel):
    """The explicit Table B article allowlist shared by row and artifact."""

    url_key: Sha256
    feed_id: Slug
    publisher_id: Slug | None
    canonical_url: Url
    title: Annotated[str, Field(min_length=1)]
    categories: list[str]
    author: str | None
    published_at: RecordedInstant | None
    published_at_source: Literal["source", "selection"]
    tier: PositiveCount
    weight: Weight
    applied_tier_weight: Weight
    editorial_rank: PositiveCount
    estimated_work: Count
    worker_assignment: Count | None
    ratings: SelectedArticleRatings
    feed_allowance: Count
    exploration_slot: bool
    cap_relaxations: list[Code]
    timing_at: RecordedInstant | None
    timing_basis: Literal["published_at", "first_seen", "unavailable"]
    age_hours: Finite | None
    allowance_reasons: list[Code]

    @model_validator(mode="after")
    def validate_selected_metadata(self) -> Self:
        if self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must match canonical_url")
        unavailable = self.timing_basis == "unavailable"
        if unavailable != (self.timing_at is None and self.age_hours is None):
            raise ValueError("unavailable timing has no instant or age")
        if not unavailable and (self.timing_at is None or self.age_hours is None):
            raise ValueError("available timing requires its measured instant and age")
        if self.published_at is None:
            raise ValueError("source or selection publication time requires a UTC instant")
        if self.published_at_source == "source" and (
            self.timing_basis != "published_at" or self.published_at != self.timing_at
        ):
            raise ValueError("source publication must retain the trusted admission instant")
        if self.published_at_source == "selection" and self.timing_basis == "published_at":
            raise ValueError("selection time must not replace the original age basis")
        return self


class SelectedArticleRow(SelectedArticleMetadata, PlannerRow):
    """One selected opportunity in its actual execution and accounting day."""

    __schema_stem__: ClassVar[str] = "feed-ingest-selected-article"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = SELECTED_ARTICLE_CHANGELOG

    run_id: RunId
    attempt: PositiveCount
    date: DateStamp

    @model_validator(mode="after")
    def validate_accounting_day(self) -> Self:
        if not self.run_id.startswith(f"{self.date}-"):
            raise ValueError("selected date must be its run's UTC accounting day")
        return self


class SelectedArtifactArticle(SelectedArticleMetadata):
    """One selected article whose sanitized text is artifact-only."""

    article_text: str


class SelectedArticlesArtifact(PlannerPayload):
    """The self-contained handoff, derived once from the same selected objects."""

    __schema_stem__: ClassVar[str] = "feed-ingest-selected-articles-artifact"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = SELECTED_ARTICLE_CHANGELOG

    schema_version: Literal["2026-10-26"]
    run_id: RunId
    attempt: PositiveCount
    date: DateStamp
    evaluated_at: RecordedInstant
    articles: list[SelectedArtifactArticle]

    @model_validator(mode="after")
    def validate_accounting_day(self) -> Self:
        if not self.run_id.startswith(f"{self.date}-"):
            raise ValueError("artifact date must be its run's UTC accounting day")
        return self


def selected_article_metadata(article: SelectedArtifactArticle) -> SelectedArticleMetadata:
    """Project only declared metadata without changing the text-bearing input."""
    return SelectedArticleMetadata(
        url_key=article.url_key,
        feed_id=article.feed_id,
        publisher_id=article.publisher_id,
        canonical_url=article.canonical_url,
        title=article.title,
        categories=list(article.categories),
        author=article.author,
        published_at=article.published_at,
        published_at_source=article.published_at_source,
        tier=article.tier,
        weight=article.weight,
        applied_tier_weight=article.applied_tier_weight,
        editorial_rank=article.editorial_rank,
        estimated_work=article.estimated_work,
        worker_assignment=article.worker_assignment,
        ratings=article.ratings.model_copy(deep=True),
        feed_allowance=article.feed_allowance,
        exploration_slot=article.exploration_slot,
        cap_relaxations=list(article.cap_relaxations),
        timing_at=article.timing_at,
        timing_basis=article.timing_basis,
        age_hours=article.age_hours,
        allowance_reasons=list(article.allowance_reasons),
    )
