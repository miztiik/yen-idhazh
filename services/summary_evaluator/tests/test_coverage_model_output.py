"""Does malformed native work fail before reduction while actual zero remains a valid value?"""

import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_recordings import (
    RecordedCoverageBackend,
    coverage_settings,
    read_coverage_recordings,
)

from summary_evaluator.source_coverage.fail_evaluation import CoverageFailure
from summary_evaluator.source_coverage.score_coverage import score_coverage
from summary_evaluator.source_coverage.validate_model_output import validate_model_output


@pytest.mark.parametrize(
    "results",
    [
        None,
        [],
        [{}, {}],
        [{}],
        [{"coherence": 0.5}],
        [{"fluency": None}],
        [{"fluency": True}],
        [{"fluency": float("nan")}],
        [{"fluency": float("inf")}],
        [{"fluency": -0.1}],
        [{"fluency": 1.1}],
        [{"fluency": 10**1000}],
    ],
)
def test_bad_batch_or_requested_score_is_invalid_model_output(results: object) -> None:
    with pytest.raises(CoverageFailure) as caught:
        validate_model_output(results, 1, "fluency")
    assert caught.value.code == "INVALID_MODEL_OUTPUT"


def test_zero_is_valid_without_a_missing_value_substitution() -> None:
    actual = [{"consistency": 0.0}]
    assert validate_model_output(actual, 1, "consistency") is actual


@pytest.mark.parametrize("dimension", ["fluency", "coherence", "consistency"])
def test_real_reduction_refuses_missing_native_work(dimension: str) -> None:
    inputs, recording = read_coverage_recordings()
    settings = coverage_settings()

    class MissingDimension(RecordedCoverageBackend):
        def evaluate_dimension(
            self, data: list[dict[str, str]], selected: str
        ) -> list[dict[str, float]]:
            genuine = super().evaluate_dimension(data, selected)
            if selected == dimension:
                genuine[0].pop(selected)
            return genuine

    backend = MissingDimension(recording.cases[0], settings, REPOSITORY)
    with pytest.raises(CoverageFailure) as caught:
        score_coverage(
            inputs.cases[0].source_text,
            inputs.cases[0].summary_text,
            settings.preparation,
            backend,
        )
    assert caught.value.code == "INVALID_MODEL_OUTPUT"
    assert backend.calls == ["fluency", "coherence", "consistency"].index(dimension) + 1
