"""Verify UniEval route admission, literal input privacy and component readiness."""

import asyncio
import hashlib
import io
from collections.abc import AsyncIterator

import httpx
import pytest

from hhem_evaluator.contracts.api_settings import ApiSettings
from hhem_evaluator.contracts.base import API_PREFIX, EVALUATE_PATH
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.unieval_result import UnievalResult
from hhem_evaluator.emit_events import EventWriter
from hhem_evaluator.serve_api import create_app
from hhem_evaluator.unieval_router import UNIEVAL_HEALTH_PATH, UNIEVAL_PATH

from .contract_examples import REPOSITORY
from .replay_predictions import Scenario, read_recordings
from .service_cases import RecordedSupervisor, service_settings
from .unieval_cases import (
    RecordedUnievalSupervisor,
    UnievalScenario,
    read_unieval_recordings,
    running_unieval,
    unieval_settings,
)


def test_real_component_health_and_reference_identity_are_bound_to_actual_work() -> None:
    async def check() -> None:
        inputs, _, identity = read_unieval_recordings()
        async with running_unieval() as (client, worker, _):
            health = await client.get(UNIEVAL_HEALTH_PATH)
            shared = await client.get("/health")
            assert health.status_code == shared.status_code == 200
            assert worker.worker is not None
            assert shared.json()["unieval"]["worker"]["pid"] == worker.worker.pid
            assert shared.json()["hhem"]["status"] == "disabled"
            assert (await client.get("/api/2026-11-02/health")).status_code == 404
            response = await client.post(UNIEVAL_PATH, json=inputs.cases[1].request.model_dump())
            result = UnievalResult.model_validate_json(response.content)
            assert result.model == identity
            assert (
                result.reference_summary_sha256
                == hashlib.sha256(
                    inputs.cases[1].request.reference_summary_text.encode("utf-8")
                ).hexdigest()
            )

    asyncio.run(check())


@pytest.mark.parametrize("idle_exit", [False, True])
def test_unieval_worker_failure_does_not_close_or_block_the_hhem_component(
    idle_exit: bool,
) -> None:
    async def check() -> None:
        selected_api, selected_unieval = unieval_settings()
        api = ApiSettings.model_validate_json(
            selected_api.model_copy(
                update={"enabled_routes": ("hhem", "unieval")}
            ).model_dump_json()
        )
        hhem = service_settings()
        hhem_worker = RecordedSupervisor(hhem, (Scenario(),))
        unieval_worker = RecordedUnievalSupervisor(
            selected_unieval, None if idle_exit else UnievalScenario(crash_at=0)
        )
        writer = EventWriter(api.logging, io.StringIO())
        app = create_app(
            api,
            hhem,
            REPOSITORY,
            writer=writer,
            supervisor=hhem_worker,
            unieval_settings=selected_unieval,
            unieval_supervisor=unieval_worker,
        )
        try:
            async with app.router.lifespan_context(app):
                await app.state.controller.loading_task
                await app.state.unieval.loading_task
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app),
                    base_url="http://127.0.0.1:3010",
                    trust_env=False,
                ) as client:
                    if idle_exit:
                        assert unieval_worker.process is not None
                        assert unieval_worker.lifetime is not None
                        process = unieval_worker.process
                        unieval_worker.lifetime.close()
                        await asyncio.to_thread(
                            process.join, selected_unieval.worker.stop_grace_ms / 1000
                        )
                        assert not process.is_alive() and process.exitcode == 0
                        response = await client.get(UNIEVAL_HEALTH_PATH)
                        assert response.status_code == 503
                        assert response.json()["failure_code"] == "WORKER_EXITED"
                    else:
                        inputs, _, _ = read_unieval_recordings()
                        response = await client.post(
                            UNIEVAL_PATH, json=inputs.cases[0].request.model_dump()
                        )
                        assert response.status_code == 500
                    assert unieval_worker.exit_confirmed
                    assert (await client.get("/health")).status_code == 503
                    assert (await client.get(f"{API_PREFIX}/health")).status_code == 200
                    hhem_inputs, predictions, _ = read_recordings(REPOSITORY)
                    response = await client.post(
                        EVALUATE_PATH,
                        json={
                            "source_text": hhem_inputs.cases[0].source_text,
                            "summary_text": hhem_inputs.cases[0].summary_text,
                        },
                    )
                    result = EvaluationResult.model_validate_json(response.content)
                    assert response.status_code == 200
                    assert result.hhem == predictions.cases[0].score
        finally:
            hhem_worker.close_controls()
        assert hhem_worker.exit_confirmed and unieval_worker.exit_confirmed

    asyncio.run(check())


def test_idle_exit_refuses_admission_before_reading_input_and_joins_the_child() -> None:
    async def check() -> None:
        async with running_unieval() as (client, worker, _):
            assert worker.process is not None and worker.lifetime is not None
            process = worker.process
            pid = process.pid
            worker.lifetime.close()
            await asyncio.to_thread(process.join, worker.settings.worker.stop_grace_ms / 1000)
            assert not process.is_alive() and process.exitcode == 0
            consumed = False

            async def body() -> AsyncIterator[bytes]:
                nonlocal consumed
                consumed = True
                yield b"{}"

            response = await client.post(
                UNIEVAL_PATH,
                content=body(),
                headers={"Content-Type": "application/json"},
            )
            result = UnievalResult.model_validate_json(response.content)
            assert response.status_code == 500 and result.status == "failed"
            assert result.errors[0].code == "WORKER_EXITED"
            assert not consumed
            assert worker.exit_confirmed and worker.last_exit == (pid, 0)
            assert (await client.get("/health")).status_code == 503

    asyncio.run(check())


@pytest.mark.parametrize(
    ("body", "headers", "status"),
    [
        (b'{"source_text":"Source","summary_text":"Answer"}', {}, 400),
        (b'{"PrivateUnknownCanary": "PrivateValueCanary"}', {}, 400),
        (b"not-json", {}, 400),
        (b"{}", {"Origin": "https://example.test"}, 403),
        (b"{}", {"Content-Type": "text/plain"}, 415),
    ],
)
def test_invalid_inputs_never_echo_text_or_invent_scores(
    body: bytes,
    headers: dict[str, str],
    status: int,
) -> None:
    async def check() -> None:
        async with running_unieval() as (client, _, log):
            response = await client.post(
                UNIEVAL_PATH,
                content=body,
                headers={"Content-Type": "application/json", **headers},
            )
            result = UnievalResult.model_validate_json(response.content)
            assert response.status_code == status and result.status == "failed"
            assert result.reference_summary_sha256 is None
            assert all(value is None for value in result.scores.model_dump().values())
            assert "PrivateUnknownCanary" not in response.text + log.getvalue()
            assert "PrivateValueCanary" not in response.text + log.getvalue()

    asyncio.run(check())
