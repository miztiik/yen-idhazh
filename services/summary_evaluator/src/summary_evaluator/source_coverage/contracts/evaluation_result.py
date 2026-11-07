"""Which unchanged metrics and evidence does a complete coverage evaluation return?"""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from summary_evaluator.shared.contracts.base import Count, PositiveCount, Score
from summary_evaluator.shared.contracts.optional_fields import is_absent, omit_default
from summary_evaluator.source_coverage.contracts.base import CoverageContract


class SentenceEvidence(CoverageContract):
    sentence_index: PositiveCount
    text: str
    score: Score
    matched_chunk: PositiveCount
    supported: bool
    source_sentence: str | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    reason: str | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator("source_sentence", "reason")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit unavailable historical evidence instead of supplying null")
        return value


class UncoveredSection(CoverageContract):
    chunk_index: PositiveCount
    chunk_total: PositiveCount
    excerpt: str
    max_similarity_score: Score
    reason: str


class CoverageMetrics(CoverageContract):
    overall_consistency: Score
    coherence: Score
    fluency: Score
    document_chunks_total: PositiveCount
    document_chunks_covered: Count
    chunk_coverage_percent: float = Field(strict=True, ge=0, le=100)
    sentence_breakdown: tuple[SentenceEvidence, ...]
    uncovered_sections: tuple[UncoveredSection, ...] | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator("uncovered_sections")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit unavailable historical sections instead of supplying null")
        return value

    @model_validator(mode="after")
    def require_real_chunk_links(self) -> Self:
        if self.document_chunks_covered > self.document_chunks_total:
            raise ValueError("Covered chunks cannot exceed the document's chunk count")
        if any(item.matched_chunk > self.document_chunks_total for item in self.sentence_breakdown):
            raise ValueError("Sentence evidence must link to an existing chunk")
        if self.uncovered_sections is not None and any(
            item.chunk_total != self.document_chunks_total
            or item.chunk_index > self.document_chunks_total
            for item in self.uncovered_sections
        ):
            raise ValueError("Uncovered sections must identify existing document chunks")
        return self


class CoverageResult(CoverageContract):
    status: Literal["success"] = "success"
    metrics: CoverageMetrics
