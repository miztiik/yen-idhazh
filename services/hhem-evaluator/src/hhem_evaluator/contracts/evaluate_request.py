"""Which texts and omittable controls may a caller supply?"""

from typing import Self

from pydantic import Field, StrictBool, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from hhem_evaluator.shared.contracts.base import (
    Count,
    NativeContract,
    NonblankText,
    PositiveCount,
    Uuid4,
)
from hhem_evaluator.shared.contracts.optional_fields import is_absent, omit_default


class EvaluateRequest(NativeContract):
    """Keep input strings unchanged and resolve no operational defaults here."""

    source_text: NonblankText
    summary_text: NonblankText
    full_source_text: NonblankText | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    hhem_full: StrictBool | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    include_window_details: StrictBool | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    chunk_words: PositiveCount | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    chunk_overlap_words: Count | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    request_id: Uuid4 | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    correlation_id: Uuid4 | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator(
        "full_source_text",
        "hhem_full",
        "include_window_details",
        "chunk_words",
        "chunk_overlap_words",
        "request_id",
        "correlation_id",
        mode="after",
    )
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit an unused field instead of supplying null")
        return value


class EffectiveSettings(NativeContract):
    """Validate the complete control set after startup defaults are applied."""

    chunk_words: PositiveCount
    chunk_overlap_words: Count
    hhem_full: StrictBool
    include_window_details: StrictBool

    @model_validator(mode="after")
    def require_valid_overlap(self) -> Self:
        if self.chunk_overlap_words >= self.chunk_words:
            raise ValueError("chunk_overlap_words must be smaller than chunk_words")
        return self
