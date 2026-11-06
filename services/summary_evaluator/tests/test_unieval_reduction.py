"""Verify parent progress identity and numeric completion rules without a model substitute."""

import pytest
from summary_evaluator_cases.unieval_cases import read_unieval_recordings, unieval_settings

from summary_evaluator.shared.read_process_identity import read_process_identity
from summary_evaluator.unieval.contracts.unieval_contract import DIMENSIONS, UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_result import UnievalScores
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    UnievalPrediction,
    UnievalPrepared,
)
from summary_evaluator.unieval.fail_unieval import UnievalFailure
from summary_evaluator.unieval.reduce_unieval import UnievalState


def test_zero_is_complete_data_and_duplicate_or_unfinished_progress_is_refused() -> None:
    inputs, predictions, identity = read_unieval_recordings()
    _, settings = unieval_settings()
    recorded = predictions.cases[0]
    state = UnievalState()
    state.set_request(inputs.cases[0].request)
    state.model = identity
    state.worker = read_process_identity(1, settings.worker.max_proc_identity_bytes)
    state.accept_plan(
        UnievalPrepared(
            version=UNIEVAL_VERSION,
            execution_id=state.execution_id,
            generation=1,
            effective_settings=recorded.effective_settings,
            work=recorded.work,
            errors=recorded.errors,
        ),
        settings,
    )
    with pytest.raises(UnievalFailure, match="invalid packet"):
        state.require_finished()
    first = recorded.comparisons[0]
    packet = UnievalPrediction(
        version=UNIEVAL_VERSION,
        execution_id=state.execution_id,
        generation=1,
        dimension=first.dimension,
        index=first.index,
        sentence_index=first.sentence_index,
        source_index=first.source_index,
        score=first.score,
        error=None,
    )
    state.accept_prediction(packet)
    with pytest.raises(UnievalFailure, match="invalid packet"):
        state.accept_prediction(packet)
    for comparison in recorded.comparisons[1:]:
        state.accept_prediction(
            UnievalPrediction(
                version=UNIEVAL_VERSION,
                execution_id=state.execution_id,
                generation=1,
                dimension=comparison.dimension,
                index=comparison.index,
                sentence_index=comparison.sentence_index,
                source_index=comparison.source_index,
                score=comparison.score,
                error=None,
            )
        )
    state.require_finished()
    actual = state.result()
    assert actual.status == "complete"
    payload = actual.model_dump()
    payload["scores"] = UnievalScores(**dict.fromkeys(DIMENSIONS, 0.0))
    zeros = type(actual).model_validate(payload)
    assert zeros.status == "complete"
    assert all(value == 0.0 for value in zeros.scores.model_dump().values())
    payload["scores"] = actual.scores.model_copy(update={"relevance": None})
    with pytest.raises(ValueError, match="Status must describe"):
        type(actual).model_validate(payload)
