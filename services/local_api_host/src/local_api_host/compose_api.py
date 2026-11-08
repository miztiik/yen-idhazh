"""How does one service component acquire a guarded FastAPI lifecycle and health route?"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

from local_api_host.contracts import HostSettings
from local_api_host.create_api_component import (
    ApiComponentRuntime,
    ComponentShutdownError,
    HealthRenderer,
    HostEventContext,
    HostEventSink,
    HostFailure,
    HostRequestContext,
)
from local_api_host.guard_requests import GuardRequests
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    PropagateTraceContext,
    TraceWarningHandler,
    create_root_operation,
    observe_request_operation,
    observe_request_started_at,
)


class _HostedFastAPI(FastAPI):
    """Place trace propagation outside request guards and FastAPI error handling."""

    def __init__(
        self,
        *args: Any,
        host_settings: HostSettings,
        component: ApiComponentRuntime[Any],
        invalid_trace_context: TraceWarningHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        default_refusal = component.default_refusal
        if default_refusal is None:
            raise ValueError("A local API component must declare its default refusal renderer")
        guarded = GuardRequests(
            super().__call__,
            host_settings,
            component.refuse_requests,
            default_refusal,
        )
        self._host_entry = PropagateTraceContext(
            guarded,
            host_settings.propagate_trace_context,
            invalid_trace_context=invalid_trace_context,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._host_entry(scope, receive, send)


def _cleanup_failures(error: BaseException) -> list[BaseException]:
    if isinstance(error, ComponentShutdownError):
        return list(error.failures)
    return [error]


def compose_api[HealthT, EventT](
    settings: HostSettings,
    component: ApiComponentRuntime[HealthT],
    render_health: HealthRenderer[HealthT],
    events: HostEventSink[HealthT, EventT],
    *,
    service_instance_id: str | None = None,
    service_operation: OperationMetadata | None = None,
    invalid_trace_context: TraceWarningHandler | None = None,
) -> FastAPI:
    """Compose one component without inspecting its health or event vocabulary."""
    identity = service_instance_id or str(uuid4())
    service_context = HostEventContext(
        service_instance_id=identity,
        operation=(
            service_operation or create_root_operation()
            if settings.propagate_trace_context
            else None
        ),
    )
    started_at = time.monotonic()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        failure: BaseException | None = None
        try:
            await events.started(service_context, events.data.started())
            await component.start()
            yield
        except BaseException as error:
            failure = error
            raise
        finally:
            cleanup: list[BaseException] = []
            try:
                await component.shutdown()
            except BaseException as error:
                cleanup.extend(_cleanup_failures(error))
            try:
                if cleanup:
                    await events.failed(
                        service_context,
                        events.data.failed(HostFailure(phase="shutdown")),
                    )
                else:
                    await events.stopped(service_context, events.data.stopped())
            except BaseException as error:
                cleanup.append(error)
            try:
                await events.aclose()
            except BaseException as error:
                cleanup.append(error)
            if cleanup:
                if failure is None and len(cleanup) == 1:
                    raise cleanup[0]
                raise BaseExceptionGroup(
                    "Shared API cleanup failed",
                    [failure, *cleanup] if failure is not None else cleanup,
                )

    app = _HostedFastAPI(
        title=settings.title,
        version=settings.schema_version,
        docs_url=None,
        redoc_url=None,
        openapi_url=settings.schema_path,
        redirect_slashes=False,
        lifespan=lifespan,
        host_settings=settings,
        component=component,
        invalid_trace_context=invalid_trace_context,
    )
    app.state.component = component
    app.state.service_instance_id = identity
    app.state.host_settings = settings
    app.state.host_events = events
    app.state.ready_emitted = False
    app.include_router(component.router)

    @app.get(settings.health_path, response_model=render_health.response_model)
    async def health(request: Request) -> Response:
        observed = await component.observe_health()
        request_context = HostRequestContext(
            service_instance_id=identity,
            operation=observe_request_operation(request),
            request_started_at=observe_request_started_at(request),
        )
        rendered = render_health.render(request_context, observed)
        if rendered.ready and not app.state.ready_emitted:
            await events.ready(
                service_context,
                events.data.ready(observed, (time.monotonic() - started_at) * 1000),
            )
            app.state.ready_emitted = True
        return rendered.response

    return app
