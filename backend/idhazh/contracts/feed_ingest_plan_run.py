"""What did one planner execution finish, including a zero or failed result?"""

from __future__ import annotations

from typing import ClassVar, Literal, Self

from pydantic import model_validator

from idhazh.contracts.base import ChangelogEntry, DateStamp, RelPath, RunId
from idhazh.contracts.feed_ingest_discovered_article import PlannerModel, PlannerRow
from idhazh.contracts.feed_ingest_selected_article import Code, Count, PositiveCount, Weight
from idhazh.contracts.recorded_instant import RecordedInstant


class PlanApiTiming(PlannerModel):
    """One measured major phase, never a per-article trace tree."""

    operation: Literal[
        "fetch", "parse", "select", "partition", "persist", "feed-health-summary",
        "feed-health-before-fetch", "feed-health-for-selection",
    ]
    duration_ms: Count
    status: Literal["completed", "failed", "interrupted"]


class PlanRunRow(PlannerRow):
    """The settings and measured result of one distinct run attempt."""

    __schema_stem__: ClassVar[str] = "feed-ingest-plan-run"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-26",
            change="Name pre-fetch and fresh selection health captures separately.",
            why="Each measured capture records its purpose without relying on list order.",
        ),
        *PlannerRow.__changelog__,
    )

    run_id: RunId
    started_at: RecordedInstant
    duration_ms: Count | None
    status: Literal["completed", "partial", "failed"]
    failure_code: Code | None
    selected_count: Count
    strategy: Literal["bin-pack", "round-robin", "none"]
    dispatch_count: Count
    selected_articles_artifact: RelPath | None
    api_timings: list[PlanApiTiming]
    date: DateStamp
    attempt: PositiveCount
    lifecycle_window_days: PositiveCount
    reliability_floor: Weight
    reliability_penalty_enabled: bool
    evaluated_at: RecordedInstant
    request_report_closed_days: PositiveCount
    reliability_window_days: PositiveCount
    selection_started_at_utc: RecordedInstant | None

    @model_validator(mode="after")
    def validate_run_day(self) -> Self:
        if self.date != self.started_at[:10] or not self.run_id.startswith(f"{self.date}-"):
            raise ValueError("run date and run_id must match the UTC day of started_at")
        return self
