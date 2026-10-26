"""What feed work did one run attempt perform on one actual UTC work day?"""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, model_validator

from idhazh.contracts.base import DateStamp, RunId, Sha256, Slug
from idhazh.contracts.feed_ingest_discovered_article import PlannerModel, PlannerRow
from idhazh.contracts.feed_ingest_selected_article import Code, Count, PositiveCount, Weight
from idhazh.contracts.recorded_instant import RecordedInstant


class FeedHealthReliability(PlannerModel):
    """The captured lookback used by this run, not additive daily counters."""

    productive: Count | None
    attempted: Count | None
    success_fraction: Weight | None
    from_day: DateStamp | None
    through_day: DateStamp | None
    production_factor: Weight | None
    complete: bool

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.productive is not None and self.attempted is not None:
            if self.productive > self.attempted:
                raise ValueError("productive reads cannot exceed attempted reads")
        if (self.from_day is None) != (self.through_day is None):
            raise ValueError("reliability window bounds are both known or both unavailable")
        if self.from_day is not None and self.through_day is not None:
            if self.from_day > self.through_day:
                raise ValueError("reliability window bounds must be ordered")
        return self


class FeedHealthRejectionCount(PlannerModel):
    """A grouped decision count, without rejected article identities or text."""

    reason_code: Code
    count: Count
    subject: Literal["feed", "article"]
    stage: Code
    attribution: Literal["feed", "pipeline", "unknown"] | None


class FeedHealthStateRow(PlannerRow):
    """One feed/endpoint/run/attempt/day contribution, never a rolling snapshot."""

    __schema_stem__: ClassVar[str] = "feed-health-state-row"

    feed_id: Slug
    endpoint_key: Sha256
    checked_at: RecordedInstant | None
    permission: Literal["allowed", "denied", "unknown"]
    availability: Literal["eligible", "resting", "retired", "unknown"]
    strikes: Count | None
    rested_runs: Count | None
    last_failure_code: Code | None
    status: Annotated[StrictInt, Field(ge=100, le=599)] | None
    reliability: FeedHealthReliability | None
    date: DateStamp
    feed_reads: Count | None
    productive_reads: Count | None
    failed_reads: Count | None
    article_candidates: Count | None
    articles_selected: Count | None
    feed_requests: Count | None
    article_requests: Count | None
    robots_requests: Count | None
    counts_complete: bool
    rejection_counts: list[FeedHealthRejectionCount]
    run_id: RunId
    attempt: PositiveCount
    items: Count | None
    outcome: Literal[
        "ok", "robots_denied", "blocked", "permanent", "transient", "skipped"
    ] | None

    @model_validator(mode="after")
    def validate_work_day(self) -> Self:
        if self.checked_at is not None and self.date != self.checked_at[:10]:
            raise ValueError("health date must name the actual UTC work day")
        counts = (
            self.feed_reads, self.productive_reads, self.failed_reads,
            self.article_candidates, self.articles_selected, self.feed_requests,
            self.article_requests, self.robots_requests,
        )
        if self.counts_complete and any(value is None for value in counts):
            raise ValueError("complete accounting requires every run counter")
        return self
