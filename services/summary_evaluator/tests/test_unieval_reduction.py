"""Verify parent progress identity and applicable numeric completion without a model substitute."""

import hashlib

import pytest
from local_api_host.propagate_trace_context import create_child_operation
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.unieval_cases import (
    read_unieval_recordings,
    recorded_unieval_controls,
    recorded_unieval_request,
    unieval_settings,
)

from summary_evaluator.shared.read_process_identity import read_process_identity
from summary_evaluator.unieval.contracts.unieval_contract import DIMENSIONS
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalScores
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
from summary_evaluator.unieval.contracts.unieval_worker_message import (
    UnievalPrediction,
    UnievalPrepared,
)
from summary_evaluator.unieval.fail_unieval import UnievalFailure
from summary_evaluator.unieval.load_unieval_resources import load_unieval_resources
from summary_evaluator.unieval.reduce_unieval import UnievalState
from summary_evaluator.unieval.score_unieval import UnievalPlan, prepare_unieval


def selected_state(request: UnievalRequest) -> tuple[UnievalState, UnievalPlan, UnievalSettings]:
    _, settings = unieval_settings()
    _, _, identity = read_unieval_recordings()
    plan = prepare_unieval(request, settings, load_unieval_resources(settings, REPOSITORY))
    state = UnievalState()
    state.evaluation_operation = create_child_operation(state.operation_metadata)
    state.set_request(request)
    state.model = identity
    state.worker = read_process_identity(1, settings.worker.max_proc_identity_bytes)
    return state, plan, settings


def prepared_packet(state: UnievalState, plan: UnievalPlan) -> UnievalPrepared:
    assert state.evaluation_operation is not None
    return UnievalPrepared(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=state.evaluation_operation,
        execution_id=state.execution_id,
        generation=1,
        effective_settings=plan.controls,
        relevance_skip_reason=plan.relevance_skip_reason,
        work=plan.work,
        errors=plan.errors,
    )


def test_zero_is_complete_data_and_duplicate_or_unfinished_progress_is_refused() -> None:
    inputs, predictions, identity = read_unieval_recordings()
    _, settings = unieval_settings()
    recorded = predictions.cases[0]
    state = UnievalState()
    state.evaluation_operation = create_child_operation(state.operation_metadata)
    state.set_request(recorded_unieval_request(inputs.cases[0].request))
    state.model = identity
    state.worker = read_process_identity(1, settings.worker.max_proc_identity_bytes)
    state.accept_plan(
        UnievalPrepared(
            version=UNIEVAL_WORKER_VERSION,
            operation_metadata=state.evaluation_operation,
            execution_id=state.execution_id,
            generation=1,
            effective_settings=recorded_unieval_controls(recorded.effective_settings),
            relevance_skip_reason=None,
            work=recorded.work,
            errors=tuple(
                UnievalError.model_validate_json(error.model_dump_json())
                for error in recorded.errors
            ),
        ),
        settings,
    )
    with pytest.raises(UnievalFailure, match="invalid packet"):
        state.require_finished()
    first = recorded.comparisons[0]
    packet = UnievalPrediction(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=state.evaluation_operation,
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
                version=UNIEVAL_WORKER_VERSION,
                operation_metadata=state.evaluation_operation,
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


@pytest.mark.parametrize(
    ("enabled", "reference", "reason"),
    [
        (False, None, "disabled"),
        (False, "\nExact unused reference \u00e9. ", "disabled"),
        (True, None, "reference_not_supplied"),
    ],
)
def test_authorized_relevance_omission_completes_using_only_unchanged_recorded_predictions(
    enabled: bool, reference: str | None, reason: str,
) -> None:
    inputs, predictions, _ = read_unieval_recordings()
    original = inputs.cases[0].request
    payload: dict[str, object] = {
        "source_text": original.source_text, "summary_text": original.summary_text,
        "evaluate_relevance": enabled,
    }
    if reference is not None:
        payload["reference_summary_text"] = reference
    request = UnievalRequest.model_validate(payload)
    state, plan, settings = selected_state(request)
    assert not plan.errors and plan.relevance_skip_reason == reason
    state.accept_plan(prepared_packet(state, plan), settings)
    captured = {
        comparison.prompt_sha256: comparison.score
        for comparison in predictions.cases[0].comparisons
    }
    assert state.evaluation_operation is not None
    for comparison in plan.comparisons:
        assert comparison.dimension != "relevance" and comparison.reference == ""
        state.accept_prediction(UnievalPrediction(
            version=UNIEVAL_WORKER_VERSION,
            operation_metadata=state.evaluation_operation,
            execution_id=state.execution_id,
            generation=1,
            dimension=comparison.dimension,
            index=comparison.index,
            sentence_index=comparison.sentence_index,
            source_index=comparison.source_index,
            score=captured[hashlib.sha256(comparison.prompt.encode("utf-8")).hexdigest()],
            error=None,
        ))
    state.require_finished()
    result = state.result()
    assert result.status == "complete" and result.errors == ()
    assert result.relevance_skip_reason == reason and result.scores.relevance is None
    assert result.reference_summary_sha256 == (
        hashlib.sha256(reference.encode("utf-8")).hexdigest() if reference is not None else None
    )
    assert result.work.relevance.planned is None and result.work.relevance.completed == 0
    assert result.effective_settings is not None
    assert result.effective_settings.evaluate_relevance is enabled
    zeroes = result.scores.model_copy(update={
        "fluency": 0.0, "coherence": 0.0, "consistency": 0.0,
    })
    assert type(result).model_validate(
        result.model_copy(update={"scores": zeroes}).model_dump()
    ).status == "complete"


@pytest.mark.parametrize("fault", ["selection", "skip", "plan", "failure"])
def test_parent_refuses_unauthorized_relevance_selection_skip_work_and_prediction(
    fault: str,
) -> None:
    from summary_evaluator.unieval.contracts.unieval_error import UnievalError
    from summary_evaluator.unieval.contracts.unieval_result import DimensionWork

    inputs, _, _ = read_unieval_recordings()
    request = UnievalRequest.model_validate({
        **inputs.cases[0].request.model_dump(), "evaluate_relevance": False,
    })
    state, plan, settings = selected_state(request)
    packet = prepared_packet(state, plan)
    if fault == "selection":
        packet = packet.model_copy(update={
            "effective_settings": packet.effective_settings.model_copy(
                update={"evaluate_relevance": True}
            ),
            "relevance_skip_reason": None,
        })
    elif fault == "skip":
        packet = packet.model_copy(update={"relevance_skip_reason": "reference_not_supplied"})
    elif fault == "plan":
        packet = packet.model_copy(update={
            "work": packet.work.model_copy(update={"relevance": DimensionWork(planned=1)})
        })
    else:
        packet = packet.model_copy(update={
            "errors": (UnievalError.from_code("RELEVANCE_INPUT_TOO_LONG", "relevance"),)
        })
    with pytest.raises(UnievalFailure, match="invalid packet"):
        state.accept_plan(packet, settings)
    state.accept_plan(prepared_packet(state, plan), settings)
    assert state.evaluation_operation is not None
    with pytest.raises(UnievalFailure, match="invalid packet"):
        state.accept_prediction(UnievalPrediction(
            version=UNIEVAL_WORKER_VERSION,
            operation_metadata=state.evaluation_operation,
            execution_id=state.execution_id,
            generation=1,
            dimension="relevance",
            index=0,
            sentence_index=None,
            source_index=None,
            score=0.0,
            error=None,
        ))
