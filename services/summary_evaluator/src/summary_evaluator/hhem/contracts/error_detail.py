"""Which fixed safe failures may cross a public service boundary?"""

from typing import Literal, Self, TypeGuard, get_args

from pydantic import StrictStr, ValidationError, model_validator

from summary_evaluator.hhem.contracts.base import Operation
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.shared.contracts.base import Count, NativeContract
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode

ErrorField = Literal[
    "source_text",
    "summary_text",
    "full_source_text",
    "hhem_full",
    "include_window_details",
    "chunk_words",
    "chunk_overlap_words",
    "request_id",
    "correlation_id",
    "version",
    "worker",
    "worker.generation",
    "worker.pid",
    "worker.start_ticks",
    "model",
    "model.loaded_revision",
    "model.loaded_weights_sha256",
    "model.loaded_config_sha256",
    "score",
    "window_index",
    "start_word",
    "end_word",
]


class ErrorDetail(NativeContract):
    """Reject exception text, caller-chosen field paths and unknown failures."""

    code: ErrorCode
    phase: Operation
    field: ErrorField | None
    window_index: Count | None
    message: StrictStr

    @model_validator(mode="after")
    def require_safe_message(self) -> Self:
        if self.message != ERROR_POLICIES[self.code].message:
            raise ValueError("message must match the declared error code")
        return self

    @classmethod
    def from_code(
        cls,
        code: ErrorCode,
        phase: Operation,
        *,
        field: ErrorField | None = None,
        window_index: int | None = None,
    ) -> Self:
        return cls(
            code=code,
            phase=phase,
            field=field,
            window_index=window_index,
            message=ERROR_POLICIES[code].message,
        )


def is_error_field(value: object) -> TypeGuard[ErrorField]:
    """Recognize only the declared contract path vocabulary."""
    return isinstance(value, str) and value in get_args(ErrorField)


def project_request_error(error: ValidationError) -> ErrorDetail:
    """Discard input echoes, unknown property names and validation diagnostics."""
    location = error.errors(include_input=False, include_context=False, include_url=False)[0]["loc"]
    field = location[0] if location else None
    return ErrorDetail.from_code(
        "INVALID_REQUEST",
        "request",
        field=(field if is_error_field(field) and field in EvaluateRequest.model_fields else None),
    )
