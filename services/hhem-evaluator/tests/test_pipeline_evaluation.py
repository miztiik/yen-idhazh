"""Compose the real API, recorded model boundary and shared native host collector."""

import asyncio
from pathlib import Path

import pytest
from summary_eval_pipeline.contracts import ServiceShutdown
from summary_eval_pipeline.evaluation import evaluate, read_owned_health
from summary_eval_pipeline.failures import WorkflowFailure
from summary_eval_pipeline.host_reader import measurement_complete
from summary_eval_pipeline.http import call_local_api
from summary_eval_pipeline.run import build_evidence
from summary_eval_pipeline.settings import load_pipeline_settings

from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.service_health import ServiceHealth

from .contract_examples import CORRELATION_ID, REPOSITORY, REQUEST_ID
from .pipeline_cases import NativeHostPipe, prepare_proc
from .replay_predictions import Scenario, read_recordings
from .service_cases import running_service


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
        errors = []
        try:
            async with running_service() as service:
                controller = service.app.state.controller
                await read_owned_health(
                    service.client,
                    "http://127.0.0.1:3010",
                    controller.instance_id,
                    controller.settings,
                    pipeline,
                )
                if partial:
                    service.log.fail_terminal = True
                status, result = await evaluate(
                    service.client,
                    "http://127.0.0.1:3010",
                    request,
                    controller.settings,
                    pipeline,
                )
                if status != 200:
                    errors.append(
                        WorkflowFailure(
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
                prepare_proc(tmp_path, closing=True)
                clean, machine = host.close()
                assert clean and measurement_complete(machine)
            assert service.worker.exit_confirmed
            evidence = build_evidence(
                result,
                host.hardware,
                machine,
                ServiceShutdown(
                    hhem_stopped=True,
                    host_stopped=clean,
                    worker_exit_confirmed=service.worker.exit_confirmed,
                ),
                errors,
            )
            assert evidence.status == ("partial" if partial else "complete")
            assert status == (500 if partial else 200)
            assert case.source_text not in evidence.model_dump_json()
            assert case.summary_text not in evidence.model_dump_json()
            if partial:
                assert evidence.errors[0].http_status == 500
        finally:
            host.close()
            assert host.process.poll() is not None

    asyncio.run(check())


def test_bad_identity_is_rejected_against_real_health() -> None:
    async def check() -> None:
        async with running_service() as service:
            with pytest.raises(WorkflowFailure) as failure:
                await read_owned_health(
                    service.client,
                    "http://127.0.0.1:3010",
                    REQUEST_ID,
                    service.app.state.controller.settings,
                    load_pipeline_settings(REPOSITORY),
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
                    "http://127.0.0.1:3010",
                    controller.instance_id,
                    controller.settings,
                    load_pipeline_settings(REPOSITORY),
                )
            )
            await asyncio.sleep(0)
            assert not waiting.done()
            await service.worker.release_prediction()
            health = await waiting
            assert health.status == "ready" and health.worker == service.worker.worker
            assert not any(event.operation == "primary" for event in service.log.events)

    asyncio.run(check())


def test_actual_health_response_enforces_the_exact_byte_allowance() -> None:
    async def check() -> None:
        async with running_service() as service:
            url = "http://127.0.0.1:3010/api/2026-11-02/health"
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
                    with pytest.raises(WorkflowFailure) as failure:
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
