"""Prove native HTTP contracts and responsive health through the real ASGI lifespan."""

import asyncio
import io
import json
from pathlib import Path

import pytest
from summary_evaluator_cases.contract_examples import API_SETTINGS_FILE, REPOSITORY, SETTINGS_FILE
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import (
    DirectRequest,
    EventLog,
    running_service,
    service_settings,
)
from summary_evaluator_cases.unieval_cases import (
    RecordedUnievalSupervisor,
    read_unieval_recordings,
    unieval_settings,
)

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_event import EventDetails
from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.emit_events import EventEmitter
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.error_detail import ApiErrorResult
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_hhem_settings as load_settings
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import (
    API_HEALTH_PATH,
    API_PREFIX,
    API_SCHEMA_PATH,
    EVALUATE_PATH,
    HHEM_HEALTH_PATH,
)
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.unieval_router import UNIEVAL_HEALTH_PATH, UNIEVAL_PATH


def test_event_overflow_is_refused_before_any_truncated_record_is_written() -> None:
    settings = service_settings(logging={"max_event_bytes": 64})
    log = EventLog()
    emitter = EventEmitter(
        EventWriter(settings.logging, log).write, StartupContext(), settings.logging
    )
    with pytest.raises(EvaluationFailure) as failure:
        emitter.emit("request", "started", EventDetails())
    assert failure.value.error.code == "LOGGING_FAILED"
    assert emitter.logging_failed and emitter.last_event_id is None
    assert log.getvalue() == ""


def test_disabled_service_and_native_openapi_do_not_start_or_read_input() -> None:
    async def check() -> None:
        settings = load_settings(SETTINGS_FILE)
        async with running_service(settings, routes=(), wait_ready=False) as service:
            response = await service.client.get(API_HEALTH_PATH)
            assert response.status_code == 503
            assert response.json()["status"] == "disabled"
            assert response.json()["hhem"]["worker"] is None
            request = DirectRequest(b"PrivateUnreadBodyCanary")
            await request.run(service.app)
            assert request.body_reads == 0
            assert request.messages[0]["status"] == 404
            assert not service.worker.controls
            assert "llama" not in response.json()
            assert "coverage" not in response.json()
            schema = (await service.client.get(API_SCHEMA_PATH)).json()
            assert EVALUATE_PATH not in schema["paths"]
            assert "/v1/chat/completions" not in schema["paths"]
            assert (await service.client.get(f"{HHEM_HEALTH_PATH}/")).status_code == 404
            assert (await service.client.get("/docs")).status_code == 404

    asyncio.run(check())


def test_loading_health_is_responsive_and_no_body_is_admitted() -> None:
    async def check() -> None:
        async with running_service(
            scenarios=(Scenario(hold_loading=True),), wait_ready=False
        ) as service:
            assert (await service.worker.handshake())["phase"] == "loading"
            response = await service.client.get(HHEM_HEALTH_PATH)
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
            assert (await service.client.get(HHEM_HEALTH_PATH)).status_code == 200

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
            schema = (await service.client.get(API_SCHEMA_PATH)).json()
            body = schema["paths"][EVALUATE_PATH]["post"]["requestBody"]
            assert (
                body["content"]["application/json"]["schema"] == EvaluateRequest.model_json_schema()
            )
            assert (
                await service.client.post(f"{API_PREFIX}/evaluate", json=base)
            ).status_code == 404
            for changes in (
                {"chunk_words": 100},
                {"chunk_overlap_words": 5000},
                {"hhem_full": True},
                {"chunk_words": "1500"},
                {"include_window_details": None},
                {"source_text": " \t\n"},
                {"UnexpectedPropertyCanary": "PrivateValueCanary"},
            ):
                response = await service.client.post(EVALUATE_PATH, json={**base, **changes})
                assert response.status_code == 400, response.text
                assert response.json()["errors"][0]["code"] == "INVALID_REQUEST"
                assert response.json()["hhem"] is None
            accepted = await service.client.post(
                EVALUATE_PATH,
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
            refused = await service.client.post(EVALUATE_PATH, json=base)
            assert refused.status_code == 400
            assert refused.json()["errors"][0]["field"] == "full_source_text"
            enabled = await service.client.post(
                EVALUATE_PATH,
                json={**base, "full_source_text": case.source_text},
            )
            assert enabled.status_code == 200, enabled.text
            assert enabled.json()["windows"]["full_reused_primary"]
            assert "window_details" in enabled.json()

    asyncio.run(check())


def test_both_recorded_scorers_work_without_generation_configuration_or_routes(
    tmp_path: Path,
) -> None:
    async def check() -> None:
        inputs, predictions, _ = read_recordings(REPOSITORY)
        unieval_inputs, _, _ = read_unieval_recordings()
        _, selected_unieval = unieval_settings(
            api=load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
        )
        unieval_worker = RecordedUnievalSupervisor(selected_unieval, None)
        async with running_service(
            routes=("hhem", "unieval"),
            root=tmp_path,
            unieval_settings=selected_unieval,
            unieval_supervisor=unieval_worker,
        ) as service:
            hhem = await service.client.post(
                EVALUATE_PATH,
                json={
                    "source_text": inputs.cases[0].source_text,
                    "summary_text": inputs.cases[0].summary_text,
                },
            )
            hhem_result = EvaluationResult.model_validate_json(hhem.content)
            assert hhem.status_code == 200 and hhem_result.hhem == predictions.cases[0].score
            unieval = await service.client.post(
                UNIEVAL_PATH, json=unieval_inputs.cases[0].request.model_dump()
            )
            unieval_result = UnievalResult.model_validate_json(unieval.content)
            assert unieval.status_code == 200 and unieval_result.status == "complete"
            health = await service.client.get(API_HEALTH_PATH)
            assert health.status_code == 200
            assert health.json()["enabled_routes"] == ["hhem", "unieval"]
            assert "llama" not in health.json()
            assert "coverage" not in health.json()
            assert not hasattr(service.app.state, "forwarder")
            schema = (await service.client.get(API_SCHEMA_PATH)).json()
            assert "/v1/chat/completions" not in schema["paths"]
            for path in (
                "/v1/chat/completions",
                "/health",
                "/api/2026-11-02/summary-eval-hhem",
                "/api/2026-11-02/health",
                "/api/2026-11-02/summary-eval-unieval",
                "/api/2026-11-02/summary-eval-unieval/health",
                "/api/2026-11-02/openapi.json",
                "/api/2026-11-05/evaluate-summary-coverage",
                "/api/2026-11-05/get-summary-coverage-health",
            ):
                request = DirectRequest(b"PrivateRetiredBodyCanary", path=path)
                await request.run(service.app)
                assert request.messages[0]["status"] == 404
                assert request.body_reads == 0
                assert (await service.client.get(path)).status_code == 404
        assert service.worker.exit_confirmed and unieval_worker.exit_confirmed

    asyncio.run(check())


@pytest.mark.parametrize(
    "path", [API_HEALTH_PATH, API_SCHEMA_PATH, HHEM_HEALTH_PATH, UNIEVAL_HEALTH_PATH, "/unknown"]
)
@pytest.mark.parametrize(
    ("headers", "code"),
    [
        (((b"origin", b"https://PrivateOriginCanary.invalid"),), "ORIGIN_FORBIDDEN"),
        (((b"host", b"PrivateHostCanary.invalid"),), "HOST_FORBIDDEN"),
    ],
)
def test_operational_and_unknown_routes_refuse_unsafe_authority_without_reading_or_echoing(
    path: str, headers: tuple[tuple[bytes, bytes], ...], code: ErrorCode
) -> None:
    async def check() -> None:
        api = load_scorer_api_settings(API_SETTINGS_FILE, "hhem").model_copy(
            update={"enabled_routes": ()}
        )
        stream = io.StringIO()
        app = create_app(api, None, REPOSITORY, writer=EventWriter(api.logging, stream))
        async with app.router.lifespan_context(app):
            request = DirectRequest(b"PrivateUnreadBodyCanary", path=path, headers=headers)
            await request.run(app)
            assert request.body_reads == 0 and request.messages[0]["status"] == 403
            response = ApiErrorResult.model_validate_json(request.messages[1]["body"])
            assert response.error.code == code
            safe = ErrorDetail.from_code(code, "request")
            assert response.error.message == safe.message and response.error.type == "api_error"
            assert "Private" not in request.messages[1]["body"].decode() + stream.getvalue()

    asyncio.run(check())


def test_excessive_full_plan_is_rejected_before_any_model_call() -> None:
    async def check() -> None:
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        settings = service_settings(scoring={"max_windows_per_comparison": 1})
        async with running_service(settings) as service:
            response = await service.client.post(
                EVALUATE_PATH,
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


def test_lifespan_preserves_the_original_error_when_cleanup_also_fails() -> None:
    async def check() -> None:
        api = load_scorer_api_settings(API_SETTINGS_FILE, "hhem")
        api = api.model_copy(update={"enabled_routes": ()})
        stream = io.StringIO()
        app = create_app(api, None, REPOSITORY, writer=EventWriter(api.logging, stream))
        original = ValueError("The operation failed before cleanup.")
        with pytest.raises(BaseExceptionGroup) as observed:
            async with app.router.lifespan_context(app):
                stream.close()
                raise original
        assert observed.value.exceptions[0] is original
        cleanup = observed.value.exceptions[1]
        assert isinstance(cleanup, RuntimeFailure)
        assert cleanup.code == "LOGGING_FAILED"

    asyncio.run(check())
