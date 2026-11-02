"""Prove score reduction through actual ASGI, byte pipes and the recorded model boundary."""

import asyncio
import json

import pytest

from hhem_evaluator.contracts.base import API_PREFIX
from hhem_evaluator.contracts.evaluation_result import EvaluationResult

from .contract_examples import REPOSITORY
from .replay_predictions import Action, Scenario, read_recordings
from .service_cases import running_service


def test_maximum_full_delta_details_reuse_and_source_direction() -> None:
    async def check() -> None:
        inputs, predictions, _ = read_recordings(REPOSITORY)
        supported, contradicted, other, _, whitespace = inputs.cases
        scores = {reply.id: reply.score for reply in predictions.cases}
        async with running_service() as service:
            primary = supported.source_text + " " + other.source_text
            assert len(supported.source_text.split()) == len(other.source_text.split()) == 21
            body: dict[str, object] = {
                "source_text": primary,
                "summary_text": supported.summary_text,
                "full_source_text": other.source_text,
                "hhem_full": True,
                "include_window_details": True,
                "chunk_words": 21,
                "chunk_overlap_words": 0,
            }
            response = await service.client.post(f"{API_PREFIX}/evaluate", json=body)
            assert response.status_code == 200, response.text
            result = EvaluationResult.model_validate_json(response.content)
            assert result.hhem == max(scores["supported"], scores["other-source"])
            assert result.hhem_full == scores["other-source"]
            assert result.hhem_delta == result.hhem - result.hhem_full
            assert result.window_details is not None
            assert [window.score for window in result.window_details.primary] == [
                scores["supported"],
                scores["other-source"],
            ]
            assert result.windows.primary is not None and result.windows.primary.scored == 2
            assert result.windows.full is not None and result.windows.full.scored == 1
            # The opposite primary/full direction must preserve subtraction order.
            reverse = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    "source_text": other.source_text,
                    "summary_text": supported.summary_text,
                    "full_source_text": supported.source_text,
                    "hhem_full": True,
                },
            )
            assert reverse.status_code == 200, reverse.text
            reversed_result = EvaluationResult.model_validate_json(reverse.content)
            assert reversed_result.hhem_delta == scores["other-source"] - scores["supported"]
            assert result.hhem_delta >= 0
            assert reversed_result.hhem_delta < 0
            reuse = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    "source_text": primary,
                    "summary_text": supported.summary_text,
                    "full_source_text": primary,
                    "hhem_full": True,
                    "include_window_details": True,
                    "chunk_words": 21,
                    "chunk_overlap_words": 0,
                },
            )
            reused = EvaluationResult.model_validate_json(reuse.content)
            assert reuse.status_code == 200
            assert reused.windows.full_reused_primary
            assert reused.windows.full is not None and reused.windows.full.scored == 0
            assert reused.timings_ms.full_scoring is None
            assert reused.window_details is not None
            assert reused.window_details.full == reused.window_details.primary
            distinct = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    "source_text": supported.source_text,
                    "summary_text": supported.summary_text,
                    "full_source_text": whitespace.source_text,
                    "hhem_full": True,
                },
            )
            assert distinct.status_code == 200, distinct.text
            assert distinct.json()["windows"]["full_reused_primary"] is False
            assert distinct.json()["hhem_full"] == scores["whitespace-distinct"]
            optional = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    "source_text": contradicted.source_text,
                    "summary_text": contradicted.summary_text,
                    "full_source_text": "UnusedFullSourceCanary",
                },
            )
            assert optional.status_code == 200, optional.text
            assert optional.json()["hhem"] == scores["contradicted"]
            assert optional.json()["hhem_full"] is None
            assert optional.json()["windows"]["full"] is None
            assert "window_details" not in optional.json()

    asyncio.run(check())


@pytest.mark.parametrize("action", ["invalid", "raise", "crash"])
def test_failed_full_comparison_preserves_completed_primary(action: Action) -> None:
    async def check() -> None:
        inputs, predictions, identity = read_recordings(REPOSITORY)
        primary, _, full, *_ = inputs.cases
        async with running_service(
            scenarios=(Scenario(actions=("score", action)), Scenario())
        ) as service:
            old_pid = service.worker.worker.pid if service.worker.worker is not None else None
            response = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    "source_text": primary.source_text,
                    "summary_text": primary.summary_text,
                    "full_source_text": full.source_text,
                    "hhem_full": True,
                    "include_window_details": True,
                },
            )
            assert response.status_code == 500, response.text
            result = EvaluationResult.model_validate_json(response.content)
            await service.app.state.controller.loading_task
            assert result.status == "partial"
            assert result.hhem == predictions.cases[0].score
            assert result.hhem_full is None and result.hhem_delta is None
            assert result.windows.primary is not None and result.windows.primary.scored == 1
            assert result.windows.full is not None and result.windows.full.scored == 0
            assert result.model is not None
            assert result.model.loaded_revision == identity.loaded_revision
            assert result.model.reference == identity.reference
            assert result.worker is not None and result.worker.pid == old_pid
            assert service.worker.confirmed_before_spawn[0][0] == old_pid
            assert service.worker.worker is not None and service.worker.worker.generation == 2
            assert service.worker.model == result.model
            logged = service.log.getvalue()
            assert primary.source_text not in logged and primary.summary_text not in logged
            assert full.source_text not in logged
            assert json.loads(response.content)["terminal_event_id"] in logged

    asyncio.run(check())
