"""Prove the real shared application forwards one fixed native operation and owns cleanup."""

import asyncio
import json

import pytest

from hhem_evaluator.contracts.base import API_PREFIX, EVALUATE_PATH
from hhem_evaluator.contracts.llama_result import LlamaResult
from hhem_evaluator.forward_llama import LLAMA_COMPLETIONS_PATH

from .contract_examples import REPOSITORY
from .llama_cases import RecordedLlama, generation_body, llama_settings
from .replay_predictions import Scenario, read_recordings
from .service_cases import DirectRequest, running_service


def test_native_request_response_and_reasoning_are_preserved_without_loading_hhem() -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        async with running_service(
            routes=("llama",), llama_settings=llama_settings(), llama_transport=recorded.transport
        ) as service:
            response = await service.client.post(
                LLAMA_COMPLETIONS_PATH,
                content=generation_body(),
                headers={
                    "Content-Type": "application/json",
                    "X-Upstream-URL": "https://ignored.invalid",
                },
            )
            assert response.status_code == 200 and response.content == recorded.body
            result = LlamaResult.model_validate_json(response.content)
            assert result.choices[0].message.reasoning_content
            native_url, native_body, native_headers = recorded.requests[0]
            assert native_url == llama_settings().base_url + LLAMA_COMPLETIONS_PATH
            assert native_body == generation_body()
            assert "x-upstream-url" not in native_headers
            assert not service.worker.controls and service.worker.model is None
            assert (await service.client.post(EVALUATE_PATH)).status_code == 404
            health = await service.client.get("/health")
            assert health.status_code == 200
            assert health.json()["service_instance_id"] == service.app.state.service_instance_id
            assert health.json()["hhem"]["status"] == "disabled"
            assert health.json()["llama"]["status"] == "ready"
            forwarder = service.app.state.forwarder
            assert not forwarder.client.trust_env and not forwarder.client.follow_redirects
            assert "PrivateSourceCanary" not in service.log.getvalue()
            answer = result.choices[0].message.content
            assert answer is not None and answer not in service.log.getvalue()
        assert forwarder.client.is_closed and not forwarder.active

    asyncio.run(check())


@pytest.mark.parametrize("stream", [True, 1, None, "false"])
def test_streaming_and_nonboolean_controls_are_refused_before_native_dispatch(
    stream: object,
) -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        payload = json.loads(generation_body())
        payload["stream"] = stream
        async with running_service(
            routes=("llama",), llama_settings=llama_settings(), llama_transport=recorded.transport
        ) as service:
            response = await service.client.post(LLAMA_COMPLETIONS_PATH, json=payload)
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "INVALID_REQUEST"
            assert not recorded.requests
            assert "PrivateSourceCanary" not in response.text + service.log.getvalue()

    asyncio.run(check())


@pytest.mark.parametrize(
    ("native_status", "body", "expected_status", "code"),
    [
        (
            429,
            b'{"error":{"code":429,"type":"server_error","message":"PrivateNativeErrorCanary"}}',
            429,
            429,
        ),
        (503, b'{"error":{"code":503,"type":"unavailable_error","message":"Loading"}}', 503, 503),
        (302, b"PrivateRedirectBodyCanary", 502, "UPSTREAM_REDIRECT"),
        (200, b"PrivateInvalidJsonCanary", 502, "INVALID_UPSTREAM_RESPONSE"),
        (
            200,
            b'{"object":"chat.completion","model":"native","choices":[]}',
            502,
            "INVALID_UPSTREAM_RESPONSE",
        ),
    ],
)
def test_native_statuses_are_preserved_and_invalid_or_redirected_results_are_explicit(
    native_status: int, body: bytes, expected_status: int, code: str | int
) -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        recorded.status, recorded.body = native_status, body
        async with running_service(
            routes=("llama",), llama_settings=llama_settings(), llama_transport=recorded.transport
        ) as service:
            response = await service.client.post(
                LLAMA_COMPLETIONS_PATH,
                content=generation_body(),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == expected_status
            assert response.json()["error"]["code"] == code
            if native_status in (429, 503):
                assert response.content == body
            assert len(recorded.requests) == 1
            assert "location" not in response.headers
            assert "Private" not in service.log.getvalue()

    asyncio.run(check())


def test_native_loading_is_not_shared_readiness_and_cannot_erase_hhem_health() -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        recorded.health_status, recorded.health_body = 503, b'{"error":{"code":503}}'
        async with running_service(
            routes=("hhem", "llama"),
            llama_settings=llama_settings(),
            llama_transport=recorded.transport,
        ) as service:
            health = await service.client.get("/health")
            assert health.status_code == 503
            assert health.json()["status"] == "loading"
            assert health.json()["llama"]["status"] == "loading"
            assert health.json()["hhem"]["status"] == "ready"
            hhem = await service.client.get(f"{API_PREFIX}/health")
            assert hhem.status_code == 200
            recorded.health_status, recorded.health_body = 200, b'{"status":"ok"}'
            assert (await service.client.get("/health")).status_code == 200

    asyncio.run(check())


def test_waiting_native_generation_keeps_health_responsive_and_admission_finite() -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        recorded.hold_generation = True
        async with running_service(
            routes=("llama",), llama_settings=llama_settings(), llama_transport=recorded.transport
        ) as service:
            active = asyncio.create_task(
                service.client.post(
                    LLAMA_COMPLETIONS_PATH,
                    content=generation_body(),
                    headers={"Content-Type": "application/json"},
                )
            )
            await recorded.started.wait()
            assert (await service.client.get("/health")).status_code == 200
            waiting = DirectRequest(b"PrivateUnreadCapacityCanary", path=LLAMA_COMPLETIONS_PATH)
            await waiting.run(service.app)
            assert waiting.body_reads == 0 and waiting.messages[0]["status"] == 429
            assert len(recorded.requests) == 1
            recorded.release.set()
            assert (await active).status_code == 200

    asyncio.run(check())


def test_hhem_prediction_does_not_block_native_generation_or_shared_health() -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        inputs, _, _ = read_recordings(REPOSITORY)
        case = inputs.cases[0]
        async with running_service(
            scenarios=(Scenario(actions=("hold",)),),
            routes=("hhem", "llama"),
            llama_settings=llama_settings(),
            llama_transport=recorded.transport,
        ) as service:
            await service.worker.handshake()
            scoring = asyncio.create_task(
                service.client.post(
                    EVALUATE_PATH,
                    json={"source_text": case.source_text, "summary_text": case.summary_text},
                )
            )
            await service.worker.handshake()
            response = await service.client.post(
                LLAMA_COMPLETIONS_PATH,
                content=generation_body(),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert (await service.client.get("/health")).status_code == 200
            assert not scoring.done()
            await service.worker.release_prediction()
            assert (await scoring).status_code == 200

    asyncio.run(check())


def test_native_deadline_cancels_the_outstanding_operation_without_logging_its_body() -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        recorded.hold_generation = True
        async with running_service(
            routes=("llama",),
            llama_settings=llama_settings(200),
            llama_transport=recorded.transport,
        ) as service:
            response = await service.client.post(
                LLAMA_COMPLETIONS_PATH,
                content=generation_body(),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 504
            assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
            assert recorded.cancelled.is_set()
            assert not service.app.state.forwarder.active
            assert "PrivateSourceCanary" not in service.log.getvalue() + response.text

    asyncio.run(check())


@pytest.mark.parametrize("shutdown", [False, True])
def test_disconnect_and_application_shutdown_cancel_native_work_and_close_the_client(
    shutdown: bool,
) -> None:
    async def check() -> None:
        recorded = RecordedLlama()
        recorded.hold_generation = True
        async with running_service(
            routes=("llama",), llama_settings=llama_settings(), llama_transport=recorded.transport
        ) as service:
            request = DirectRequest(generation_body(), path=LLAMA_COMPLETIONS_PATH)
            active = asyncio.create_task(request.run(service.app))
            await recorded.started.wait()
            forwarder = service.app.state.forwarder
            if shutdown:
                await forwarder.close()
            else:
                request.disconnected.set()
            async with asyncio.timeout(5):
                await active
            assert recorded.cancelled.is_set() and not request.messages
            assert not forwarder.active
        assert forwarder.client.is_closed

    asyncio.run(check())
