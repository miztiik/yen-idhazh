"""Which exact texts and explicit relevance selection can UniEval accept?"""

from typing import Self

from pydantic import Field, StrictBool, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from summary_evaluator.shared.contracts.base import Count, NonblankText, PositiveCount, Uuid4
from summary_evaluator.shared.contracts.optional_fields import is_absent, omit_default
from summary_evaluator.unieval.contracts.unieval_contract import SourceMode, UnievalScoringContract


class UnievalRequest(UnievalScoringContract):
    source_text: NonblankText
    summary_text: NonblankText
    reference_summary_text: NonblankText | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    evaluate_relevance: StrictBool | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    consistency_source_mode: SourceMode | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    request_id: Uuid4 | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    correlation_id: Uuid4 | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator(
        "reference_summary_text", "evaluate_relevance", "consistency_source_mode",
        "request_id", "correlation_id", mode="after",
    )
    @classmethod
    def refuse_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit an unused control instead of supplying null")
        return value


class UnievalControls(UnievalScoringContract):
    consistency_source_mode: SourceMode
    evaluate_relevance: StrictBool = False
    max_input_tokens: PositiveCount
    source_window_tokens: PositiveCount
    source_overlap_tokens: Count
    max_source_windows: PositiveCount
    max_comparisons: PositiveCount

    @model_validator(mode="after")
    def require_finite_geometry(self) -> Self:
        if self.source_overlap_tokens >= self.source_window_tokens:
            raise ValueError("Source overlap must be smaller than its target window")
        return self


class EffectiveUnievalControls(UnievalControls):
    evaluate_relevance: StrictBool
    source_budget_tokens: PositiveCount | None
