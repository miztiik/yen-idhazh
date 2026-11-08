"""Which original request and controls identify genuine four-score recordings?"""

from pydantic import AwareDatetime, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

from summary_evaluator.shared.contracts.base import (
    ContextIdentity,
    Count,
    NonblankText,
    Score,
    Sha256,
    Uuid4,
)
from summary_evaluator.shared.contracts.optional_fields import is_absent, omit_default
from summary_evaluator.unieval.contracts.previous_unieval_result import (
    PreviousEffectiveUnievalControls,
    PreviousUnievalControls,
)
from summary_evaluator.unieval.contracts.unieval_contract import (
    Dimension,
    SourceMode,
    UnievalContract,
    UnievalVersion,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_result import UnievalWork


class PreviousUnievalRequest(UnievalContract):
    source_text: NonblankText
    summary_text: NonblankText
    reference_summary_text: NonblankText
    consistency_source_mode: SourceMode | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    request_id: Uuid4 | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    correlation_id: Uuid4 | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )

    @field_validator("consistency_source_mode", "request_id", "correlation_id", mode="after")
    @classmethod
    def refuse_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit an unused control instead of supplying null")
        return value


class UnievalRecordingInput(UnievalContract):
    id: ContextIdentity
    request: PreviousUnievalRequest
    controls: PreviousUnievalControls


class UnievalRecordingInputs(UnievalContract):
    version: UnievalVersion
    cases: tuple[UnievalRecordingInput, ...]


class RecordedUnievalComparison(UnievalContract):
    dimension: Dimension
    index: Count
    sentence_index: Count | None
    source_index: Count | None
    prompt_sha256: Sha256
    score: Score


class RecordedUnievalCase(UnievalContract):
    id: ContextIdentity
    input_sha256: Sha256
    effective_settings: PreviousEffectiveUnievalControls
    work: UnievalWork
    errors: tuple[UnievalError, ...]
    comparisons: tuple[RecordedUnievalComparison, ...]


class UnievalRecordingPredictions(UnievalContract):
    version: UnievalVersion
    recorded_at: AwareDatetime
    model_identity_sha256: Sha256
    cases: tuple[RecordedUnievalCase, ...]
