"""How does one FastAPI host compose explicitly registered native components?"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from fastapi import FastAPI
from starlette.responses import JSONResponse

from summary_evaluator.serve_http.contracts.api_health import ApiHealth, DisabledEvaluatorHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.guard_local_requests import GuardLocalRequests
from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH, API_SCHEMA_PATH
from summary_evaluator.shared.contracts.server_contract import SERVER_SCHEMA_VERSION
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_api_component import (
    ApiComponentRuntime,
    ComponentContext,
    RefusalHandler,
)
from summary_evaluator.shared.create_execution_id import create_execution_id


@dataclass(frozen=True)
class ComponentRegistration:
    """Name a declared component, its private state alias and its native setup."""

    name: ApiComponent
    state_attribute: str
    create: Callable[[ComponentContext, EventWriter], ApiComponentRuntime]


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
    )
    host = ComponentContext(
        root=root,
        listener=api.listener,
        logging=api.logging,
        shutdown_timeout_ms=api.shutdown_timeout_ms,
        startup=context or StartupContext(),
        service_instance_id=create_execution_id(),
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
        try:
            events.close()
        except BaseException as cleanup:
            raise BaseExceptionGroup("Shared API construction failed", [failure, cleanup]) from None
        raise
    started_at = time.monotonic()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        failure: BaseException | None = None
        try:
            events.diagnostic(ApiDiagnosticData(component="api", action="started", level="INFO"))
            for component in components.values():
                await component.start()
            yield
        except BaseException as error:
            failure = error
            raise
        finally:
            outcomes = await asyncio.gather(
                *(component.shutdown() for component in components.values()), return_exceptions=True
            )
            cleanup = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
            try:
                events.diagnostic(
                    ApiDiagnosticData(
                        component="api",
                        action="failed" if cleanup else "stopped",
                        level="ERROR" if cleanup else "INFO",
                        code="SHUTDOWN_FAILED" if cleanup else None,
                    )
                )
            except BaseException as error:
                cleanup.append(error)
            try:
                events.close()
            except BaseException as error:
                cleanup.append(error)
            if cleanup:
                if failure is None and len(cleanup) == 1:
                    raise cleanup[0]
                raise BaseExceptionGroup(
                    "Shared API cleanup failed", [failure, *cleanup] if failure else cleanup
                )

    app = FastAPI(
        title="summary-evaluator",
        version=SERVER_SCHEMA_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=API_SCHEMA_PATH,
        redirect_slashes=False,
        lifespan=lifespan,
    )
    for registration in registrations:
        runtime = components.get(registration.name)
        setattr(app.state, registration.state_attribute, runtime.state if runtime else None)
    app.state.components, app.state.events = components, events
    app.state.service_instance_id = host.service_instance_id
    app.state.api_settings = api
    app.state.ready_emitted = False
    app.add_middleware(GuardLocalRequests, settings=api, refuse_requests=refusals)
    for component in components.values():
        app.include_router(component.router)

    @app.get(API_HEALTH_PATH, response_model=ApiHealth)
    async def health() -> JSONResponse:
        observations = {
            name: await component.observe_health() for name, component in components.items()
        }
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
        if status == "ready" and not app.state.ready_emitted:
            events.diagnostic(
                ApiDiagnosticData(
                    component="api",
                    action="ready",
                    level="INFO",
                    duration_ms=(time.monotonic() - started_at) * 1000,
                )
            )
            app.state.ready_emitted = True
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
        return JSONResponse(observed.model_dump(mode="json"), status_code=observed.http_status)

    return app
