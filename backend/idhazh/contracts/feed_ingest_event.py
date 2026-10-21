"""Typed audit events exchanged across feed-ingest planning stages."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    RunId,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.feed_ingest_article_assessment import ArticleAssessmentRecord
from idhazh.contracts.feed_ingest_candidate import (
    ArticleLabels,
    NonEmpty,
    PlanningStage,
    PolicyIdentity,
    ScoreEvidence,
    SourceSnapshot,
)
from idhazh.contracts.feed_ingest_rejection import DropReason

Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]

class FeedOutcomePayload(Model):
    """Recorded outcome of one requested or skipped feed."""

    kind: Literal["feed_outcome"]
    source: SourceSnapshot
    fetch_status: Literal[
        "not_requested", "success", "http_failure", "network_failure", "timeout"
    ]
    parse_status: Literal["not_attempted", "success", "empty", "failure"]
    parsed_count: Count | None
    harvested_count: Count | None
    fetch_duration_ms: Count | None
    parse_duration_ms: Count | None
    rejection_reason: DropReason | None


class CandidateDecisionPayload(Model):
    """A stage's decision without copying article text into the audit stream."""

    kind: Literal["candidate_decision"]
    assessment: ArticleAssessmentRecord


class PortfolioChoicePayload(Model):
    """The evidence for a selected item and its portfolio replacement."""

    kind: Literal["portfolio_choice"]
    candidate_id: Sha256
    url_key: Sha256
    editorial_rank: PositiveCount
    scores: ScoreEvidence
    labels: ArticleLabels
    replaced_candidate_id: Sha256 | None
    replacement_reason: Literal["carrier", "cap_relaxation", "none"]

    @model_validator(mode="after")
    def validate_replacement(self) -> Self:
        if (self.replaced_candidate_id is None) != (self.replacement_reason == "none"):
            raise ValueError("replacement identity and reason must agree")
        return self


class StageCompletionPayload(Model):
    """Counts and outcome for one completed planning stage."""

    kind: Literal["stage_completion"]
    stage: PlanningStage
    input_count: Count
    output_count: Count
    terminal_rejection_count: Count
    source_count: Count | None


EventPayload = Annotated[
    FeedOutcomePayload
    | CandidateDecisionPayload
    | PortfolioChoicePayload
    | StageCompletionPayload,
    Field(discriminator="kind"),
]


class FeedIngestEvent(Contract):
    """One ordered audit event carrying only declared decision evidence."""

    __schema_stem__: ClassVar[str] = "feed-ingest-event"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-20",
            change="Declare typed feed-ingest audit event payloads.",
            why="Stage observations need a replayable contract without article text.",
        ),
    )
    version: Literal["2026-10-20"] = "2026-10-20"

    event_id: Sha256
    correlation_id: NonEmpty
    run_id: RunId
    attempt: PositiveCount
    sequence: Count
    occurred_at: Timestamp
    stage: PlanningStage
    audit_event_type: Literal[
        "feed_outcome", "candidate_decision", "portfolio_choice", "stage_completion"
    ]
    source_id: Slug | None
    candidate_id: Sha256 | None
    elapsed_ms: Count
    step_elapsed_ms: Count
    policy: PolicyIdentity
    payload: EventPayload

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.audit_event_type != self.payload.kind:
            raise ValueError("audit_event_type must match the typed payload discriminator")
        if isinstance(self.payload, FeedOutcomePayload):
            if self.source_id != self.payload.source.source_id or self.candidate_id is not None:
                raise ValueError("feed outcome events identify only their source")
        elif isinstance(self.payload, CandidateDecisionPayload):
            assessment = self.payload.assessment
            if (
                self.candidate_id != assessment.candidate_id
                or self.source_id != assessment.source_id
            ):
                raise ValueError("candidate decision events identify source and candidate")
            if self.stage != assessment.stage:
                raise ValueError("candidate decision stage must match the event stage")
            if self.policy != assessment.policy:
                raise ValueError("candidate decision policy must match the event policy")
        elif isinstance(self.payload, PortfolioChoicePayload):
            if self.candidate_id != self.payload.candidate_id or self.source_id is None:
                raise ValueError("portfolio choice events identify source and candidate")
            if self.stage != "curate-article-portfolio":
                raise ValueError("portfolio choices belong to the portfolio stage")
        else:
            if self.candidate_id is not None:
                raise ValueError("stage completion events do not identify a candidate")
            if self.stage != self.payload.stage:
                raise ValueError("stage completion payload must match the event stage")
        return self
