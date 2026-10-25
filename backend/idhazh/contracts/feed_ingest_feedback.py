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
    """One source's request estimate in the legacy operational-state snapshot."""

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
        if (self.measured_target_requests is None) != (
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
    """Which saved revision a selection captured, including both evidence windows."""

    status: Literal["current", "stale_fallback", "unavailable"]
    state_revision: PositiveCount | None
    notices: list[Literal["restrictions_unverified"]] = Field(
        default_factory=list, json_schema_extra={"default": []},
    )
    lifecycle_status: Literal["complete", "partial", "unavailable"]
    lifecycle_window_days: PositiveCount
    lifecycle_window_start: DateStamp | None
    lifecycle_window_end: DateStamp | None
    request_status: Literal["complete", "partial", "unavailable"]
    request_window_days: PositiveCount
    request_window_start: DateStamp | None
    request_window_end: DateStamp | None

    @model_validator(mode="after")
    def validate_read(self) -> Self:
        expected_notices = ["restrictions_unverified"] if self.status == "unavailable" else []
        if self.notices != expected_notices:
            raise ValueError("an unavailable state has the neutral restrictions warning only")
        if self.status == "unavailable":
            if any(value is not None for value in (
                self.state_revision,
                self.lifecycle_window_start,
                self.lifecycle_window_end,
                self.request_window_start,
                self.request_window_end,
            )):
                raise ValueError("unavailable state has no saved revision or window")
            if self.lifecycle_status != "unavailable" or self.request_status != "unavailable":
                raise ValueError("unavailable state has unavailable evidence components")
        else:
            if self.state_revision is None or any(value is None for value in (
                self.request_window_start, self.request_window_end,
            )):
                raise ValueError("a saved state reading retains its revision and request window")
            if (self.lifecycle_window_start is None) != (self.lifecycle_window_end is None):
                raise ValueError("lifecycle represented-day bounds are available together")
            if self.lifecycle_status != "unavailable" and (
                self.lifecycle_window_start is None or self.lifecycle_window_end is None
            ):
                raise ValueError("known lifecycle evidence retains its represented-day bounds")
            if self.request_status == "unavailable" and any(value is None for value in (
                self.request_window_start, self.request_window_end,
            )):
                raise ValueError("unavailable request evidence still names its configured window")
        if any(start is not None and end is not None and start > end for start, end in (
            (self.lifecycle_window_start, self.lifecycle_window_end),
            (self.request_window_start, self.request_window_end),
        )):
            raise ValueError("operational state window starts after it ends")
        return self


class SelectionStateCapture(Model):
    """The state read at selection start, or an explicit legacy absence."""

    capture_status: Literal["captured", "not_recorded"]
    selection_started_at_utc: Timestamp | None = None
    state: OperationalStateRead | None = None

    @model_validator(mode="after")
    def validate_capture(self) -> Self:
        if self.capture_status == "captured":
            if self.selection_started_at_utc is None or self.state is None:
                raise ValueError("a captured selection state records its clock and state")
        elif self.selection_started_at_utc is not None or self.state is not None:
            raise ValueError("an unrecorded legacy selection has no captured clock or state")
        return self
