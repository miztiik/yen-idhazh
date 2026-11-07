"""Do coverage recordings bind bounded inputs and genuine complete dimension calls?"""

import pytest
from pydantic import ValidationError

from idhazh.contracts.coverage_model_recording import (
    CoverageDimensionCall,
    CoverageRecordingCaseInput,
    CoverageRecordingInputs,
)


def test_capture_inputs_are_bounded_and_distinct() -> None:
    inputs = CoverageRecordingInputs(
        max_cases=1,
        max_input_bytes=64,
        cases=(
            CoverageRecordingCaseInput(
                id="one", source_text="Prepared source.", summary_text="Summary."
            ),
        ),
    )
    assert inputs.version == "2026-11-07"
    with pytest.raises(ValidationError):
        CoverageRecordingInputs.model_validate(
            {**inputs.model_dump(), "cases": inputs.cases + inputs.cases}
        )
    with pytest.raises(ValidationError):
        CoverageRecordingInputs.model_validate({**inputs.model_dump(), "max_input_bytes": 1})


@pytest.mark.parametrize("results", [(), ({"coherence": 0.5},), ({"fluency": float("nan")},)])
def test_recordings_refuse_missing_or_nonfinite_model_results(results: object) -> None:
    with pytest.raises(ValidationError):
        CoverageDimensionCall.model_validate(
            {
                "index": 0,
                "dimension": "fluency",
                "overall": False,
                "inputs": ({"system_output": "A complete sentence."},),
                "results": results,
            }
        )


def test_a_genuine_zero_is_a_complete_recorded_score() -> None:
    call = CoverageDimensionCall(
        index=0,
        dimension="fluency",
        overall=False,
        inputs=({"system_output": "A complete sentence."},),
        results=({"fluency": 0.0},),
    )
    assert call.results[0]["fluency"] == 0.0
