"""Does the real coverage API enforce safe complete results and owned bounded failure cleanup?"""

import asyncio
import io
import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_cases import (
    CoverageScenario,
    RecordedCoverageSupervisor,
    running_coverage,
)
from summary_evaluator_cases.coverage_recordings import coverage_settings, read_coverage_recordings
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import (
    DirectRequest,
    RecordedSupervisor,
    service_settings,
)

from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import (
    API_HEALTH_PATH,
    COVERAGE_EVALUATE_PATH,
    COVERAGE_HEALTH_PATH,
    EVALUATE_PATH,
    HHEM_HEALTH_PATH,
)
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageResult


async def until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0)


def body() -> dict[str, str]:
    inputs, _ = read_coverage_recordings()
    return {
        "source_text": inputs.cases[0].source_text,
        "summary_text": inputs.cases[0].summary_text,
    }


def test_actual_route_retains_genuine_metrics_and_has_no_legacy_alias_or_machine_fields() -> None:
    async def check() -> None:
        _, recording = read_coverage_recordings()
        async with running_coverage() as (client, worker, _, _):
            health = await client.get(COVERAGE_HEALTH_PATH)
            shared = await client.get(API_HEALTH_PATH)
            assert health.status_code == shared.status_code == 200
            assert worker.worker is not None
            assert health.json()["worker"]["pid"] == worker.worker.pid
            assert shared.json()["enabled_routes"] == ["coverage"]
            assert (
                shared.json()["hhem"]["status"]
                == shared.json()["unieval"]["status"]
                == "disabled"
            )
            response = await client.post(COVERAGE_EVALUATE_PATH, json=body())
            result = CoverageResult.model_validate_json(response.content)
            assert response.status_code == 200
            assert result.metrics.model_dump(mode="json") == recording.cases[0].expected_metrics
            assert set(response.json()) == {"status", "metrics"}
            assert "memory" not in health.json() and "serverTelemetry" not in response.json()
            for path in ("/v1/evaluate", "/health", f"{COVERAGE_EVALUATE_PATH}/"):
                assert (await client.post(path, json=body())).status_code == 404

    asyncio.run(check())


def test_disabled_coverage_constructs_no_worker_or_reads_its_named_resources(
    tmp_path: Path,
) -> None:
    api = load_api_settings(REPOSITORY / "config" / "summary-evals" / "api.json")
    api = api.model_copy(update={"enabled_routes": ()})
    app = create_app(api, None, tmp_path, writer=EventWriter(api.logging, io.StringIO()))
    assert app.state.coverage is None
    assert COVERAGE_EVALUATE_PATH not in app.openapi()["paths"]


@pytest.mark.parametrize(
    ("kind", "headers", "code", "status"),
    [
        (b"not-json", {}, "INVALID_JSON", 400),
        (b'{"sourceText":"PrivateTextCanary","summaryText":"Summary"}', {}, "INVALID_REQUEST", 400),
        (b"{}", {"Origin": "https://example.invalid"}, "ORIGIN_FORBIDDEN", 403),
        (b"{}", {"Content-Type": "text/plain"}, "UNSUPPORTED_MEDIA", 415),
    ],
)
def test_request_refusals_keep_the_shared_safe_body(
    kind: bytes, headers: dict[str, str], code: str, status: int
) -> None:
    async def check() -> None:
        async with running_coverage() as (client, _, logs, _):
            response = await client.post(
                COVERAGE_EVALUATE_PATH,
                content=kind,
                headers={"Content-Type": "application/json", **headers},
            )
            assert response.status_code == status
            assert response.json()["error"]["code"] == code
            assert response.json()["error"]["type"] == "api_error"
            assert "PrivateTextCanary" not in response.text + logs.getvalue()
            assert set(response.json()) == {"error"}

    asyncio.run(check())


@pytest.mark.parametrize("kind", ["missing_batch", "missing_dimension", "nonfinite", "extra_batch"])
def test_invalid_model_work_is_a_safe_500_without_partial_metrics(kind: str) -> None:
    async def check() -> None:
        async with running_coverage(
            scenario=CoverageScenario(invalid_dimension="consistency", invalid_kind=kind)
        ) as (client, worker, logs, _):
            response = await client.post(COVERAGE_EVALUATE_PATH, json=body())
            assert response.status_code == 500
            assert response.json() == {
                "error": {
                    "code": "INVALID_MODEL_OUTPUT",
                    "type": "api_error",
                    "message": ERROR_POLICIES["INVALID_MODEL_OUTPUT"].message,
                }
            }
            assert worker.exit_confirmed
            assert (await client.get(COVERAGE_HEALTH_PATH)).status_code == 503
            assert "Traceback" not in logs.getvalue()

    asyncio.run(check())


def test_not_ready_refuses_input_before_reading_it_and_stops_the_loading_child() -> None:
    async def check() -> None:
        async with running_coverage(
            scenario=CoverageScenario(block_loading=True), wait_ready=False
        ) as (client, worker, _, app):
            assert await worker.handshake() == {"phase": "loading"}
            assert (await client.get(COVERAGE_HEALTH_PATH)).status_code == 503
            request = DirectRequest(b"PrivateUnreadInput", path=COVERAGE_EVALUATE_PATH)
            await request.run(app)
            assert request.body_reads == 0 and request.messages[0]["status"] == 503

    asyncio.run(check())


def test_configured_input_byte_limit_is_exact() -> None:
    async def check() -> None:
        encoded = json.dumps(body(), separators=(",", ":")).encode()
        selected = coverage_settings()
        selected = selected.model_copy(
            update={
                "listener": selected.listener.model_copy(update={"max_body_bytes": len(encoded)})
            }
        )
        async with running_coverage(settings=selected) as (client, _, _, _):
            accepted = await client.post(
                COVERAGE_EVALUATE_PATH,
                content=encoded,
                headers={"Content-Type": "application/json"},
            )
            assert accepted.status_code == 200
            refused = await client.post(
                COVERAGE_EVALUATE_PATH,
                content=encoded + b" ",
                headers={"Content-Type": "application/json"},
            )
            assert refused.status_code == 413
            assert refused.json()["error"]["code"] == "BODY_TOO_LARGE"

    asyncio.run(check())


def test_queue_full_and_expiry_do_not_cancel_the_active_coverage_worker() -> None:
    async def check() -> None:
        selected = coverage_settings()
        selected = selected.model_copy(
            update={
                "queue": selected.queue.model_copy(update={"capacity": 1, "wait_timeout_ms": 250})
            }
        )
        async with running_coverage(
            settings=selected, scenario=CoverageScenario(hold_dimension="consistency")
        ) as (client, worker, _, app):
            active = asyncio.create_task(client.post(COVERAGE_EVALUATE_PATH, json=body()))
            assert (await worker.handshake())["phase"] == "loading"
            for dimension in ("fluency", "coherence", "consistency"):
                assert (await worker.handshake())["dimension"] == dimension
            original = worker.worker
            queued = asyncio.create_task(client.post(COVERAGE_EVALUATE_PATH, json=body()))
            await until(lambda: app.state.coverage.queue.depth == 1)
            overflow = DirectRequest(b"UnreadOverflow", path=COVERAGE_EVALUATE_PATH)
            await overflow.run(app)
            assert overflow.body_reads == 0 and overflow.messages[0]["status"] == 429
            expired = await queued
            assert expired.status_code == 503 and expired.json()["error"]["code"] == "QUEUE_TIMEOUT"
            assert expired.headers["Retry-After"] == str(selected.queue.retry_after_seconds)
            assert worker.worker == original and not worker.exit_confirmed
            await worker.release()
            assert (await active).status_code == 200

    asyncio.run(check())


def test_timeout_keeps_504_and_stops_the_exact_blocked_worker() -> None:
    async def check() -> None:
        selected = coverage_settings()
        selected = selected.model_copy(
            update={"evaluation": selected.evaluation.model_copy(update={"timeout_ms": 500})}
        )
        async with running_coverage(
            settings=selected, scenario=CoverageScenario(block_dimension="consistency")
        ) as (client, worker, _, _):
            assert worker.worker is not None
            pid = worker.worker.pid
            response = await client.post(COVERAGE_EVALUATE_PATH, json=body())
            assert response.status_code == 504
            assert response.json()["error"]["code"] == "EVALUATION_TIMEOUT"
            assert worker.exit_confirmed and worker.last_exit is not None
            assert worker.last_exit[0] == pid

    asyncio.run(check())


def test_active_disconnect_delivers_no_response_and_confirms_owned_exit() -> None:
    async def check() -> None:
        async with running_coverage(
            scenario=CoverageScenario(block_dimension="consistency")
        ) as (_, worker, _, app):
            request = DirectRequest(json.dumps(body()).encode(), path=COVERAGE_EVALUATE_PATH)
            active = asyncio.create_task(request.run(app))
            assert (await worker.handshake())["phase"] == "loading"
            for dimension in ("fluency", "coherence", "consistency"):
                assert (await worker.handshake())["dimension"] == dimension
            request.disconnected.set()
            await active
            assert request.messages == []
            assert worker.exit_confirmed

    asyncio.run(check())


def test_failed_coverage_neither_borrows_nor_stops_completed_hhem_work() -> None:
    async def check() -> None:
        api = load_api_settings(REPOSITORY / "config" / "summary-evals" / "api.json")
        api = api.model_copy(update={"enabled_routes": ("hhem", "coverage")})
        hhem = service_settings()
        hhem_worker = RecordedSupervisor(hhem, (Scenario(),))
        coverage = coverage_settings()
        worker = RecordedCoverageSupervisor(coverage, CoverageScenario(crash_dimension="fluency"))
        app = create_app(
            api, hhem, REPOSITORY, writer=EventWriter(api.logging, io.StringIO()),
            supervisor=hhem_worker, coverage_settings=coverage, coverage_supervisor=worker,
        )
        try:
            async with app.router.lifespan_context(app):
                await app.state.controller.loading_task
                await app.state.coverage.loading_task
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app),
                    base_url=f"http://{api.listener.host}:{api.listener.port}",
                    trust_env=False,
                ) as client:
                    inputs, predictions, _ = read_recordings(REPOSITORY)
                    native_body = {
                        "source_text": inputs.cases[0].source_text,
                        "summary_text": inputs.cases[0].summary_text,
                    }
                    completed = await client.post(EVALUATE_PATH, json=native_body)
                    result = EvaluationResult.model_validate_json(completed.content)
                    assert result.hhem == predictions.cases[0].score
                    failed = await client.post(COVERAGE_EVALUATE_PATH, json=body())
                    assert failed.status_code == 500 and set(failed.json()) == {"error"}
                    assert (await client.get(HHEM_HEALTH_PATH)).status_code == 200
                    assert (await client.get(API_HEALTH_PATH)).status_code == 503
                    retained = await client.post(EVALUATE_PATH, json=native_body)
                    assert retained.status_code == 200 and retained.json()["hhem"] == result.hhem
        finally:
            hhem_worker.close_controls()
            worker.close_controls()
        assert hhem_worker.exit_confirmed and worker.exit_confirmed

    asyncio.run(check())
