"""Is every requested native dimension present, finite and complete before any reduction?"""

import math
from typing import cast

from summary_evaluator.source_coverage.fail_evaluation import CoverageFailure


def validate_model_output(
    results: object, expected_count: int, dimension: str
) -> list[dict[str, float]]:
    if not isinstance(results, list) or len(results) != expected_count or expected_count <= 0:
        raise CoverageFailure("INVALID_MODEL_OUTPUT")
    for result in results:
        if not isinstance(result, dict) or dimension not in result:
            raise CoverageFailure("INVALID_MODEL_OUTPUT")
        value = result[dimension]
        if type(value) not in (int, float):
            raise CoverageFailure("INVALID_MODEL_OUTPUT")
        try:
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise CoverageFailure("INVALID_MODEL_OUTPUT")
        except OverflowError:
            raise CoverageFailure("INVALID_MODEL_OUTPUT") from None
    return cast(list[dict[str, float]], results)
