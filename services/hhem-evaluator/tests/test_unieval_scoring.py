"""Prove sentence-by-window reduction and partial truth through the real UniEval API."""

import asyncio

import pytest

from hhem_evaluator.contracts.unieval_result import UnievalResult
from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.unieval_router import UNIEVAL_PATH

from .unieval_cases import (
    UnievalScenario,
    read_unieval_recordings,
    running_unieval,
    unieval_settings,
)


def test_four_scores_use_sentence_maxima_not_one_best_whole_summary_window() -> None:
    async def check() -> None:
        inputs, predictions, _ = read_unieval_recordings()
        case, recorded = inputs.cases[0], predictions.cases[0]
        async with running_unieval() as (client, worker, log):
            response = await client.post(
                UNIEVAL_PATH,
                content=case.request.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
            result = UnievalResult.model_validate_json(response.content)
            assert response.status_code == 200 and result.status == "complete", response.text
            width = len(recorded.work.source_spans)
            values = [
                item.score for item in recorded.comparisons if item.dimension == "consistency"
            ]
            maxima = [max(values[start : start + width]) for start in range(0, len(values), width)]
            assert result.scores.consistency == sum(maxima) / len(maxima)
            for dimension in ("fluency", "coherence", "relevance"):
                scores = [
                    item.score for item in recorded.comparisons if item.dimension == dimension
                ]
                assert getattr(result.scores, dimension) == sum(scores) / len(scores)
            assert result.worker == worker.worker
            assert case.request.source_text not in response.text
            assert case.request.reference_summary_text not in response.text
            assert case.request.summary_text not in log.getvalue()
            assert result.work.consistency.completed == len(values)
        assert worker.exit_confirmed and worker.last_exit is not None

    asyncio.run(check())


def test_normalization_planning_error_keeps_recorded_independent_dimensions() -> None:
    async def check() -> None:
        inputs, predictions, _ = read_unieval_recordings()
        case = next(case for case in inputs.cases if case.id == "normalization-overlap")
        recorded = next(
            recorded_case for recorded_case in predictions.cases if recorded_case.id == case.id
        )
        _, selected = unieval_settings()
        settings = UnievalSettings.model_validate_json(
            selected.model_copy(update={"scoring": case.controls}).model_dump_json()
        )
        async with running_unieval(settings=settings) as (client, worker, _):
            response = await client.post(UNIEVAL_PATH, json=case.request.model_dump())
            result = UnievalResult.model_validate_json(response.content)
            assert response.status_code == 400 and result.status == "partial"
            assert result.scores.consistency is None
            assert result.scores.coherence is None
            for dimension in ("fluency", "relevance"):
                expected = next(
                    item.score for item in recorded.comparisons if item.dimension == dimension
                )
                assert getattr(result.scores, dimension) == expected
            assert any(
                error.code == "CONSISTENCY_INPUT_TOO_LONG" and error.dimension == "consistency"
                for error in result.errors
            )
            assert all(error.code != "WORKER_EXITED" for error in result.errors)
            assert (await client.get("/health")).status_code == 200
            assert worker.is_alive

    asyncio.run(check())


@pytest.mark.parametrize("scenario", [UnievalScenario(invalid_at=4), UnievalScenario(fail_at=4)])
def test_failed_matrix_cell_keeps_completed_dimensions_but_has_no_consistency(
    scenario: UnievalScenario,
) -> None:
    async def check() -> None:
        inputs, _, _ = read_unieval_recordings()
        async with running_unieval(scenario=scenario) as (client, _, _):
            response = await client.post(UNIEVAL_PATH, json=inputs.cases[0].request.model_dump())
            result = UnievalResult.model_validate_json(response.content)
            assert response.status_code == 500 and result.status == "partial"
            assert result.scores.consistency is None
            assert result.scores.fluency is not None
            assert result.scores.coherence is not None
            assert result.scores.relevance is not None
            assert result.work.consistency.planned is not None
            assert result.work.consistency.completed < result.work.consistency.planned
            assert result.errors[0].dimension == "consistency"
            assert "PrivateModelFailureCanary" not in response.text

    asyncio.run(check())
