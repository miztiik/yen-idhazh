"""Which body-free errors describe failed UniEval input, dimensions and processes?"""

from typing import Final, Literal, Self

from pydantic import ConfigDict, model_validator

from summary_evaluator.shared.contracts.base import Count, PositiveCount
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode, ErrorPolicy
from summary_evaluator.unieval.contracts.unieval_contract import Dimension, UnievalContract

UnievalHealthErrorCode = (
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
UnievalErrorCode = UnievalHealthErrorCode | Literal[
    "MODEL_INPUT_TOO_LONG", "WINDOW_BUDGET_INSUFFICIENT"
]
UNIEVAL_ERROR_VERSION: Final = "2026-11-09"
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
        "MODEL_INPUT_TOO_LONG": ErrorPolicy(
            400, "The complete model input exceeds the configured token allowance."
        ),
        "WINDOW_BUDGET_INSUFFICIENT": ErrorPolicy(
            400,
            "Source windows cannot reserve forward progress and required overlap "
            "within the configured input allowance.",
        ),
    }
)


class UnievalError(UnievalContract):
    model_config = ConfigDict(
        json_schema_extra={
            "version": UNIEVAL_ERROR_VERSION,
            "readCompatibility": "unmeasured errors may omit both token fields",
            "changelog": [
                {
                    "version": UNIEVAL_ERROR_VERSION,
                    "change": "Pair assembled input counts with their configured allowance.",
                },
                {"version": "2026-11-04", "change": "Declare fixed body-free failure messages."},
            ],
        }
    )
    code: UnievalErrorCode
    dimension: Dimension | None
    index: Count | None
    message: str
    input_tokens: Count | None = None
    allowed_tokens: PositiveCount | None = None

    @model_validator(mode="after")
    def require_declared_message(self) -> Self:
        if self.message != POLICIES[self.code].message:
            raise ValueError("The error requires its fixed safe message")
        if self.code == "WINDOW_BUDGET_INSUFFICIENT" and (
            self.dimension != "consistency" or self.index is not None
        ):
            raise ValueError("Window geometry requires consistency planning, not a comparison")
        if (self.input_tokens is None) != (self.allowed_tokens is None):
            raise ValueError("Input and allowance measurements must be supplied together")
        if self.code == "MODEL_INPUT_TOO_LONG" and self.input_tokens is None:
            raise ValueError("Predictor refusal requires an assembled-input measurement")
        if self.input_tokens is not None and self.allowed_tokens is not None:
            if self.input_tokens <= self.allowed_tokens:
                raise ValueError("A measured refusal must exceed its configured allowance")
            if self.code == "MODEL_INPUT_TOO_LONG":
                if self.dimension is not None or self.index is not None:
                    raise ValueError("Predictor refusal has no comparison identity")
            elif (
                self.index is None
                or (self.code == "SUMMARY_SENTENCE_TOO_LONG"
                    and self.dimension not in ("fluency", "consistency"))
                or (self.code == "COHERENCE_INPUT_TOO_LONG" and self.dimension != "coherence")
                or (self.code == "RELEVANCE_INPUT_TOO_LONG" and self.dimension != "relevance")
                or (self.code == "CONSISTENCY_INPUT_TOO_LONG" and self.dimension != "consistency")
                or self.code not in (
                    "SUMMARY_SENTENCE_TOO_LONG", "COHERENCE_INPUT_TOO_LONG",
                    "RELEVANCE_INPUT_TOO_LONG", "CONSISTENCY_INPUT_TOO_LONG",
                )
            ):
                raise ValueError("Measured refusal requires its affected dimension and comparison")
        return self

    @classmethod
    def from_code(
        cls,
        code: UnievalErrorCode,
        dimension: Dimension | None = None,
        index: int | None = None,
        *,
        input_tokens: int | None = None,
        allowed_tokens: int | None = None,
    ) -> Self:
        return cls(
            code=code, dimension=dimension, index=index, message=POLICIES[code].message,
            input_tokens=input_tokens, allowed_tokens=allowed_tokens,
        )
