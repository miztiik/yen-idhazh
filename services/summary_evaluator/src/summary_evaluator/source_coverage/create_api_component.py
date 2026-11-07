"""How does coverage bind its native controller, routes and lifecycle to an HTTP host?"""

from collections.abc import Callable
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response

from summary_evaluator.shared.contracts.api_paths import COVERAGE_EVALUATE_PATH
from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings
from summary_evaluator.shared.create_api_component import (
    ApiComponentRuntime,
    ComponentContext,
    ComponentHealth,
)
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.control_evaluation import CoverageController
from summary_evaluator.source_coverage.coverage_router import create_coverage_router
from summary_evaluator.source_coverage.dispatch_evaluation import (
    RefusalRenderer,
    dispatch_evaluation,
)
from summary_evaluator.source_coverage.load_settings import load_settings
from summary_evaluator.source_coverage.maintain_worker import CoverageSupervisor


def load_component_settings(
    root: Path,
    listener: ListenerSettings,
    logging: LoggingSettings,
    shutdown_timeout_ms: int,
) -> CoverageSettings:
    settings = load_settings(root, listener, logging)
    if settings.worker.shutdown_timeout_ms > shutdown_timeout_ms:
        raise ValueError("The shared shutdown wait is shorter than the coverage worker wait")
    return settings


def create_api_component(
    host: ComponentContext,
    *,
    settings: CoverageSettings | None = None,
    supervisor: CoverageSupervisor | None = None,
    writer: Callable[[LifecycleFields], None],
    render_refusal: RefusalRenderer,
    refusal_schema: dict[str, object],
) -> ApiComponentRuntime:
    selected = settings or load_component_settings(
        host.root, host.listener, host.logging, host.shutdown_timeout_ms
    )
    if (
        selected.listener != host.listener
        or selected.logging != host.logging
        or selected.worker.shutdown_timeout_ms > host.shutdown_timeout_ms
    ):
        raise ValueError("Coverage must use shared listener, logging and shutdown bounds")
    controller = CoverageController(
        selected, host.root, writer, host.service_instance_id, supervisor=supervisor
    )

    async def observe_health() -> ComponentHealth:
        observed = await controller.health()
        return ComponentHealth(observed.status, observed)

    async def refuse_forbidden(request: Request, code: ErrorCode) -> Response:
        return await dispatch_evaluation(request, controller, render_refusal, code)

    return ApiComponentRuntime(
        router=create_coverage_router(controller, render_refusal, refusal_schema),
        state=controller,
        start=controller.start,
        shutdown=controller.shutdown,
        observe_health=observe_health,
        refuse_requests={COVERAGE_EVALUATE_PATH: refuse_forbidden},
    )
