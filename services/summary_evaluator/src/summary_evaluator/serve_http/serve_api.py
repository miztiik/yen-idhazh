"""How does one FastAPI lifespan compose independent summary evaluators?"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import JSONResponse

from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.control_service import EvaluationController
from summary_evaluator.hhem.hhem_router import create_hhem_router
from summary_evaluator.hhem.maintain_worker import WorkerSupervisor
from summary_evaluator.serve_http.contracts.api_health import ApiHealth, DisabledEvaluatorHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.contracts.server_event import ApiDiagnosticData
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.guard_local_requests import GuardLocalRequests
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.shared.contracts.api_paths import API_HEALTH_PATH, API_SCHEMA_PATH
from summary_evaluator.shared.contracts.server_contract import SERVER_SCHEMA_VERSION
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.control_unieval import UnievalController
from summary_evaluator.unieval.maintain_unieval_worker import UnievalSupervisor
from summary_evaluator.unieval.unieval_router import create_unieval_router


def create_app(
    api: ApiSettings,
    settings: ServiceSettings | None,
    root: Path,
    context: StartupContext | None = None,
    *,
    supervisor: WorkerSupervisor | None = None,
    writer: EventWriter | None = None,
    unieval_settings: UnievalSettings | None = None,
    unieval_supervisor: UnievalSupervisor | None = None,
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
    events = writer or EventWriter(
        api.logging,
        directory=root / api.log_directory,
        run_id=context.run_id if context is not None else None,
    )
    controller = (
        EvaluationController(
            settings, context or StartupContext(), root, supervisor=supervisor, writer=events.write
        )
        if "hhem" in api.enabled_routes and settings is not None
        else None
    )
    instance_id = controller.instance_id if controller is not None else create_execution_id()
    unieval: UnievalController | None = None
    if "unieval" in api.enabled_routes:
        selected_unieval = unieval_settings or load_unieval_settings(root, api)
        if (
            selected_unieval.listener != api.listener
            or selected_unieval.logging != api.logging
            or selected_unieval.worker.shutdown_timeout_ms > api.shutdown_timeout_ms
        ):
            raise ValueError("UniEval must use the shared listener, logging and shutdown bounds")
        unieval = UnievalController(
            selected_unieval,
            root,
            events.unieval_diagnostic,
            instance_id,
            supervisor=unieval_supervisor,
        )
    started_at = time.monotonic()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        failure: BaseException | None = None
        try:
            events.diagnostic(ApiDiagnosticData(component="api", action="started", level="INFO"))
            if controller is not None:
                await controller.start()
            if unieval is not None:
                await unieval.start()
            yield
        except BaseException as error:
            failure = error
            raise
        finally:
            stopping = []
            if controller is not None:
                stopping.append(controller.shutdown())
            if unieval is not None:
                stopping.append(unieval.shutdown())
            outcomes = await asyncio.gather(*stopping, return_exceptions=True)
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
    app.state.controller, app.state.events = controller, events
    app.state.unieval = unieval
    app.state.service_instance_id = instance_id
    app.state.api_settings = api
    app.state.ready_emitted = False
    app.add_middleware(GuardLocalRequests, settings=api, controller=controller, unieval=unieval)
    if controller is not None:
        app.include_router(create_hhem_router(controller))
    if unieval is not None:
        app.include_router(create_unieval_router(unieval))

    @app.get(API_HEALTH_PATH, response_model=ApiHealth)
    async def health() -> JSONResponse:
        hhem = controller.health() if controller is not None else DisabledEvaluatorHealth()
        observed_unieval = (
            await unieval.health() if unieval is not None else DisabledEvaluatorHealth()
        )
        components = {"hhem": hhem, "unieval": observed_unieval}
        states = [components[component].status for component in api.enabled_routes]
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
                "unieval": observed_unieval,
                "log_file": events.log_file,
                "log_available": events.log_available,
            }
        )
        return JSONResponse(observed.model_dump(mode="json"), status_code=observed.http_status)

    return app
