"""Which body-free errors describe failed UniEval input, dimensions and processes?"""

from typing import Literal, Self

from pydantic import model_validator

from summary_evaluator.shared.contracts.base import Count
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode, ErrorPolicy
from summary_evaluator.unieval.contracts.unieval_contract import Dimension, UnievalContract

UnievalErrorCode = (
    ErrorCode
    | Literal[
        "SUMMARY_SENTENCE_TOO_LONG",
        "COHERENCE_INPUT_TOO_LONG",
        "RELEVANCE_INPUT_TOO_LONG",
        "CONSISTENCY_INPUT_TOO_LONG",
        "COMPARISON_LIMIT_EXCEEDED",
        "TOKENIZER_FAILED",
    ]
)
POLICIES: dict[UnievalErrorCode, ErrorPolicy] = {
    code: policy for code, policy in ERROR_POLICIES.items()
}
POLICIES.update(
    {
        "SUMMARY_SENTENCE_TOO_LONG": ErrorPolicy(
            400, "A complete summary sentence exceeds the configured prompt allowance."
        ),
        "COHERENCE_INPUT_TOO_LONG": ErrorPolicy(
            400, "The complete source and summary exceed the coherence prompt allowance."
        ),
        "RELEVANCE_INPUT_TOO_LONG": ErrorPolicy(
            400, "The complete reference and summary exceed the relevance prompt allowance."
        ),
        "CONSISTENCY_INPUT_TOO_LONG": ErrorPolicy(
            400, "The complete consistency prompt exceeds the configured allowance."
        ),
        "COMPARISON_LIMIT_EXCEEDED": ErrorPolicy(
            400, "The evaluation exceeds the configured comparison allowance."
        ),
        "TOKENIZER_FAILED": ErrorPolicy(
            500, "The declared local text resources could not be used."
        ),
    }
)


class UnievalError(UnievalContract):
    code: UnievalErrorCode
    dimension: Dimension | None
    index: Count | None
    message: str

    @model_validator(mode="after")
    def require_declared_message(self) -> Self:
        if self.message != POLICIES[self.code].message:
            raise ValueError("The error requires its fixed safe message")
        return self

    @classmethod
    def from_code(
        cls,
        code: UnievalErrorCode,
        dimension: Dimension | None = None,
        index: int | None = None,
    ) -> Self:
        return cls(code=code, dimension=dimension, index=index, message=POLICIES[code].message)
