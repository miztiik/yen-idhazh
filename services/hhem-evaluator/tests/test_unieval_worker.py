"""Verify native-call timeout kills and joins only the owned UniEval worker."""

import asyncio

from hhem_evaluator.contracts.unieval_result import UnievalResult
from hhem_evaluator.shared.contracts.api_paths import API_HEALTH_PATH
from hhem_evaluator.unieval_router import UNIEVAL_PATH

from .unieval_cases import (
    UnievalScenario,
    read_unieval_recordings,
    running_unieval,
    unieval_settings,
)


def test_timed_out_matrix_preserves_three_scores_and_confirms_actual_worker_exit() -> None:
    async def check() -> None:
        _, selected = unieval_settings()
        settings = selected.model_copy(
            update={"evaluation": selected.evaluation.model_copy(update={"timeout_ms": 1000})}
        )
        inputs, _, _ = read_unieval_recordings()
        async with running_unieval(settings=settings, scenario=UnievalScenario(block_at=4)) as (
            client,
            worker,
            _,
        ):
            response = await client.post(UNIEVAL_PATH, json=inputs.cases[0].request.model_dump())
            result = UnievalResult.model_validate_json(response.content)
            assert response.status_code == 504
            assert result.status == "partial" and result.scores.consistency is None
            assert result.scores.fluency is not None
            assert result.scores.coherence is not None
            assert result.scores.relevance is not None
            assert result.errors[0].code == "EVALUATION_TIMEOUT"
            assert worker.exit_confirmed and worker.last_exit is not None
            assert (await client.get(API_HEALTH_PATH)).status_code == 503

    asyncio.run(check())
