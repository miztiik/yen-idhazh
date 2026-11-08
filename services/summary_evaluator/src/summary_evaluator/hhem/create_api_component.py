"""How does HHEM bind its native controller, routes and lifecycle to an HTTP host?"""

from collections.abc import Callable

from local_api_host.propagate_trace_context import OperationMetadata, create_child_operation
from starlette.requests import Request
from starlette.responses import Response

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.evaluation_event import EvaluationEvent
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.control_service import EvaluationController
from summary_evaluator.hhem.dispatch_evaluation import dispatch_evaluation
from summary_evaluator.hhem.hhem_router import create_hhem_router
from summary_evaluator.hhem.maintain_worker import WorkerSupervisor
from summary_evaluator.shared.contracts.api_paths import EVALUATE_PATH
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.create_api_component import (
    ApiComponentRuntime,
    ComponentContext,
    ComponentHealth,
    observe_worker_exit,
)


def create_api_component(
    host: ComponentContext,
    settings: ServiceSettings | None,
    *,
    supervisor: WorkerSupervisor | None = None,
    writer: Callable[[EvaluationEvent, OperationMetadata], None],
) -> ApiComponentRuntime:
    if settings is None:
        raise ValueError("Enabled HHEM requires its named scoring settings")
    if (
        not settings.enabled
        or settings.listener != host.listener
        or settings.logging != host.logging
    ):
        raise ValueError("The HHEM snapshot must use shared route, listener and logging settings")
    if host.shutdown_timeout_ms < settings.worker.shutdown_timeout_ms:
        raise ValueError("The API shutdown wait must accommodate the HHEM shutdown wait")
    controller = EvaluationController(
        settings,
        host.startup,
        host.root,
        supervisor=supervisor,
        writer=writer,
        service_instance_id=host.service_instance_id,
        service_operation=create_child_operation(host.service_operation),
        propagate_trace_context=host.propagate_trace_context,
    )

    async def observe_health() -> ComponentHealth:
        observed = controller.health()
        return ComponentHealth(observed.status, observed)

    async def refuse_forbidden(request: Request, code: ErrorCode) -> Response:
        return await dispatch_evaluation(
            request, controller, ErrorDetail.from_code(code, "request")
        )

    return ApiComponentRuntime(
        router=create_hhem_router(controller),
        state=controller,
        start=controller.start,
        shutdown=controller.shutdown,
        observe_health=observe_health,
        refuse_requests={EVALUATE_PATH: refuse_forbidden},
        worker_settings=settings.worker,
        is_stopping=lambda: controller.stopping,
        observe_exit=lambda: observe_worker_exit(controller.worker),
        refuse_failure=refuse_forbidden,
    )
