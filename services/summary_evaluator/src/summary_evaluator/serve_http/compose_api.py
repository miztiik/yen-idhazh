"""How does the evaluator adapt registered scorers to one neutral API component?"""

import asyncio
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Final, get_args

from fastapi import APIRouter, FastAPI
from local_api_host.compose_api import compose_api
from local_api_host.contracts import HostSettings
from local_api_host.contracts import ListenerSettings as HostListenerSettings
from local_api_host.create_api_component import (
    ApiComponentRuntime as HostApiComponentRuntime,
)
from local_api_host.create_api_component import (
    ComponentShutdownError,
    HealthRenderer,
    HostEventContext,
    HostEventDataFactory,
    HostEventSink,
    HostFailure,
    HostRefusalCode,
    HostRequestContext,
    RenderedHealth,
)
from local_api_host.propagate_trace_context import OperationMetadata
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from summary_evaluator.serve_http.contracts.api_health import ApiHealth, DisabledEvaluatorHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH, API_SCHEMA_PATH
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES
from summary_evaluator.shared.contracts.server_contract import SERVER_SCHEMA_VERSION
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_api_component import (
    ApiComponentRuntime,
    ComponentContext,
    ComponentHealth,
    RefusalHandler,
)
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.fail_runtime import RuntimeFailure

SUMMARY_EVALUATOR_TITLE: Final = "summary-evaluator"


@dataclass(frozen=True)
class ComponentRegistration:
    """Name a declared component, its private state alias and its native setup."""

    name: ApiComponent
    state_attribute: str
    create: Callable[[ComponentContext, EventWriter], ApiComponentRuntime]


@dataclass(frozen=True)
class EvaluatorHealthObservation:
    """Retain native scorer health without teaching the host its vocabulary."""

    components: Mapping[ApiComponent, ComponentHealth]


def create_host_settings(api: ApiSettings) -> HostSettings:
    """Project evaluator settings into the neutral host contract."""
    return HostSettings(
        title=SUMMARY_EVALUATOR_TITLE,
        schema_version=SERVER_SCHEMA_VERSION,
        health_path=API_HEALTH_PATH,
        schema_path=API_SCHEMA_PATH,
        listener=HostListenerSettings.model_validate(api.listener.model_dump(mode="json")),
        shutdown_timeout_ms=api.shutdown_timeout_ms,
        propagate_trace_context=api.propagate_trace_context,
    )


def _close_construction_events(events: EventWriter, failure: BaseException) -> None:
    try:
        events.close()
    except BaseException as cleanup:
        raise BaseExceptionGroup(
            "Shared API construction failed",
            [failure, cleanup],
        ) from None


def compose_app(
    api: ApiSettings,
    root: Path,
    context: StartupContext | None = None,
    *,
    registrations: tuple[ComponentRegistration, ...],
    writer: EventWriter | None = None,
) -> FastAPI:
    names = tuple(registration.name for registration in registrations)
    if len(set(names)) != len(names) or set(names) != set(get_args(ApiComponent)):
        raise ValueError("Registered API components must match the declared component vocabulary")
    if not set(api.enabled_routes).issubset(names):
        raise ValueError("Enabled API components must have a declared registration")
    events = writer or EventWriter(
        api.logging,
        directory=root / api.log_directory,
        run_id=context.run_id if context is not None else None,
        propagate_trace_context=api.propagate_trace_context,
    )
    events.bind_trace_mode(api.propagate_trace_context)
    service_instance_id = create_execution_id()
    host = ComponentContext(
        root=root,
        listener=api.listener,
        logging=api.logging,
        shutdown_timeout_ms=api.shutdown_timeout_ms,
        startup=context or StartupContext(),
        service_instance_id=service_instance_id,
        service_operation=events.service_operation,
        propagate_trace_context=api.propagate_trace_context,
    )
    components: dict[ApiComponent, ApiComponentRuntime] = {}
    refusals: dict[str, RefusalHandler] = {}
    try:
        for registration in registrations:
            if registration.name not in api.enabled_routes:
                continue
            component = registration.create(host, events)
            if refusals.keys() & component.refuse_requests.keys():
                raise ValueError("Registered API components must have distinct refusal paths")
            components[registration.name] = component
            refusals.update(component.refuse_requests)
    except BaseException as failure:
        _close_construction_events(events, failure)
        raise

    router = APIRouter()
    for component in components.values():
        router.include_router(component.router)

    async def start_components() -> None:
        for component in components.values():
            await component.start()

    async def shutdown_components() -> None:
        outcomes = await asyncio.gather(
            *(component.shutdown() for component in components.values()),
            return_exceptions=True,
        )
        cleanup = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        if len(cleanup) == 1:
            raise cleanup[0]
        if cleanup:
            raise ComponentShutdownError(tuple(cleanup))

    async def observe_health() -> EvaluatorHealthObservation:
        return EvaluatorHealthObservation(
            components={
                name: await component.observe_health() for name, component in components.items()
            }
        )

    async def default_refusal(
        _request: Request,
        code: HostRefusalCode,
    ) -> Response:
        policy = ERROR_POLICIES[code]
        return refuse_request(code, policy.message, 403)

    aggregate = HostApiComponentRuntime(
        router=router,
        state=components,
        start=start_components,
        shutdown=shutdown_components,
        observe_health=observe_health,
        refuse_requests=refusals,
        default_refusal=default_refusal,
    )

    def render_health(
        _request: HostRequestContext,
        observation: EvaluatorHealthObservation,
    ) -> RenderedHealth:
        observations = observation.components
        states = [observations[name].status for name in api.enabled_routes]
        status = (
            "disabled"
            if not states
            else "ready"
            if all(state == "ready" for state in states)
            else "failed"
            if "failed" in states
            else "stopping"
            if "stopping" in states
            else "loading"
        )
        observed = ApiHealth.model_validate(
            {
                "version": SERVER_SCHEMA_VERSION,
                "service_instance_id": host.service_instance_id,
                "enabled_routes": api.enabled_routes,
                "status": status,
                **{
                    name: observations[name].payload
                    if name in observations
                    else DisabledEvaluatorHealth()
                    for name in names
                },
                "log_file": events.log_file,
                "log_available": events.log_available,
            }
        )
        return RenderedHealth(
            response=JSONResponse(
                observed.model_dump(mode="json"),
                status_code=observed.http_status,
            ),
            ready=status == "ready",
        )

    def translate_host_failure(failure: HostFailure) -> ApiDiagnosticData:
        if failure.phase == "startup":
            return ApiDiagnosticData(component="api", action="stopped", level="INFO")
        return ApiDiagnosticData(
            component="api",
            action="failed",
            level="ERROR",
            code="SHUTDOWN_FAILED",
        )

    data = HostEventDataFactory[
        EvaluatorHealthObservation,
        ApiDiagnosticData,
    ](
        started=lambda: ApiDiagnosticData(component="api", action="started", level="INFO"),
        ready=lambda _health, duration_ms: ApiDiagnosticData(
            component="api",
            action="ready",
            level="INFO",
            duration_ms=duration_ms,
        ),
        stopped=lambda: ApiDiagnosticData(component="api", action="stopped", level="INFO"),
        failed=translate_host_failure,
    )

    async def emit_event(
        event_context: HostEventContext,
        event: ApiDiagnosticData,
    ) -> None:
        events.diagnostic(event, event_context.operation or host.service_operation)

    async def warn_invalid_trace(request: Request, operation: OperationMetadata) -> Response | None:
        try:
            events.diagnostic(
                ApiDiagnosticData(
                    component="api",
                    action="failed",
                    level="WARNING",
                    code="INVALID_TRACE_CONTEXT",
                ),
                operation,
            )
        except RuntimeFailure as failure:
            for runtime in components.values():
                if request.method == "POST" and request.url.path in runtime.refuse_requests:
                    return await runtime.refuse_failure(request, failure.code)
            return PlainTextResponse(
                HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
        return None

    async def close_events() -> None:
        events.close()

    try:
        app = compose_api(
            create_host_settings(api),
            aggregate,
            HealthRenderer(response_model=ApiHealth, render=render_health),
            HostEventSink(
                data=data,
                started=emit_event,
                ready=emit_event,
                stopped=emit_event,
                failed=emit_event,
                aclose=close_events,
            ),
            service_instance_id=service_instance_id,
            service_operation=host.service_operation,
            invalid_trace_context=warn_invalid_trace,
        )
    except BaseException as failure:
        _close_construction_events(events, failure)
        raise
    for registration in registrations:
        runtime = components.get(registration.name)
        setattr(app.state, registration.state_attribute, runtime.state if runtime else None)
    app.state.components, app.state.events = components, events
    app.state.service_instance_id = host.service_instance_id
    app.state.api_settings = api
    return app
