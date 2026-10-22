"""Why was one feed or offered article refused at its deciding stage?"""

from enum import StrEnum
from typing import Any, ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Sha256,
    Slug,
    Timestamp,
    Url,
    derive_url_key,
)
from idhazh.contracts.feed_ingest_candidate import (
    Count,
    Finite,
    NonEmpty,
    NonNegative,
    Positive,
    PositiveCount,
)
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.feed_ingest_diagnostics import HarvestDiagnostics

RejectionStage = Literal[
    "harvest-feeds",
    "screen-article-candidates",
    "curate-article-portfolio",
]


class DropReason(StrEnum):
    SOURCE_INACTIVE = "SOURCE_INACTIVE"
    FETCH_FAILED = "FETCH_FAILED"
    FETCH_FAILED_HTTP = "FETCH_FAILED_HTTP"
    FETCH_TIMEOUT = "FETCH_TIMEOUT"
    EXTRACT_FAILED = "EXTRACT_FAILED"
    EXTRACT_EMPTY = "EXTRACT_EMPTY"
    ALREADY_PUBLISHED = "ALREADY_PUBLISHED"
    SETTLED_FAILURE = "SETTLED_FAILURE"
    BLOCKED_URL_MARKER = "BLOCKED_URL_MARKER"
    PAYWALL_OR_BLOCKED = "PAYWALL_OR_BLOCKED"
    FEED_PARSE_FAILED = "FEED_PARSE_FAILED"
    FEED_EMPTY = "FEED_EMPTY"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
    CATEGORY_EXCLUDED = "CATEGORY_EXCLUDED"
    STUB_CONTENT = "STUB_CONTENT"
    STALE_MAX_AGE_EXCEEDED = "STALE_MAX_AGE_EXCEEDED"
    STALE_HALF_LIFE_DECAY = "STALE_HALF_LIFE_DECAY"
    DUPLICATE_CANONICAL_URL = "DUPLICATE_CANONICAL_URL"
    EVENT_CLUSTER_SIMILARITY = "EVENT_CLUSTER_SIMILARITY"
    SOURCE_QUOTA_EXCEEDED = "SOURCE_QUOTA_EXCEEDED"
    DESK_QUOTA_EXCEEDED = "DESK_QUOTA_EXCEEDED"
    KIND_QUOTA_EXCEEDED = "KIND_QUOTA_EXCEEDED"
    MMR_PORTFOLIO_CUTOFF = "MMR_PORTFOLIO_CUTOFF"
    REPLACED_BY_CARRIER = "REPLACED_BY_CARRIER"
    PUBLICATION_BUDGET_EXCEEDED = "PUBLICATION_BUDGET_EXCEEDED"
    ROLLING_HISTORY_REPEAT = "ROLLING_HISTORY_REPEAT"


REASON_STAGES: dict[DropReason, tuple[RejectionStage, ...]] = {
    reason: (
        ("harvest-feeds",)
        if reason
        in {
            DropReason.SOURCE_INACTIVE,
            DropReason.FETCH_FAILED,
            DropReason.FETCH_FAILED_HTTP,
            DropReason.FETCH_TIMEOUT,
            DropReason.EXTRACT_FAILED,
            DropReason.EXTRACT_EMPTY,
            DropReason.FEED_PARSE_FAILED,
            DropReason.FEED_EMPTY,
            DropReason.MISSING_REQUIRED_FIELDS,
            DropReason.ALREADY_PUBLISHED,
            DropReason.SETTLED_FAILURE,
            DropReason.BLOCKED_URL_MARKER,
        }
        else ("screen-article-candidates",)
        if reason
        in {
            DropReason.PAYWALL_OR_BLOCKED,
            DropReason.CATEGORY_EXCLUDED,
            DropReason.STUB_CONTENT,
            DropReason.STALE_HALF_LIFE_DECAY,
        }
        else ("harvest-feeds", "screen-article-candidates")
        if reason == DropReason.STALE_MAX_AGE_EXCEEDED
        else ("screen-article-candidates", "curate-article-portfolio")
        if reason in {DropReason.DUPLICATE_CANONICAL_URL, DropReason.ROLLING_HISTORY_REPEAT}
        else ("curate-article-portfolio",)
    )
    for reason in DropReason
}


class RejectionDetails(Model):
    """Fixed typed observations; absent measurements remain null."""

    http_status: int | None = Field(default=None, strict=True, ge=100, le=599)
    timeout_ms: Positive | None = None
    words_found: Count | None = None
    words_required: PositiveCount | None = None
    age_hours: NonNegative | None = None
    max_age_hours: Positive | None = None
    observed_value: Finite | None = None
    limit: Finite | None = None
    matched_url_key: Sha256 | None = None
    published_on: DateStamp | None = None
    failure_code: FailureCode | None = None
    matched_url_marker: NonEmpty | None = None
    history_window_days: PositiveCount | None = None
    diagnostics: HarvestDiagnostics | None = None


REQUIRED_DETAILS: dict[DropReason, tuple[str, ...]] = {
    DropReason.FETCH_FAILED_HTTP: ("http_status",),
    DropReason.FETCH_TIMEOUT: ("timeout_ms",),
    DropReason.EXTRACT_FAILED: ("diagnostics",),
    DropReason.EXTRACT_EMPTY: ("diagnostics",),
    DropReason.STUB_CONTENT: ("words_found", "words_required"),
    DropReason.STALE_MAX_AGE_EXCEEDED: ("age_hours", "max_age_hours"),
    DropReason.ALREADY_PUBLISHED: ("matched_url_key", "published_on", "history_window_days"),
    DropReason.SETTLED_FAILURE: ("matched_url_key", "failure_code"),
    DropReason.BLOCKED_URL_MARKER: ("matched_url_key", "matched_url_marker"),
    DropReason.STALE_HALF_LIFE_DECAY: ("observed_value", "limit"),
    DropReason.DUPLICATE_CANONICAL_URL: ("matched_url_key",),
    DropReason.EVENT_CLUSTER_SIMILARITY: ("matched_url_key", "observed_value", "limit"),
    DropReason.REPLACED_BY_CARRIER: ("matched_url_key",),
    DropReason.ROLLING_HISTORY_REPEAT: ("matched_url_key", "history_window_days"),
    **dict.fromkeys(
        (
            DropReason.SOURCE_QUOTA_EXCEEDED,
            DropReason.DESK_QUOTA_EXCEEDED,
            DropReason.KIND_QUOTA_EXCEEDED,
            DropReason.MMR_PORTFOLIO_CUTOFF,
            DropReason.PUBLICATION_BUDGET_EXCEEDED,
        ),
        ("observed_value", "limit"),
    ),
}


class CandidateRejectionRecord(Contract):
    """One terminal feed or candidate refusal, with no fabricated article identity."""

    __schema_stem__: ClassVar[str] = "feed-ingest-rejection"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-22T20:30",
            change="Record configured pre-fetch publication and settled-failure exclusions.",
            why="A terminal refusal must name the exact known reason without page measurements.",
        ),
        ChangelogEntry(
            version="2026-10-22T18:15",
            change="Preserve typed fetch and extraction diagnostics and operation timings.",
            why="A terminal reason must not erase the operation that actually failed.",
        ),
        ChangelogEntry(
            version="2026-10-22",
            change="Allow measured publication-age refusal before article download.",
            why="Expired feed entries need no page extraction to establish their age.",
        ),
        ChangelogEntry(
            version="2026-10-20",
            change="Declare terminal feed and article rejections.",
            why="Every deciding stage retains typed reasons and observations.",
        ),
    )
    version: Literal["2026-10-22T20:30"] = "2026-10-22T20:30"
    date: DateStamp
    correlation_id: NonEmpty
    source_id: Slug
    feed_url: Url
    subject: Literal["feed", "article"]
    candidate_id: Sha256 | None
    url_key: Sha256 | None
    canonical_url: Url | None
    title: str | None
    categories: list[str]
    stage: RejectionStage
    drop_reason: DropReason
    details: RejectionDetails
    rejected_at: Timestamp

    @model_validator(mode="before")
    @classmethod
    def migrate_previous_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("version") in {
            "2026-10-20", "2026-10-22", "2026-10-22T18:15"
        }:
            if value.get("drop_reason") in {
                "ALREADY_PUBLISHED", "SETTLED_FAILURE", "BLOCKED_URL_MARKER"
            }:
                raise ValueError("planner exclusions require the declared exclusion contract version")
            return {**value, "version": "2026-10-22T20:30"}
        return value

    @model_validator(mode="after")
    def validate_rejection(self) -> Self:
        article = self.subject == "article"
        if article != (self.candidate_id is not None):
            raise ValueError("candidate_id is required only for an article")
        for name in ("url_key", "canonical_url", "title"):
            value = getattr(self, name)
            if not article and value is not None:
                raise ValueError(f"feed rejection requires null {name}")
            missing_title = name == "title" and self.drop_reason in {
                DropReason.FETCH_FAILED,
                DropReason.FETCH_FAILED_HTTP,
                DropReason.FETCH_TIMEOUT,
                DropReason.EXTRACT_FAILED,
                DropReason.EXTRACT_EMPTY,
                DropReason.ALREADY_PUBLISHED,
                DropReason.SETTLED_FAILURE,
                DropReason.BLOCKED_URL_MARKER,
            }
            if (
                article
                and self.drop_reason != DropReason.MISSING_REQUIRED_FIELDS
                and value is None
                and not missing_title
            ):
                raise ValueError(f"article rejection requires {name}")
        if self.canonical_url is not None and self.url_key is not None:
            if self.url_key != derive_url_key(self.canonical_url):
                raise ValueError("url_key must match canonical_url")
        if self.date != self.rejected_at[:10]:
            raise ValueError("date must match the UTC rejection day")
        if self.stage not in REASON_STAGES[self.drop_reason]:
            raise ValueError("drop_reason is not valid for stage")
        feed_only = {
            DropReason.SOURCE_INACTIVE,
            DropReason.FEED_PARSE_FAILED,
            DropReason.FEED_EMPTY,
        }
        if article and self.drop_reason in feed_only:
            raise ValueError("drop_reason requires a feed subject")
        if not article and self.stage != "harvest-feeds":
            raise ValueError("feed failures belong to harvest-feeds")
        if not article and self.drop_reason == DropReason.MISSING_REQUIRED_FIELDS:
            raise ValueError("missing article fields require an article subject")
        if not article and self.drop_reason in {
            DropReason.EXTRACT_FAILED,
            DropReason.EXTRACT_EMPTY,
        }:
            raise ValueError("extraction failures require an article subject")
        for name in REQUIRED_DETAILS.get(self.drop_reason, ()):
            if getattr(self.details, name) is None:
                raise ValueError(f"{self.drop_reason} requires details.{name}")
        return self
