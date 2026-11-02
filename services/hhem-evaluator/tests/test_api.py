"""Prove native HTTP contracts and responsive health through the real ASGI lifespan."""

import asyncio
import json

import pytest

from hhem_evaluator.contracts.base import API_PREFIX
from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.evaluation_event import EventDetails
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.service_settings import ServiceSettings, StartupContext
from hhem_evaluator.emit_events import EventEmitter, EventWriter
from hhem_evaluator.fail_evaluation import EvaluationFailure

from .contract_examples import REPOSITORY, SETTINGS_FILE
from .replay_predictions import Scenario, read_recordings
from .service_cases import DirectRequest, EventLog, running_service, service_settings


def test_event_overflow_is_refused_before_any_truncated_record_is_written() -> None:
    settings = service_settings(logging={"max_event_bytes": 64})
    log = EventLog()
    emitter = EventEmitter(EventWriter(settings.logging, log), StartupContext())
    with pytest.raises(EvaluationFailure) as failure:
        emitter.emit("request", "started", EventDetails())
    assert failure.value.error.code == "LOGGING_FAILED"
    assert emitter.logging_failed and emitter.last_event_id is None
    assert log.getvalue() == ""


def test_disabled_service_and_native_openapi_do_not_start_or_read_input() -> None:
    async def check() -> None:
        settings = ServiceSettings.model_validate_json(SETTINGS_FILE.read_bytes())
        async with running_service(settings, wait_ready=False) as service:
            response = await service.client.get(f"{API_PREFIX}/health")
            assert response.status_code == 503
            assert response.json()["status"] == "disabled"
            assert response.json()["worker"] is None
            request = DirectRequest(b"PrivateUnreadBodyCanary")
            await request.run(service.app)
            assert request.body_reads == 0
            assert request.messages[0]["status"] == 503
            assert not service.worker.controls
            schema = (await service.client.get(f"{API_PREFIX}/openapi.json")).json()
            body = schema["paths"][f"{API_PREFIX}/evaluate"]["post"]["requestBody"]
            declared = body["content"]["application/json"]["schema"]
            native = EvaluateRequest.model_json_schema()
            assert declared == native
            result_schema = schema["components"]["schemas"]["EvaluationResult"]
            assert result_schema["version"] == settings.version
            assert (await service.client.get(f"{API_PREFIX}/health/")).status_code == 404
            assert (await service.client.get("/docs")).status_code == 404

    asyncio.run(check())


def test_loading_health_is_responsive_and_no_body_is_admitted() -> None:
    async def check() -> None:
        async with running_service(
            scenarios=(Scenario(hold_loading=True),), wait_ready=False
        ) as service:
            assert (await service.worker.handshake())["phase"] == "loading"
            response = await service.client.get(f"{API_PREFIX}/health")
            assert response.status_code == 503
            assert response.json()["status"] == "loading"
            assert response.json()["worker"]["pid"] > 0
            assert response.json()["model"] is None
            request = DirectRequest(b"PrivateUnreadyBodyCanary")
            await request.run(service.app)
            assert request.body_reads == 0
            assert request.messages[0]["status"] == 503
            await service.worker.release_prediction()
            await service.app.state.controller.loading_task
            assert (await service.client.get(f"{API_PREFIX}/health")).status_code == 200

    asyncio.run(check())


def test_resolved_controls_are_native_and_invalid_requests_never_get_a_422() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        base: dict[str, object] = {
            "source_text": case.source_text,
            "summary_text": case.summary_text,
        }
        async with running_service() as service:
            for changes in (
                {"chunk_words": 100},
                {"chunk_overlap_words": 900},
                {"hhem_full": True},
                {"chunk_words": "1500"},
                {"include_window_details": None},
                {"source_text": " \t\n"},
                {"UnexpectedPropertyCanary": "PrivateValueCanary"},
            ):
                response = await service.client.post(
                    f"{API_PREFIX}/evaluate", json={**base, **changes}
                )
                assert response.status_code == 400, response.text
                assert response.json()["errors"][0]["code"] == "INVALID_REQUEST"
                assert response.json()["hhem"] is None
            accepted = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    **base,
                    "chunk_words": 1500,
                    "chunk_overlap_words": 900,
                },
            )
            assert accepted.status_code == 200, accepted.text
            result = EvaluationResult.model_validate_json(accepted.content)
            assert result.effective_settings is not None
            assert result.effective_settings.chunk_words == 1500
            assert result.effective_settings.chunk_overlap_words == 900
            assert not result.effective_settings.hhem_full
            assert not result.effective_settings.include_window_details
        settings = service_settings(response={"hhem_full": True, "include_window_details": True})
        async with running_service(settings) as service:
            refused = await service.client.post(f"{API_PREFIX}/evaluate", json=base)
            assert refused.status_code == 400
            assert refused.json()["errors"][0]["field"] == "full_source_text"
            enabled = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={**base, "full_source_text": case.source_text},
            )
            assert enabled.status_code == 200, enabled.text
            assert enabled.json()["windows"]["full_reused_primary"]
            assert "window_details" in enabled.json()

    asyncio.run(check())


def test_excessive_full_plan_is_rejected_before_any_model_call() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        settings = service_settings(scoring={"max_windows_per_comparison": 1})
        async with running_service(settings) as service:
            response = await service.client.post(
                f"{API_PREFIX}/evaluate",
                json={
                    "source_text": case.source_text,
                    "summary_text": case.summary_text,
                    "full_source_text": case.source_text + " another word",
                    "hhem_full": True,
                    "chunk_words": len(case.source_text.split()),
                    "chunk_overlap_words": 0,
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["errors"][0]["code"] == "WINDOW_LIMIT_EXCEEDED"
            assert response.json()["windows"]["primary"]["scored"] == 0
            assert not any(event.operation == "primary" for event in service.log.events)
            assert "another word" not in json.dumps(response.json())

    asyncio.run(check())
