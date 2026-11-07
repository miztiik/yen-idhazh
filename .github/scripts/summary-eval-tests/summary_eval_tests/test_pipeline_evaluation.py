"""Compose the real API, recorded model boundary and shared native host collector."""

import asyncio
from pathlib import Path

import httpx
import pytest
from summary_eval_pipeline.contracts import PipelineError
from summary_eval_pipeline.evaluation import evaluate, read_owned_health
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.host_reader import measurement_complete
from summary_eval_pipeline.http import call_local_api
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_eval_pipeline.storage import read_result, write_result
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.contracts.service_health import ServiceHealth
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH, HHEM_HEALTH_PATH
from summary_evaluator_cases.contract_examples import CORRELATION_ID, REPOSITORY, REQUEST_ID
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import running_service

from summary_eval_tests.pipeline_cases import NativeHostPipe, prepare_proc


@pytest.mark.parametrize("partial", [False, True])
def test_actual_handlers_preserve_scores_including_error_http_results(
    tmp_path: Path,
    partial: bool,
) -> None:
    async def check() -> None:
        inputs, predictions, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        request = EvaluateRequest(
            source_text=case.source_text,
            summary_text=case.summary_text,
            hhem_full=False,
            request_id=REQUEST_ID,
            correlation_id=CORRELATION_ID,
        )
        prepare_proc(tmp_path)
        host = NativeHostPipe(tmp_path)
        pipeline = load_pipeline_settings(REPOSITORY)
        errors: list[PipelineError] = []
        try:
            async with running_service() as service:
                controller = service.app.state.controller
                evaluation_timeouts: list[object] = []

                async def observe_timeout(sent: httpx.Request) -> None:
                    if sent.url.path == EVALUATE_PATH:
                        evaluation_timeouts.append(sent.extensions["timeout"]["read"])

                service.client.event_hooks["request"].append(observe_timeout)
                await read_owned_health(
                    service.client,
                    str(service.client.base_url).rstrip("/"),
                    controller.instance_id,
                    controller.settings.worker,
                    pipeline,
                    "hhem",
                )
                if partial:
                    service.log.fail_terminal = True
                status, result = await evaluate(
                    service.client,
                    str(service.client.base_url).rstrip("/"),
                    request,
                    controller.settings,
                    pipeline,
                )
                assert evaluation_timeouts == [
                    (
                        controller.settings.queue.wait_timeout_ms
                        + controller.settings.evaluation.timeout_ms
                        + controller.settings.worker.shutdown_timeout_ms
                        + pipeline.http_connect_timeout_ms
                    )
                    / 1000
                ]
                if status != 200:
                    errors.append(
                        WorkflowError(
                            "EVALUATION_FAILED",
                            "evaluation",
                            "hhem",
                            status,
                        ).error
                    )
                assert result.hhem == predictions.cases[0].score and result.hhem_full is None
                assert result.effective_settings is not None
                assert result.effective_settings.hhem_full is False
                assert (
                    sum(
                        event.operation == "primary" and event.phase == "started"
                        for event in service.log.events
                    )
                    == 1
                )
                assert not any(event.operation == "full" for event in service.log.events)
                write_result(tmp_path / "hhem.json", result)
                prepare_proc(tmp_path, closing=True)
                clean, machine = host.close()
                assert clean and measurement_complete(machine)
            assert service.worker.exit_confirmed
            retained = read_result(
                tmp_path / "hhem.json", EvaluationResult, pipeline.max_response_bytes
            )
            assert retained == result
            assert status == (500 if partial else 200)
            assert case.source_text not in retained.model_dump_json()
            assert case.summary_text not in retained.model_dump_json()
            if partial:
                assert errors[0].http_status == 500
        finally:
            host.close()
            assert host.process.poll() is not None

    asyncio.run(check())


def test_bad_identity_is_rejected_against_real_health() -> None:
    async def check() -> None:
        async with running_service() as service:
            with pytest.raises(WorkflowError) as failure:
                await read_owned_health(
                    service.client,
                    str(service.client.base_url).rstrip("/"),
                    REQUEST_ID,
                    service.app.state.controller.settings.worker,
                    load_pipeline_settings(REPOSITORY),
                    "hhem",
                )
            assert failure.value.error.code == "STARTUP_IDENTITY_MISMATCH"
            assert not any(event.operation == "primary" for event in service.log.events)

    asyncio.run(check())


def test_health_waits_for_actual_model_readiness_without_sending_a_score_request() -> None:
    async def check() -> None:
        async with running_service(
            scenarios=(Scenario(hold_loading=True),),
            wait_ready=False,
        ) as service:
            assert (await service.worker.handshake())["phase"] == "loading"
            controller = service.app.state.controller
            assert controller.health().status == "loading"
            waiting = asyncio.create_task(
                read_owned_health(
                    service.client,
                    str(service.client.base_url).rstrip("/"),
                    controller.instance_id,
                    controller.settings.worker,
                    load_pipeline_settings(REPOSITORY),
                    "hhem",
                )
            )
            await asyncio.sleep(0)
            assert not waiting.done()
            await service.worker.release_prediction()
            health = await waiting
            assert isinstance(health.hhem, ServiceHealth)
            assert health.status == "ready" and health.hhem.worker == service.worker.worker
            assert not any(event.operation == "primary" for event in service.log.events)

    asyncio.run(check())


def test_actual_health_response_enforces_the_exact_byte_allowance() -> None:
    async def check() -> None:
        async with running_service() as service:
            url = str(service.client.base_url).rstrip("/") + HHEM_HEALTH_PATH
            size = len((await service.client.get(url)).content)
            pipeline = load_pipeline_settings(REPOSITORY)
            for allowance, allowed in ((size, True), (size - 1, False)):
                selected = pipeline.model_copy(update={"max_response_bytes": allowance})
                if allowed:
                    status, health = await call_local_api(
                        service.client,
                        "GET",
                        url,
                        ServiceHealth,
                        selected,
                        5000,
                        service="hhem",
                        phase="health",
                    )
                    assert status == 200 and health.worker == service.worker.worker
                else:
                    with pytest.raises(WorkflowError) as failure:
                        await call_local_api(
                            service.client,
                            "GET",
                            url,
                            ServiceHealth,
                            selected,
                            5000,
                            service="hhem",
                            phase="health",
                        )
                    assert failure.value.error.code == "RESPONSE_TOO_LARGE"

    asyncio.run(check())
