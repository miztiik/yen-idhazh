"""Verify that one registration integrates native startup, health, refusal and cleanup."""

import asyncio
import io
from pathlib import Path
from typing import get_args

import httpx
import pytest
from summary_evaluator_cases.contract_examples import API_SETTINGS_FILE, REPOSITORY
from summary_evaluator_cases.coverage_cases import RecordedCoverageSupervisor
from summary_evaluator_cases.coverage_recordings import coverage_settings
from summary_evaluator_cases.replay_predictions import Scenario
from summary_evaluator_cases.service_cases import EventLog, RecordedSupervisor, service_settings
from summary_evaluator_cases.unieval_cases import RecordedUnievalSupervisor, unieval_settings

from summary_evaluator.hhem.contracts.evaluation_result import EvaluationResult
from summary_evaluator.hhem.create_api_component import (
    create_api_component as create_hhem_component,
)
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.compose_api import ComponentRegistration, compose_app
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.serve_http.contracts.error_detail import ApiErrorResult
from summary_evaluator.serve_http.contracts.server_event import (
    ApiDiagnosticData,
    DiagnosticComponent,
)
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import (
    API_HEALTH_PATH,
    COVERAGE_EVALUATE_PATH,
    COVERAGE_HEALTH_PATH,
    EVALUATE_PATH,
    HHEM_HEALTH_PATH,
)
from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.unieval_router import UNIEVAL_HEALTH_PATH, UNIEVAL_PATH


def test_registration_requires_the_complete_distinct_declared_vocabulary(tmp_path: Path) -> None:
    api = load_api_settings(API_SETTINGS_FILE).model_copy(update={"enabled_routes": ()})
    registration = ComponentRegistration(
        "hhem",
        "controller",
        lambda host, events: create_hhem_component(host, None, writer=events.write),
    )
    for registrations in ((), (registration, registration)):
        with pytest.raises(ValueError, match="must match the declared component vocabulary"):
            compose_app(
                api,
                tmp_path,
                registrations=registrations,
                writer=EventWriter(api.logging, io.StringIO()),
            )


@pytest.mark.parametrize("component", ["unieval", "coverage"])
def test_component_diagnostics_retain_the_native_envelope(component: DiagnosticComponent) -> None:
    api = load_api_settings(API_SETTINGS_FILE)
    log = EventLog()
    writer = EventWriter(api.logging, log)
    data = LifecycleFields(action="failed", level="ERROR", code="WORKER_EXITED")
    writer.component_diagnostic(component, data)
    envelope = log.envelopes[0]
    assert isinstance(envelope.data, ApiDiagnosticData)
    assert envelope.data.component == component
    assert envelope.data.model_dump(exclude={"component"}) == data.model_dump()
    assert envelope.type == f"fastapi-server.{component}.failed"


@pytest.mark.parametrize("component", ["hhem", "unieval", "coverage"])
@pytest.mark.parametrize("mismatch", ["listener", "shutdown"])
def test_each_adapter_validates_shared_bounds_and_closes_construction_logs(
    component: ApiComponent,
    mismatch: str,
    tmp_path: Path,
) -> None:
    api = load_api_settings(API_SETTINGS_FILE).model_copy(update={"enabled_routes": (component,)})
    hhem = service_settings()
    _, unieval = unieval_settings()
    coverage = coverage_settings()
    shutdown_wait = {
        "hhem": hhem.worker.shutdown_timeout_ms,
        "unieval": unieval.worker.shutdown_timeout_ms,
        "coverage": coverage.worker.shutdown_timeout_ms,
    }[component]
    if mismatch == "listener":
        api = api.model_copy(
            update={
                "listener": api.listener.model_copy(
                    update={"max_body_bytes": api.listener.max_body_bytes + 1}
                )
            }
        )
    else:
        api = api.model_copy(update={"shutdown_timeout_ms": shutdown_wait - 1})
    events = EventWriter(api.logging, io.StringIO(), directory=tmp_path / "logs")
    with pytest.raises(ValueError, match="shared|shutdown"):
        create_app(
            api,
            hhem,
            tmp_path,
            writer=events,
            unieval_settings=unieval,
            coverage_settings=coverage,
        )
    assert events.file_handler is not None and events.file_handler.stream is None


def test_all_registered_scorers_start_before_requests_and_keep_native_health_and_refusals(
    tmp_path: Path,
) -> None:
    from summary_evaluator_cases.service_cases import DirectRequest

    async def check() -> None:
        api = load_api_settings(API_SETTINGS_FILE).model_copy(
            update={"enabled_routes": ("coverage", "unieval", "hhem")}
        )
        hhem = service_settings()
        _, unieval = unieval_settings()
        coverage = coverage_settings()
        hhem_worker = RecordedSupervisor(hhem, (Scenario(),))
        unieval_worker = RecordedUnievalSupervisor(unieval)
        coverage_worker = RecordedCoverageSupervisor(coverage)
        log = EventLog()
        startup = StartupContext(run_id="component-registration")
        app = create_app(
            api,
            hhem,
            tmp_path,
            startup,
            writer=EventWriter(api.logging, log),
            supervisor=hhem_worker,
            unieval_settings=unieval,
            unieval_supervisor=unieval_worker,
            coverage_settings=coverage,
            coverage_supervisor=coverage_worker,
        )
        assert set(app.state.components) == set(get_args(ApiComponent))
        controllers = (app.state.controller, app.state.unieval, app.state.coverage)
        assert all(controller.worker.process is None for controller in controllers)
        assert app.state.controller.context == startup
        try:
            async with app.router.lifespan_context(app):
                assert all(controller.loading_task is not None for controller in controllers)
                await asyncio.gather(*(controller.loading_task for controller in controllers))
                assert all(controller.status == "ready" for controller in controllers)
                assert len({controller.worker.worker.pid for controller in controllers}) == len(
                    controllers
                )
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app),
                    base_url=f"http://{api.listener.host}:{api.listener.port}",
                    trust_env=False,
                ) as client:
                    shared = await client.get(API_HEALTH_PATH)
                    assert shared.status_code == 200
                    assert shared.json()["enabled_routes"] == list(api.enabled_routes)
                    for name, path in (
                        ("hhem", HHEM_HEALTH_PATH),
                        ("unieval", UNIEVAL_HEALTH_PATH),
                        ("coverage", COVERAGE_HEALTH_PATH),
                    ):
                        native = await client.get(path)
                        assert native.status_code == 200
                        assert shared.json()[name] == native.json()
                        assert native.json()["service_instance_id"] == app.state.service_instance_id
                    assert (await client.get(API_HEALTH_PATH)).status_code == 200
                    assert (
                        len(
                            [
                                event
                                for event in log.envelopes
                                if isinstance(event.data, ApiDiagnosticData)
                                and event.data.component == "api"
                                and event.data.action == "ready"
                            ]
                        )
                        == 1
                    )
                    for headers, code in (
                        (((b"origin", b"https://example.invalid"),), "ORIGIN_FORBIDDEN"),
                        (((b"host", b"example.invalid"),), "HOST_FORBIDDEN"),
                    ):
                        for path in (EVALUATE_PATH, UNIEVAL_PATH, COVERAGE_EVALUATE_PATH):
                            request = DirectRequest(
                                b"PrivateUnreadInputCanary", path=path, headers=headers
                            )
                            await request.run(app)
                            assert request.body_reads == 0 and request.messages[0]["status"] == 403
                            body = request.messages[1]["body"]
                            if path == EVALUATE_PATH:
                                assert (
                                    EvaluationResult.model_validate_json(body).errors[0].code
                                    == code
                                )
                            elif path == UNIEVAL_PATH:
                                assert (
                                    UnievalResult.model_validate_json(body).errors[0].code == code
                                )
                            else:
                                assert ApiErrorResult.model_validate_json(body).error.code == code
                            assert b"PrivateUnreadInputCanary" not in body
                    assert all(controller.queue.depth == 0 for controller in controllers)
        finally:
            hhem_worker.close_controls()
            coverage_worker.close_controls()
        assert all(controller.worker.exit_confirmed for controller in controllers)

    asyncio.run(check())


def test_startup_failure_cleans_all_components_and_retains_native_errors() -> None:
    async def check() -> None:
        api = load_api_settings(API_SETTINGS_FILE).model_copy(
            update={"enabled_routes": ("hhem", "unieval", "coverage")}
        )
        _, unieval = unieval_settings()
        stream = io.StringIO()
        app = create_app(
            api,
            service_settings(),
            REPOSITORY,
            writer=EventWriter(api.logging, stream),
            unieval_settings=unieval,
            coverage_settings=coverage_settings(),
        )
        stream.close()
        with pytest.raises(BaseExceptionGroup) as observed:
            async with app.router.lifespan_context(app):
                raise AssertionError("A failed startup cannot enter the request-serving lifespan")
        assert isinstance(observed.value.exceptions[0], RuntimeFailure)
        assert observed.value.exceptions[0].code == "LOGGING_FAILED"
        assert len(observed.value.exceptions) == len(app.state.components) + 2
        assert any(isinstance(error, EvaluationFailure) for error in observed.value.exceptions)
        for controller in (app.state.controller, app.state.unieval, app.state.coverage):
            assert controller.stopping and controller.loading_task is None
            assert controller.worker.process is None and controller.worker.exit_confirmed

    asyncio.run(check())
