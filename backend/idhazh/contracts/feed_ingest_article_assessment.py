"""Per-candidate evidence and decisions at each planning stage."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Sha256,
    Slug,
    Timestamp,
    Url,
    derive_url_key,
)
from idhazh.contracts.feed_ingest_candidate import (
    ArticleLabels,
    NonEmpty,
    PlanningStage,
    PolicyIdentity,
    ScoreEvidence,
    SourceSnapshot,
)
from idhazh.contracts.feed_ingest_rejection import REASON_STAGES, DropReason
from idhazh.contracts.sources import SourceForm

Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]
FiniteNonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveFinite = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class ArticleAssessmentRecord(Contract):
    """One source candidate's evidence and decision at one ordered stage."""

    __schema_stem__: ClassVar[str] = "feed-ingest-article-assessment"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-20",
            change="Declare stage-specific article assessment evidence.",
            why="Audit rows keep measured quality separate from source and portfolio effects.",
        ),
    )
    version: Literal["2026-10-20"] = "2026-10-20"

    date: DateStamp
    correlation_id: NonEmpty
    candidate_id: Sha256
    source_id: Slug
    source: SourceSnapshot
    labels: ArticleLabels
    canonical_url: Url | None
    url_key: Sha256 | None
    stage: PlanningStage
    decision: Literal["admitted", "rejected", "selected"]
    reason: DropReason | None
    observed_at: Timestamp
    policy: PolicyIdentity

    effective_published_at: Timestamp | None
    publication_clock: Literal["published_at", "fetched_at", "unavailable"]
    age_hours: FiniteNonNegative | None
    max_age_hours: PositiveFinite | None

    extracted_word_count: Count | None
    source_form: SourceForm
    extraction_outcome: Literal["success", "failed", "not_attempted", "unavailable"]
    word_threshold: PositiveCount | None

    author_present: bool | None
    publisher_identity: NonEmpty | None
    attribution_status: Literal["available", "unavailable"]

    paywall: bool | None
    categories: list[NonEmpty] | None
    required_fields_present: bool | None
    suitability_status: Literal["available", "unavailable"]

    informative_verdict_status: Literal["not_assessed", "assessed"]
    informative_verdict: bool | None
    informative_evaluator_version: NonEmpty | None
    suitability_verdict_status: Literal["not_assessed", "assessed"]
    suitability_verdict: bool | None
    suitability_evaluator_version: NonEmpty | None

    score_evidence: ScoreEvidence | None
    score_evidence_status: Literal["not_assessed", "assessed"]

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.source_id != self.source.source_id:
            raise ValueError("source_id must match the recorded source snapshot")
        if self.date != self.observed_at[:10]:
            raise ValueError("date must match the UTC observation day")
        if (self.canonical_url is None) != (self.url_key is None):
            raise ValueError("article URL and url_key are available together")
        if self.canonical_url is not None and self.url_key != derive_url_key(self.canonical_url):
            raise ValueError("url_key must match canonical_url")
        if (self.decision == "rejected") != (self.reason is not None):
            raise ValueError("only rejected decisions carry a rejection reason")
        if self.reason is not None and self.stage not in REASON_STAGES[self.reason]:
            raise ValueError("rejection reason is not valid for the recorded stage")
        if self.publication_clock == "unavailable":
            if self.effective_published_at is not None or self.age_hours is not None:
                raise ValueError("unavailable publication timing carries no timestamp or age")
        elif self.effective_published_at is None or self.age_hours is None:
            raise ValueError("available publication timing carries its timestamp and age")
        if (self.age_hours is None) != (self.max_age_hours is None):
            raise ValueError("age and its effective cutoff are recorded together")
        if self.extraction_outcome == "success":
            if self.extracted_word_count is None or self.word_threshold is None:
                raise ValueError("successful extraction records count and threshold")
        elif self.extraction_outcome == "failed":
            if self.word_threshold is None:
                raise ValueError("failed extraction records the applied word threshold")
        elif self.extracted_word_count is not None or self.word_threshold is not None:
            raise ValueError("unperformed extraction has no count or threshold")
        if self.attribution_status == "unavailable":
            if self.author_present is not None or self.publisher_identity is not None:
                raise ValueError("unavailable attribution carries no inferred values")
        elif self.author_present is None:
            raise ValueError("available attribution records whether a byline exists")
        if self.suitability_status == "unavailable":
            if any(
                value is not None
                for value in (self.paywall, self.categories, self.required_fields_present)
            ):
                raise ValueError("unavailable suitability carries no inferred values")
        elif any(
            value is None
            for value in (self.paywall, self.categories, self.required_fields_present)
        ):
            raise ValueError("available suitability records each required check")
        for status, verdict, evaluator, name in (
            (
                self.informative_verdict_status,
                self.informative_verdict,
                self.informative_evaluator_version,
                "informative",
            ),
            (
                self.suitability_verdict_status,
                self.suitability_verdict,
                self.suitability_evaluator_version,
                "suitability",
            ),
        ):
            assessed = status == "assessed"
            if assessed != (verdict is not None and evaluator is not None):
                raise ValueError(f"{name} verdict and evaluator version match assessed status")
        if (self.score_evidence_status == "assessed") != (self.score_evidence is not None):
            raise ValueError("score evidence must match its availability status")
        return self
