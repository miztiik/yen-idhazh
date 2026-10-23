"""Which durable operator request and fetched document may a later request replay?"""

import json
from typing import Annotated, ClassVar, Literal, Self

from pydantic import UUID4, UUID5, Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    RunId,
    Sha256,
    Slug,
    Timestamp,
    Url,
)
from idhazh.contracts.feed_ingest_candidate import Count, NonEmpty
from idhazh.contracts.feed_ingest_diagnostics import FetchFailure

HttpStatus = Annotated[StrictInt, Field(ge=100, le=599)]
ErrorCode = Annotated[str, Field(max_length=64, pattern=r"^[A-Z][A-Z0-9_]*$")]


class FetchAttempt(Model):
    """One measured DNS/robots/target attempt; HTTP statuses are protocol facts."""

    phase: Literal["validation", "robots", "target"]
    sequence: Count
    retry: Count
    duration_ms: Count
    http_status: HttpStatus | None
    failure: FetchFailure | None
    error_code: ErrorCode | None


class PlannerObservation(Model):
    """Distinct stage and attempt events retain their cause and article identity."""

    event_id: UUID5
    caused_by_event_id: UUID5 | None
    correlation_id: NonEmpty
    run_id: RunId
    article_id: Sha256
    source_id: Slug
    occurred_at: Timestamp
    operation: Literal["fetch", "parse", "attempt"]


class FetchedDocument(Contract):
    """Private fetch bytes and measured evidence, never a caller-selected path."""

    version: Literal["2026-10-23"] = "2026-10-23"
    __schema_stem__: ClassVar[str] = "fetched-document"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-23",
            change="Declare durable fetched documents and causal observations.",
            why="Parsing reads fetched bytes by validated identity, never by a caller path.",
        ),
    )
    kind: Literal["feed", "article"]
    canonical_url: Url
    article_id: Sha256
    source_id: Slug
    body: str | None
    http_status: HttpStatus | None
    failure: FetchFailure | None
    robots: Literal["allowed", "denied", "unknown"] | None
    error_code: ErrorCode | None
    robots_failure: FetchFailure | None
    robots_http_status: HttpStatus | None
    attempts: list[FetchAttempt]
    observation: PlannerObservation
    attempt_observations: list[PlannerObservation]
    body_sha256: Sha256 | None

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        if (self.body is None) != (self.body_sha256 is None):
            raise ValueError("body and body digest must be available together")
        if (
            self.observation.operation != "fetch"
            or self.observation.article_id != self.article_id
            or self.observation.source_id != self.source_id
        ):
            raise ValueError("fetch observation must retain document identity")
        if len(self.attempts) != len(self.attempt_observations) or any(
            attempt.sequence != index for index, attempt in enumerate(self.attempts)
        ):
            raise ValueError("attempt observations must match the ordered attempts")
        return self


class PlannerOperation(Contract):
    """One keyed request holds its captured identity and exact completed response."""

    version: Literal["2026-10-23"] = "2026-10-23"
    __schema_stem__: ClassVar[str] = "planner-operation"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-23",
            change="Declare durable keyed operator request replay.",
            why="Restarts must retain request identity and the exact completed response.",
        ),
    )
    request_id: UUID4
    operation: Literal["fetch", "parse", "plan"]
    input_sha256: Sha256
    config_sha256: Sha256
    run_id: RunId
    correlation_id: UUID4
    created_at: Timestamp
    state: Literal["started", "complete"]
    response_json: str | None
    artifact: FetchedDocument | None

    @model_validator(mode="after")
    def validate_completion(self) -> Self:
        has_output = self.response_json is not None or self.artifact is not None
        if self.state == "started" and has_output:
            raise ValueError("started requests cannot carry completed output")
        if self.state == "complete":
            fetch_artifact_matches = (self.operation == "fetch") == (self.artifact is not None)
            if self.response_json is None or not fetch_artifact_matches:
                raise ValueError(
                    "completed requests need a response and only fetch carries an artifact"
                )
            json.loads(self.response_json)
        return self
