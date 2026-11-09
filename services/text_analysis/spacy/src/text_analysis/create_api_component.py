"""How does the text-analysis service bind its contracts and runtime to the host?"""

import asyncio
import time
from typing import Literal, cast

from fastapi import APIRouter, FastAPI
from local_api_host.compose_api import compose_api
from local_api_host.contracts import HostSettings
from local_api_host.contracts import ListenerSettings as HostListenerSettings
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
    observe_request_operation,
    observe_request_started_at,
)
from local_api_host.read_request_body import (
    ClientDisconnectedError,
    RequestBodyError,
    read_request_body,
)
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from text_analysis.declare_api_contracts import (
    ANALYZE_TEXT_PATH,
    API_SCHEMA_VERSION,
    HEALTH_PATH,
    SCHEMA_PATH,
    AnalysisCommand,
    AnalysisOutcome,
    AnalysisResult,
    AnalyzeTextRequest,
    ErrorCode,
    ErrorDetail,
    ErrorResult,
    EventType,
    FeatureErrorCode,
    FeatureResult,
    LanguageCapability,
    ModelIdentity,
    OutcomeStatus,
    ProfileCapability,
    RequestEventData,
    RequestFeatureStatus,
    ServiceEventData,
    ServiceEventStatus,
    ServiceFailureCode,
    TextAnalysisHealth,
)
from text_analysis.declare_service_settings import (
    EnabledLanguage,
    FeatureName,
    LanguageCode,
    ModelProfile,
    ServiceSettings,
)
from text_analysis.emit_events import EventEmitter
from text_analysis.run_analysis import (
    AnalysisRuntime,
    RuntimeAdmissionError,
)

APPLICATION_TITLE = "text-analysis"


def _json_response(
    model: ErrorResult | AnalysisResult | TextAnalysisHealth,
    status: int,
) -> Response:
    return Response(
        model.model_dump_json(),
        status_code=status,
        media_type="application/json",
    )


def _health_capabilities(settings: ServiceSettings) -> tuple[LanguageCapability, ...]:
    capabilities: list[LanguageCapability] = []
    for language in ("en", "zh", "ta"):
        language_settings = settings.languages.select(cast(LanguageCode, language))
        capabilities.append(
            LanguageCapability(
                language=cast(LanguageCode, language),
                enabled=language_settings.enabled,
                default_profile=language_settings.default_profile,
                supported_features=language_settings.supported_features,
                default_features=(
                    settings.resolve_default_features(cast(LanguageCode, language))
                    if language_settings.enabled
                    else ()
                ),
                important_terms_limit=(
                    settings.important_terms.max_results
                    if language == "en"
                    and language_settings.enabled
                    and "important_terms" in language_settings.supported_features
                    else None
                ),
                profiles=tuple(
                    ProfileCapability(
                        profile=profile,
                        package=model.package,
                        model_version=model.version,
                    )
                    for profile, model in language_settings.profiles.items()
                ),
            )
        )
    return tuple(capabilities)


def _observe_health(
    settings: ServiceSettings,
    runtime: AnalysisRuntime,
) -> TextAnalysisHealth:
    return TextAnalysisHealth(
        enabled=settings.enabled,
        status=runtime.status,
        active_requests=runtime.active_requests,
        max_concurrent_requests=settings.max_concurrent_requests,
        pool_ready=runtime.pool_ready,
        spacy_version=settings.spacy_version,
        default_features=settings.default_features,
        allowed_features=settings.allowed_features,
        languages=_health_capabilities(settings),
    )


def _service_event_data(
    settings: ServiceSettings,
    runtime: AnalysisRuntime,
    *,
    status: ServiceEventStatus,
    level: Literal["INFO", "ERROR"] = "INFO",
    error_code: ServiceFailureCode | None = None,
) -> ServiceEventData:
    return ServiceEventData.model_validate(
        {
            "level": level,
            "enabled": settings.enabled,
            "status": status,
            "active_requests": runtime.active_requests,
            "max_concurrent_requests": settings.max_concurrent_requests,
            "pool_ready": runtime.pool_ready,
            **({"error_code": error_code} if error_code is not None else {}),
        }
    )


def _request_event_data(
    settings: ServiceSettings,
    runtime: AnalysisRuntime,
    *,
    request: AnalyzeTextRequest | None,
    profile: ModelProfile | None,
    requested_features: tuple[FeatureName, ...],
    feature_results: tuple[FeatureResult, ...],
    outcome: AnalysisOutcome | None,
    result_status: OutcomeStatus,
    total_ms: float,
    error: ErrorDetail | None,
) -> RequestEventData:
    model = outcome.model if outcome is not None else None
    return RequestEventData.model_validate(
        {
            "level": "ERROR" if result_status == "failed" else "INFO",
            **({"language": request.language} if request is not None else {}),
            **({"model_profile": profile} if profile is not None else {}),
            **({"package": model.package} if model is not None else {}),
            **({"model_version": model.model_version} if model is not None else {}),
            **({"spacy_version": model.spacy_version} if model is not None else {}),
            "requested_features": requested_features,
            "feature_statuses": tuple(
                RequestFeatureStatus(
                    feature=item.feature,
                    status=item.status,
                    error_code=(
                        cast(FeatureErrorCode, item.error.code)
                        if item.error is not None
                        else None
                    ),
                )
                for item in feature_results
            ),
            "active_requests": runtime.active_requests,
            "max_concurrent_requests": settings.max_concurrent_requests,
            "model_load_ms": outcome.model_load_ms if outcome is not None else 0.0,
            "analysis_ms": outcome.analysis_ms if outcome is not None else 0.0,
            "total_ms": total_ms,
            "result_status": result_status,
            **({"error_code": error.code} if error is not None else {}),
        }
    )


def _operation(request: Request) -> OperationMetadata:
    operation = observe_request_operation(request)
    if operation is None:
        raise RuntimeError("Trace propagation is required for text analysis")
    return operation


async def _emit_request_event(
    emitter: EventEmitter,
    operation: OperationMetadata,
    data: RequestEventData,
) -> None:
    event_type = {
        "complete": "text-analysis.request.completed",
        "partial": "text-analysis.request.partial",
        "failed": "text-analysis.request.failed",
    }[data.result_status]
    await emitter.emit(operation, cast(EventType, event_type), data)


def _validation_error_code(error: ValidationError) -> ErrorCode:
    details = error.errors(
        include_input=False,
        include_context=False,
        include_url=False,
    )
    location = details[0]["loc"] if details else ()
    if location and location[0] == "model_profile":
        return "UNSUPPORTED_MODEL_PROFILE"
    if location and location[0] == "features" and details[0]["type"] == "literal_error":
        return "UNSUPPORTED_FEATURE"
    return "INVALID_REQUEST"


def _aggregate_status(features: tuple[FeatureResult, ...]) -> OutcomeStatus:
    complete = sum(item.status == "complete" for item in features)
    if complete == len(features):
        return "complete"
    return "failed" if complete == 0 else "partial"


def create_app(settings: ServiceSettings) -> FastAPI:
    """Create the hosted application without loading model weights."""
    emitter = EventEmitter(settings.logging)
    runtime: AnalysisRuntime

    async def report_pool_failure() -> None:
        await emitter.emit_runtime_failure(
            _service_event_data(
                settings,
                runtime,
                status="failed",
                level="ERROR",
                error_code="ANALYSIS_FAILED",
            )
        )

    runtime = AnalysisRuntime(settings, report_pool_failure)
    emitter.bind_failure(runtime.mark_logging_failed)
    router = APIRouter()

    async def request_error(
        request: Request,
        code: ErrorCode,
        *,
        parsed: AnalyzeTextRequest | None = None,
        profile: ModelProfile | None = None,
        features: tuple[FeatureName, ...] = (),
        started_at: float | None = None,
    ) -> Response:
        error = ErrorDetail.from_code(code)
        result = ErrorResult(error=error)
        total_ms = (
            time.monotonic()
            - (
                observe_request_started_at(request)
                if started_at is None
                else started_at
            )
        ) * 1000
        await _emit_request_event(
            emitter,
            _operation(request),
            _request_event_data(
                settings,
                runtime,
                request=parsed,
                profile=profile,
                requested_features=features,
                feature_results=(),
                outcome=None,
                result_status="failed",
                total_ms=total_ms,
                error=error,
            ),
        )
        return _json_response(result, error.http_status)

    @router.post(
        ANALYZE_TEXT_PATH,
        response_model=AnalysisResult,
        responses={
            403: {"model": ErrorResult},
            413: {"model": ErrorResult},
            422: {"model": AnalysisResult | ErrorResult},
            429: {"model": ErrorResult},
            500: {"model": ErrorResult},
            503: {"model": ErrorResult},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/AnalyzeTextRequest"
                        }
                    }
                },
            }
        },
    )
    async def run_ner_spacy(request: Request) -> Response:
        started_at = observe_request_started_at(request)
        if not settings.enabled:
            return await request_error(
                request,
                "SERVICE_DISABLED",
                started_at=started_at,
            )
        if runtime.status != "ready":
            return await request_error(
                request,
                "ANALYSIS_FAILED",
                started_at=started_at,
            )
        try:
            body = await read_request_body(request, settings.listener)
        except ClientDisconnectedError:
            raise asyncio.CancelledError from None
        except RequestBodyError as failure:
            code: ErrorCode = (
                "BODY_TOO_LARGE"
                if failure.code == "BODY_TOO_LARGE"
                else "INVALID_REQUEST"
            )
            return await request_error(
                request,
                code,
                started_at=started_at,
            )
        try:
            parsed = AnalyzeTextRequest.model_validate_json(body)
        except ValidationError as failure:
            return await request_error(
                request,
                _validation_error_code(failure),
                started_at=started_at,
            )
        finally:
            del body

        features = parsed.features or settings.resolve_default_features(parsed.language)
        if any(feature not in settings.allowed_features for feature in features):
            return await request_error(
                request,
                "UNSUPPORTED_FEATURE",
                parsed=parsed,
                features=features,
                started_at=started_at,
            )
        language_settings = settings.languages.select(parsed.language)
        if not language_settings.enabled:
            return await request_error(
                request,
                "LANGUAGE_UNAVAILABLE",
                parsed=parsed,
                features=features,
                started_at=started_at,
            )
        profile = parsed.model_profile or language_settings.default_profile
        if profile is None or profile not in language_settings.profiles:
            return await request_error(
                request,
                "UNSUPPORTED_MODEL_PROFILE",
                parsed=parsed,
                features=features,
                started_at=started_at,
            )
        command = AnalysisCommand(
            text=parsed.text,
            language=cast(EnabledLanguage, parsed.language),
            profile=profile,
            features=features,
        )
        try:
            completion = runtime.submit(command)
        except RuntimeAdmissionError as failure:
            return await request_error(
                request,
                failure.code,
                parsed=parsed,
                profile=profile,
                features=features,
                started_at=started_at,
            )
        outcome = await asyncio.shield(completion)
        if outcome.error is not None:
            result = ErrorResult(error=outcome.error)
            total_ms = (time.monotonic() - started_at) * 1000
            await _emit_request_event(
                emitter,
                _operation(request),
                _request_event_data(
                    settings,
                    runtime,
                    request=parsed,
                    profile=profile,
                    requested_features=features,
                    feature_results=(),
                    outcome=outcome,
                    result_status="failed",
                    total_ms=total_ms,
                    error=outcome.error,
                ),
            )
            return _json_response(
                result,
                outcome.error.http_status,
            )

        model = cast(ModelIdentity, outcome.model)
        status = _aggregate_status(outcome.features)
        result = AnalysisResult(
            status=status,
            language=cast(EnabledLanguage, parsed.language),
            model=model,
            features=outcome.features,
        )
        total_ms = (time.monotonic() - started_at) * 1000
        feature_error = next(
            (item.error for item in outcome.features if item.error is not None),
            None,
        )
        await _emit_request_event(
            emitter,
            _operation(request),
            _request_event_data(
                settings,
                runtime,
                request=parsed,
                profile=profile,
                requested_features=features,
                feature_results=outcome.features,
                outcome=outcome,
                result_status=status,
                total_ms=total_ms,
                error=feature_error,
            ),
        )
        return _json_response(result, 422 if status == "failed" else 200)

    async def refuse_analyze(request: Request, code: HostRefusalCode) -> Response:
        return await request_error(request, cast(ErrorCode, code))

    async def refuse_default(_request: Request, code: HostRefusalCode) -> Response:
        error = ErrorDetail.from_code(cast(ErrorCode, code))
        return _json_response(ErrorResult(error=error), error.http_status)

    async def observe_health() -> TextAnalysisHealth:
        return _observe_health(settings, runtime)

    component = ApiComponentRuntime[
        TextAnalysisHealth
    ](
        router=router,
        state=runtime,
        start=runtime.start,
        shutdown=runtime.shutdown,
        observe_health=observe_health,
        refuse_requests={ANALYZE_TEXT_PATH: refuse_analyze},
        default_refusal=refuse_default,
    )

    def render_health(
        _context: HostRequestContext,
        health: TextAnalysisHealth,
    ) -> RenderedHealth:
        return RenderedHealth(
            response=_json_response(
                health,
                200 if health.status == "ready" else 503,
            ),
            ready=health.status == "ready",
        )

    data = HostEventDataFactory[TextAnalysisHealth, ServiceEventData](
        started=lambda: _service_event_data(
            settings,
            runtime,
            status="starting" if settings.enabled else "disabled",
        ),
        ready=lambda health, _duration_ms: ServiceEventData(
            level="INFO",
            enabled=health.enabled,
            status="ready",
            active_requests=health.active_requests,
            max_concurrent_requests=health.max_concurrent_requests,
            pool_ready=health.pool_ready,
        ),
        stopped=lambda: _service_event_data(
            settings,
            runtime,
            status="stopped",
        ),
        failed=lambda failure: _service_event_data(
            settings,
            runtime,
            status="failed",
            level="ERROR",
            error_code=(
                "STARTUP_FAILED"
                if failure.phase == "startup"
                else "SHUTDOWN_FAILED"
            ),
        ),
    )

    async def emit_service_event(
        context: HostEventContext,
        event: ServiceEventData,
    ) -> None:
        if context.operation is None:
            raise RuntimeError("Text-analysis lifecycle events require trace context")
        event_type = {
            "starting": "text-analysis.service.started",
            "disabled": "text-analysis.service.started",
            "ready": "text-analysis.service.ready",
            "stopped": "text-analysis.service.stopped",
            "failed": "text-analysis.service.failed",
        }[event.status]
        await emitter.emit_service(
            context.operation,
            cast(EventType, event_type),
            event,
        )

    host_settings = HostSettings(
        title=APPLICATION_TITLE,
        schema_version=API_SCHEMA_VERSION,
        health_path=HEALTH_PATH,
        schema_path=SCHEMA_PATH,
        listener=HostListenerSettings(
            host=settings.listener.host,
            port=settings.listener.port,
            max_body_bytes=settings.listener.max_body_bytes,
            body_read_timeout_ms=settings.listener.body_read_timeout_ms,
        ),
        shutdown_timeout_ms=settings.listener.shutdown_timeout_ms,
        propagate_trace_context=True,
    )
    app = compose_api(
        host_settings,
        component,
        HealthRenderer(
            response_model=TextAnalysisHealth,
            render=render_health,
        ),
        HostEventSink(
            data=data,
            started=emit_service_event,
            ready=emit_service_event,
            stopped=emit_service_event,
            failed=emit_service_event,
            aclose=emitter.aclose,
        ),
    )
    app.state.text_analysis_events = emitter
    app.state.text_analysis_runtime = runtime
    original_openapi = app.openapi

    def openapi_schema() -> dict[str, object]:
        if app.openapi_schema is not None:
            return cast(dict[str, object], app.openapi_schema)
        schema = cast(dict[str, object], original_openapi())
        components = cast(
            dict[str, object],
            schema.setdefault("components", {}),
        )
        models = cast(
            dict[str, object],
            components.setdefault("schemas", {}),
        )
        request_schema = AnalyzeTextRequest.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        definitions = cast(
            dict[str, object],
            request_schema.pop("$defs", {}),
        )
        models.update(definitions)
        models["AnalyzeTextRequest"] = request_schema
        app.openapi_schema = schema
        return schema

    app.openapi = openapi_schema
    return app
