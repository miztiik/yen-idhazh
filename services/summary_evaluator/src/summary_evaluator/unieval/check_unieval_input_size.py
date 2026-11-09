"""Which complete assembled input exceeds its allowance, and which dimension does it affect?"""

from typing import Final

from summary_evaluator.unieval.contracts.unieval_contract import Dimension
from summary_evaluator.unieval.contracts.unieval_error import UnievalError, UnievalErrorCode

INPUT_SIZE_CODES: Final[dict[Dimension, UnievalErrorCode]] = {
    "fluency": "SUMMARY_SENTENCE_TOO_LONG",
    "coherence": "COHERENCE_INPUT_TOO_LONG",
    "consistency": "CONSISTENCY_INPUT_TOO_LONG",
    "relevance": "RELEVANCE_INPUT_TOO_LONG",
}


def check_unieval_input_size(
    input_tokens: int,
    allowed_tokens: int,
    dimension: Dimension | None = None,
    index: int | None = None,
    *,
    summary_sentence_only: bool = False,
) -> UnievalError | None:
    if input_tokens <= allowed_tokens:
        return None
    code: UnievalErrorCode = (
        "SUMMARY_SENTENCE_TOO_LONG" if summary_sentence_only
        else INPUT_SIZE_CODES[dimension] if dimension is not None
        else "MODEL_INPUT_TOO_LONG"
    )
    return UnievalError.from_code(
        code, dimension, index, input_tokens=input_tokens, allowed_tokens=allowed_tokens,
    )


def project_unieval_error(
    error: UnievalError, dimension: Dimension, index: int,
) -> UnievalError:
    return UnievalError.from_code(
        INPUT_SIZE_CODES[dimension] if error.code == "MODEL_INPUT_TOO_LONG" else error.code,
        dimension,
        index,
        input_tokens=error.input_tokens,
        allowed_tokens=error.allowed_tokens,
    )
