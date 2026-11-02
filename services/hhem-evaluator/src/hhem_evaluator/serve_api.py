"""Which native routes expose the bounded local evaluator without reading bodies early?"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .contracts.base import API_PREFIX
from .contracts.error_detail import ErrorDetail
from .contracts.evaluate_request import EvaluateRequest
from .contracts.evaluation_result import EvaluationResult
from .contracts.service_health import ServiceHealth
from .contracts.service_settings import ServiceSettings, StartupContext
from .control_service import EvaluationController
from .dispatch_evaluation import dispatch_evaluation
from .emit_events import EventWriter
from .maintain_worker import WorkerSupervisor


class GuardLocalRequests:
    """Refuse browser origins and hosts without redirecting or consuming input."""

    def __init__(self, app: ASGIApp, controller: EvaluationController) -> None:
        self.app, self.controller = app, controller

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        listener = self.controller.settings.listener
        host = f"[{listener.host}]" if ":" in listener.host else listener.host
        error = None
        if "origin" in request.headers:
            error = ErrorDetail.from_code("ORIGIN_FORBIDDEN", "request")
        elif len(request.headers.getlist("host")) != 1 or request.headers.get("host") not in (
            host,
            f"{host}:{listener.port}",
        ):
            error = ErrorDetail.from_code("HOST_FORBIDDEN", "request")
        if error is not None:
            response = await dispatch_evaluation(request, self.controller, error)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def create_app(
    settings: ServiceSettings,
    root: Path,
    context: StartupContext | None = None,
    *,
    supervisor: WorkerSupervisor | None = None,
    writer: EventWriter | None = None,
) -> FastAPI:
    controller = EvaluationController(
        settings, context or StartupContext(), root, supervisor=supervisor, writer=writer
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await controller.start()
        try:
            yield
        finally:
            await controller.shutdown()

    app = FastAPI(
        title="Local HHEM evaluation",
        version=settings.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        redirect_slashes=False,
        lifespan=lifespan,
    )
    app.state.controller = controller
    app.add_middleware(GuardLocalRequests, controller=controller)

    @app.get(f"{API_PREFIX}/health", response_model=ServiceHealth)
    async def health() -> JSONResponse:
        observed = controller.health()
        return JSONResponse(observed.model_dump(mode="json"), status_code=observed.http_status)

    @app.post(
        f"{API_PREFIX}/evaluate",
        response_model=EvaluationResult,
        responses={
            status: {"model": EvaluationResult}
            for status in (400, 403, 408, 413, 415, 429, 500, 503, 504)
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": EvaluateRequest.model_json_schema()}},
            }
        },
    )
    async def evaluate(request: Request) -> Response:
        return await dispatch_evaluation(request, controller)

    return app
