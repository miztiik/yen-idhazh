"""How are the native GLiNER2 operations bound to the existing guarded API host?"""

import asyncio
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TextIO, cast

from fastapi import APIRouter, FastAPI
from local_api_host.compose_api import compose_api
from local_api_host.contracts import HostSettings
from local_api_host.create_api_component import (
    ApiComponentRuntime,
    HealthRenderer,
    HostEventContext,
    HostEventDataFactory,
    HostEventSink,
    HostRefusalCode,
    HostRequestContext,
    RenderedHealth,
)
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_root_operation,
    observe_request_operation,
)
from local_api_host.read_request_body import (
    ClientDisconnectedError,
    RequestBodyError,
    read_request_body,
)
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from gliner_api.analyze_text import analyze_text
from gliner_api.declare_analysis_contracts import AnalyzeTextRequest, AnalyzeTextResult
from gliner_api.declare_api_contracts import (
    ANALYZE_TEXT_PATH,
    API_VERSION,
    APPLICATION_TITLE,
    HEALTH_PATH,
    SCHEMA_PATH,
    ApiContract,
    ErrorCode,
    ErrorDetail,
    ErrorResult,
    GlinerHealth,
    OperationName,
)
from gliner_api.declare_event_contracts import EventType, RequestEventData, ServiceEventData
from gliner_api.declare_schema import install_request_schemas
from gliner_api.emit_events import EventDeliveryError, EventEmitter
from gliner_api.load_model import NativeModel
from gliner_api.load_settings import GlinerSettings
from gliner_api.run_model import ModelRuntime, OperationError

_OPERATIONS: dict[str, OperationName] = {
    ANALYZE_TEXT_PATH: "analyze-text-gliner",
}


def _json_response(
    model: ApiContract, status: int, headers: Mapping[str, str] | None = None
) -> Response:
    return Response(
        model.model_dump_json(),
        status_code=status,
        media_type="application/json",
        headers=headers,
    )


def create_app(
    settings: GlinerSettings,
    transport: HostSettings,
    *,
    root: Path,
    stream: TextIO | None = None,
) -> FastAPI:
    """Consume existing listener bounds without importing another provider's model code."""
    if not transport.propagate_trace_context:
        raise ValueError("The GLiNER API requires W3C trace transport.")
    hosting = HostSettings.model_validate(
        transport.model_dump()
        | {
            "title": APPLICATION_TITLE,
            "schema_version": API_VERSION,
            "health_path": HEALTH_PATH,
            "schema_path": SCHEMA_PATH,
        }
    )
    emitter = EventEmitter(settings.logging, stream)
    runtime = ModelRuntime(settings, root, hosting.shutdown_timeout_ms)
    service_operation = create_root_operation()
    router = APIRouter()

    async def emit_request(
        request: Request,
        operation_name: OperationName,
        error: ErrorDetail | None,
    ) -> bool:
        operation = observe_request_operation(request)
        if operation is None:
            raise RuntimeError("The GLiNER request requires receiving operation metadata.")
        try:
            await emitter.emit(
                operation,
                "gliner.request.failed" if error is not None else "gliner.request.completed",
                RequestEventData(
                    operation=operation_name,
                    status="failed" if error is not None else "complete",
                    error_code=error.code if error is not None else None,
                ),
            )
        except EventDeliveryError:
            runtime.mark_failed("LOGGING_FAILED")
            return False
        return True

    async def request_error(
        request: Request,
        code: ErrorCode,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        error = ErrorDetail.from_code(code)
        operation_name = _OPERATIONS.get(request.url.path)
        if operation_name is not None and not await emit_request(request, operation_name, error):
            error = ErrorDetail.from_code("LOGGING_FAILED")
        return _json_response(ErrorResult(error=error), error.http_status, headers)

    async def process[
        RequestT,
        ResultT: ApiContract,
    ](
        request: Request,
        parse: Callable[[bytes], RequestT],
        run: Callable[[NativeModel, RequestT], ResultT],
    ) -> Response:
        try:
            body = await read_request_body(request, hosting.listener)
        except ClientDisconnectedError:
            raise asyncio.CancelledError from None
        except RequestBodyError as error:
            return await request_error(
                request, "BODY_TOO_LARGE" if error.code == "BODY_TOO_LARGE" else "INVALID_REQUEST"
            )
        try:
            parsed = parse(body)
        except ValidationError:
            return await request_error(request, "INVALID_REQUEST")
        finally:
            del body
        if not settings.enabled:
            return await request_error(request, "SERVICE_DISABLED")

        async def emit_terminal(outcome: ResultT | OperationError) -> None:
            error = (
                ErrorDetail.from_code(outcome.code)
                if isinstance(outcome, OperationError)
                else None
            )
            if not await emit_request(request, _OPERATIONS[request.url.path], error):
                raise OperationError("LOGGING_FAILED")

        try:
            result = await runtime.execute(
                lambda model: run(model, parsed),
                terminal=emit_terminal,
            )
        except OperationError as error:
            detail = ErrorDetail.from_code(error.code)
            return _json_response(
                ErrorResult(error=detail),
                detail.http_status,
            )
        return _json_response(result, 200)

    errors: dict[int | str, dict[str, object]] = {
        status: {"model": ErrorResult} for status in (403, 413, 422, 500, 503)
    }

    @router.post(
        ANALYZE_TEXT_PATH,
        response_model=AnalyzeTextResult,
        responses=errors,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/AnalyzeTextRequest"}
                    }
                },
            }
        },
    )
    async def analyze_text_gliner(request: Request) -> Response:
        return await process(
            request,
            lambda body: AnalyzeTextRequest.model_validate_json(body, strict=True),
            lambda model, parsed: analyze_text(model, parsed, settings),
        )

    async def refuse(request: Request, code: HostRefusalCode) -> Response:
        return await request_error(request, code)

    async def start() -> None:
        await runtime.start()
        if runtime.status == "failed":
            await emitter.emit(
                service_operation,
                "gliner.service.failed",
                ServiceEventData(
                    status="failed", enabled=settings.enabled, error_code="MODEL_UNAVAILABLE"
                ),
            )

    async def observe_health() -> GlinerHealth:
        return runtime.observe_health()

    component = ApiComponentRuntime[GlinerHealth](
        router=router,
        state=runtime,
        start=start,
        shutdown=runtime.shutdown,
        observe_health=observe_health,
        refuse_requests={path: refuse for path in _OPERATIONS},
        default_refusal=refuse,
    )

    def render_health(_context: HostRequestContext, health: GlinerHealth) -> RenderedHealth:
        return RenderedHealth(
            response=_json_response(health, 200 if health.status == "ready" else 503),
            ready=health.status == "ready",
        )

    async def emit_service(context: HostEventContext, data: ServiceEventData) -> None:
        operation: OperationMetadata | None = context.operation
        if operation is None:
            raise RuntimeError("GLiNER lifecycle diagnostics require W3C transport.")
        event_type: EventType = cast(
            EventType,
            {
                "starting": "gliner.service.started",
                "disabled": "gliner.service.started",
                "ready": "gliner.service.ready",
                "stopped": "gliner.service.stopped",
                "failed": "gliner.service.failed",
            }[data.status],
        )
        await emitter.emit(operation, event_type, data)

    event_data = HostEventDataFactory[GlinerHealth, ServiceEventData](
        started=lambda: ServiceEventData(
            status="starting" if settings.enabled else "disabled", enabled=settings.enabled
        ),
        ready=lambda _health, _duration: ServiceEventData(
            status="ready", enabled=settings.enabled
        ),
        stopped=lambda: ServiceEventData(status="stopped", enabled=settings.enabled),
        failed=lambda failure: ServiceEventData(
            status="failed",
            enabled=settings.enabled,
            error_code="STARTUP_FAILED" if failure.phase == "startup" else "SHUTDOWN_FAILED",
        ),
    )
    app = compose_api(
        hosting,
        component,
        HealthRenderer[GlinerHealth](response_model=GlinerHealth, render=render_health),
        HostEventSink[GlinerHealth, ServiceEventData](
            data=event_data,
            started=emit_service,
            ready=emit_service,
            stopped=emit_service,
            failed=emit_service,
            aclose=emitter.aclose,
        ),
        service_operation=service_operation,
    )

    @app.exception_handler(HTTPException)
    async def refuse_unknown(request: Request, error: HTTPException) -> Response:
        return await request_error(
            request,
            "METHOD_NOT_ALLOWED" if error.status_code == 405 else "NOT_FOUND",
            headers=error.headers,
        )

    install_request_schemas(app)
    return app
