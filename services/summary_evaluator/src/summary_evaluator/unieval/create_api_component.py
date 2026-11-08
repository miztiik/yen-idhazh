"""How does UniEval bind its native controller, routes and lifecycle to an HTTP host?"""

from collections.abc import Callable
from pathlib import Path

from local_api_host.propagate_trace_context import OperationMetadata, create_child_operation
from starlette.requests import Request
from starlette.responses import Response

from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings
from summary_evaluator.shared.create_api_component import (
    ApiComponentRuntime,
    ComponentContext,
    ComponentHealth,
    observe_worker_exit,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.control_unieval import UnievalController
from summary_evaluator.unieval.dispatch_unieval import dispatch_unieval
from summary_evaluator.unieval.load_unieval_settings import load_unieval_settings
from summary_evaluator.unieval.maintain_unieval_worker import UnievalSupervisor
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH, create_unieval_router


def load_component_settings(
    root: Path,
    listener: ListenerSettings,
    logging: LoggingSettings,
    shutdown_timeout_ms: int,
) -> UnievalSettings:
    settings = load_unieval_settings(root, listener, logging)
    if settings.worker.shutdown_timeout_ms > shutdown_timeout_ms:
        raise ValueError("The shared shutdown wait is shorter than the UniEval worker wait")
    return settings


def create_api_component(
    host: ComponentContext,
    *,
    settings: UnievalSettings | None = None,
    supervisor: UnievalSupervisor | None = None,
    writer: Callable[[LifecycleFields, OperationMetadata], None],
) -> ApiComponentRuntime:
    selected = settings or load_component_settings(
        host.root, host.listener, host.logging, host.shutdown_timeout_ms
    )
    if (
        selected.listener != host.listener
        or selected.logging != host.logging
        or selected.worker.shutdown_timeout_ms > host.shutdown_timeout_ms
    ):
        raise ValueError("UniEval must use the shared listener, logging and shutdown bounds")
    controller = UnievalController(
        selected,
        host.root,
        writer,
        host.service_instance_id,
        supervisor=supervisor,
        service_operation=create_child_operation(host.service_operation),
        propagate_trace_context=host.propagate_trace_context,
    )

    async def observe_health() -> ComponentHealth:
        observed = await controller.health()
        return ComponentHealth(observed.status, observed)

    async def refuse_forbidden(request: Request, code: ErrorCode) -> Response:
        return await dispatch_unieval(request, controller, UnievalError.from_code(code))

    return ApiComponentRuntime(
        router=create_unieval_router(controller),
        state=controller,
        start=controller.start,
        shutdown=controller.shutdown,
        observe_health=observe_health,
        refuse_requests={UNIEVAL_PATH: refuse_forbidden},
        worker_settings=selected.worker,
        is_stopping=lambda: controller.stopping,
        observe_exit=lambda: observe_worker_exit(controller.worker),
        refuse_failure=refuse_forbidden,
    )
