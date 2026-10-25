"""Which saved operational estimate records one source's request evidence?"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    Model,
    Slug,
    Timestamp,
)
from idhazh.contracts.feed_ingest_candidate import NonEmpty

Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]
UnitInterval = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class FeedIngestOperationalStateRow(Contract):
    """One source's request estimate in a versioned operational-state snapshot."""

    __schema_stem__: ClassVar[str] = "feed-ingest-operational-state"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-25",
            change="Declare per-source request estimates and their saved evidence window.",
            why="A later selection needs a typed revision without replacing raw observations.",
        ),
    )

    version: Literal["2026-10-25"] = "2026-10-25"
    date: DateStamp
    state_revision: PositiveCount
    parent_revision: PositiveCount | None
    written_at_utc: Timestamp
    evidence_cutoff_utc: Timestamp
    window_days: PositiveCount
    window_start: DateStamp
    window_end: DateStamp
    code_revision: CommitSha
    policy_version: NonEmpty
    source_id: Slug
    evidence_start_utc: Timestamp | None
    evidence_end_utc: Timestamp | None
    measured_target_requests: Count | None
    measured_source_wasted_requests: Count | None
    observed_attempted_opportunities: Count
    observed_measured_opportunities: Count
    measured_coverage: UnitInterval | None
    qualification_status: Literal["qualified", "insufficient_support", "unavailable"]
    request_waste_ratio: UnitInterval | None
    operational_penalty: UnitInterval | None

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        if self.parent_revision is not None and self.parent_revision >= self.state_revision:
            raise ValueError("parent revision must be older than the saved state")
        if self.window_start > self.window_end:
            raise ValueError("operational evidence window starts after it ends")
        if (
            self.evidence_start_utc is not None
            and self.evidence_end_utc is not None
            and self.evidence_start_utc > self.evidence_end_utc
        ):
            raise ValueError("observed evidence starts after it ends")
        if (
            self.measured_target_requests is None
        ) != (
            self.measured_source_wasted_requests is None
        ):
            raise ValueError("measured request totals and waste are available together")
        if (
            self.measured_target_requests is not None
            and self.measured_source_wasted_requests is not None
            and self.measured_source_wasted_requests > self.measured_target_requests
        ):
            raise ValueError("wasted requests cannot exceed total requests")
        if self.observed_measured_opportunities > self.observed_attempted_opportunities:
            raise ValueError("measured opportunities cannot exceed attempted opportunities")
        if self.qualification_status == "qualified":
            if (
                self.measured_target_requests is None
                or self.measured_target_requests == 0
                or self.measured_coverage is None
                or self.request_waste_ratio is None
                or self.operational_penalty is None
            ):
                raise ValueError("qualified state has positive measured requests and coverage")
        elif self.request_waste_ratio is not None or self.operational_penalty is not None:
            raise ValueError("unqualified state has no request estimate or score adjustment")
        return self


class OperationalStateRead(Model):
    """Which saved revision a consumer used, including the original fallback window."""

    status: Literal["current", "stale_fallback", "unavailable"]
    state_revision: PositiveCount | None
    window_days: PositiveCount
    window_start: DateStamp | None
    window_end: DateStamp | None

    @model_validator(mode="after")
    def validate_read(self) -> Self:
        if self.status == "unavailable":
            if any(value is not None for value in (
                self.state_revision, self.window_start, self.window_end,
            )):
                raise ValueError("unavailable state has no saved revision or window")
        elif self.state_revision is None or self.window_start is None or self.window_end is None:
            raise ValueError("a saved state reading retains its revision and original window")
        if (
            self.window_start is not None
            and self.window_end is not None
            and self.window_start > self.window_end
        ):
            raise ValueError("operational state window starts after it ends")
        return self
