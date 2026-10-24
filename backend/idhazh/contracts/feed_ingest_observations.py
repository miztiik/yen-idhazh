"""Which individual feed and document operations retain their measured evidence?"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, UUID5, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, RunId, Sha256, Slug, Timestamp
from idhazh.contracts.feed_ingest_candidate import Count, NonEmpty, PositiveCount
from idhazh.contracts.feed_ingest_diagnostics import ExtractionFailure, FetchFailure

HttpStatus = Annotated[StrictInt, Field(ge=100, le=599)]
RequestPhase = Literal["validation", "robots", "target"]
RequestCoverage = Literal["complete", "partial", "unknown"]
OperationOutcome = Literal["success", "empty", "failed", "not_attempted", "unavailable"]
Attribution = Literal["source", "pipeline", "unresolved"]
FailureCode = FetchFailure | ExtractionFailure | Literal["malformed-feed"]


class DocumentObservationRecord(Contract):
    """One immutable operation fact, distinct from its event stream and summary."""

    version: Literal["2026-10-24"] = "2026-10-24"
    __schema_stem__: ClassVar[str] = "feed-ingest-document-observation"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-24",
            change="Declare per-operation observations with scoped request accounting.",
            why="Later feedback must retain actual work and partial failures without a duplicate event contract.",
        ),
    )

    event_id: UUID5
    caused_by_event_id: UUID5 | None
    observed_run_id: RunId | None
    observed_attempt: PositiveCount | None
    correlation_id: NonEmpty | None
    source_id: Slug | None
    publisher_id: Slug | None
    article_id: Sha256 | None
    candidate_id: Sha256 | None
    operation: Literal["fetch", "parse", "attempt"]
    outcome: OperationOutcome
    occurred_at: Timestamp
    duration_ms: Count | None
    http_status: HttpStatus | None
    attribution: Attribution | None
    failure_code: FailureCode | None
    request_phase: RequestPhase | None
    request_sequence: Count | None
    retry: Count | None
    dispatched_request_count: Count | None
    request_coverage: RequestCoverage | None

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.event_id == self.caused_by_event_id:
            raise ValueError("an observation cannot cause itself")
        if self.observed_attempt is not None and self.observed_run_id is None:
            raise ValueError("an observed run attempt requires its run identity")
        if self.publisher_id is not None and self.source_id is None:
            raise ValueError("a publisher identity requires its source identity")
        if self.outcome == "failed":
            if self.attribution is None:
                raise ValueError("a failed operation records its attribution status")
        elif self.attribution is not None or self.failure_code is not None:
            raise ValueError("only a failed operation records failure attribution or cause")

        request_fields = (
            self.request_phase,
            self.request_sequence,
            self.retry,
            self.dispatched_request_count,
            self.request_coverage,
        )
        if self.operation == "attempt":
            if any(value is None for value in (
                self.request_phase, self.request_sequence, self.retry, self.request_coverage
            )):
                raise ValueError("an attempt records its phase, order, retry and request coverage")
            if self.request_coverage == "complete" and self.dispatched_request_count is None:
                raise ValueError("complete request coverage records its measured count")
            if self.request_coverage == "unknown" and self.dispatched_request_count is not None:
                raise ValueError("unknown request coverage has no measured count")
        elif any(value is not None for value in request_fields):
            raise ValueError("phase-specific request accounting belongs to attempt observations")
        return self
