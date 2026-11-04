"""How does one FastAPI lifespan compose explicit HHEM and native llama routes?"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI
from starlette.responses import JSONResponse

from .contracts.api_health import ApiHealth, DisabledHhemHealth
from .contracts.api_settings import ApiSettings
from .contracts.base import API_PREFIX
from .contracts.llama_result import LlamaHealth
from .contracts.llama_settings import LlamaSettings
from .contracts.server_contract import SERVER_SCHEMA_VERSION
from .contracts.server_event import ApiDiagnosticData
from .contracts.service_settings import ServiceSettings, StartupContext
from .control_service import EvaluationController
from .emit_events import EventWriter
from .forward_llama import LlamaForwarder
from .guard_local_requests import GuardLocalRequests
from .hhem_router import create_hhem_router
from .llama_router import create_llama_router, declare_llama_request_schema
from .load_llama_settings import load_llama_settings
from .maintain_worker import WorkerSupervisor
from .resolve_ids import create_execution_id


def create_app(
    api: ApiSettings,
    settings: ServiceSettings | None,
    root: Path,
    context: StartupContext | None = None,
    *,
    supervisor: WorkerSupervisor | None = None,
    writer: EventWriter | None = None,
    llama_settings: LlamaSettings | None = None,
    llama_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    if "hhem" in api.enabled_routes:
        if settings is None:
            raise ValueError("Enabled HHEM requires its named scoring settings")
        if (
            not settings.enabled
            or settings.listener != api.listener
            or settings.logging != api.logging
        ):
            raise ValueError(
                "The HHEM snapshot must use shared route, listener and logging settings"
            )
        if api.shutdown_timeout_ms < settings.worker.shutdown_timeout_ms:
            raise ValueError("The API shutdown wait must accommodate the HHEM shutdown wait")
    selected: LlamaSettings | None = None
    if "llama" in api.enabled_routes:
        selected = llama_settings or load_llama_settings(root / "config" / "idhazh.json")
        if urlsplit(selected.base_url).port == api.listener.port:
            raise ValueError("The native model port conflicts with the shared API listener")
    events = writer or EventWriter(
        api.logging,
        directory=root / api.log_directory,
        run_id=context.run_id if context is not None else None,
    )
    controller = (
        EvaluationController(
            settings, context or StartupContext(), root, supervisor=supervisor, writer=events
        )
        if "hhem" in api.enabled_routes and settings is not None
        else None
    )
    instance_id = controller.instance_id if controller is not None else create_execution_id()
    forwarder: LlamaForwarder | None = None
    if selected is not None:
        forwarder = LlamaForwarder(api, selected, events, transport=llama_transport)
    started_at = time.monotonic()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        failure: BaseException | None = None
        try:
            events.diagnostic(ApiDiagnosticData(component="api", action="started", level="INFO"))
            if forwarder is not None:
                await forwarder.start()
            if controller is not None:
                await controller.start()
            yield
        except BaseException as error:
            failure = error
            raise
        finally:
            cleanup: list[BaseException] = []
            if forwarder is not None:
                try:
                    await forwarder.close()
                except BaseException as error:
                    cleanup.append(error)
            if controller is not None:
                try:
                    await controller.shutdown()
                except BaseException as error:
                    cleanup.append(error)
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
                raise BaseExceptionGroup(
                    "Shared API cleanup failed", [failure, *cleanup] if failure else cleanup
                )

    app = FastAPI(
        title="local-model-api",
        version=SERVER_SCHEMA_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        redirect_slashes=False,
        lifespan=lifespan,
    )
    app.state.controller, app.state.forwarder, app.state.events = controller, forwarder, events
    app.state.service_instance_id = instance_id
    app.state.api_settings = api
    app.state.ready_emitted = False
    app.add_middleware(GuardLocalRequests, settings=api, controller=controller)
    if controller is not None:
        app.include_router(create_hhem_router(controller))
    if forwarder is not None:
        app.include_router(create_llama_router(forwarder))

    @app.get("/health", response_model=ApiHealth)
    async def health() -> JSONResponse:
        native = (
            await forwarder.health()
            if forwarder is not None
            else LlamaHealth(status="disabled", http_status=None, failure_code=None)
        )
        hhem = controller.health() if controller is not None else DisabledHhemHealth()
        states = [
            hhem.status if component == "hhem" else native.status
            for component in api.enabled_routes
        ]
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
                "service_instance_id": instance_id,
                "enabled_routes": api.enabled_routes,
                "status": status,
                "hhem": hhem,
                "llama": native,
                "log_file": events.log_file,
                "log_available": events.log_available,
            }
        )
        return JSONResponse(observed.model_dump(mode="json"), status_code=observed.http_status)

    if forwarder is not None:
        declare_llama_request_schema(app)
    return app
