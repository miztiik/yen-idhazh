"""How does evaluator-specific worker state extend the neutral HTTP component?"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Protocol

from local_api_host.create_api_component import (
    ApiComponentRuntime as HostApiComponentRuntime,
)
from local_api_host.create_api_component import RefusalHandler
from local_api_host.propagate_trace_context import OperationMetadata
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from summary_evaluator.shared.contracts.base import ServiceStatus
from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.service_settings import (
    ListenerSettings,
    LoggingSettings,
    StartupContext,
    WorkerSettings,
)
from summary_evaluator.shared.contracts.worker_exit import WorkerExit

__all__ = [
    "ApiComponentRuntime",
    "ComponentContext",
    "ComponentHealth",
    "RefusalHandler",
    "observe_worker_exit",
]


class WorkerOwnership(Protocol):
    @property
    def process(self) -> BaseProcess | None: ...

    @property
    def exit_confirmed(self) -> bool: ...

    @property
    def last_exit(self) -> tuple[int, int] | None: ...


def observe_worker_exit(worker: WorkerOwnership) -> WorkerExit:
    if worker.exit_confirmed:
        if worker.last_exit is None:
            return WorkerExit(pid=None, exit_code=None, confirmed=None)
        return WorkerExit(pid=worker.last_exit[0], exit_code=worker.last_exit[1], confirmed=True)
    return WorkerExit(
        pid=worker.process.pid if worker.process is not None else None,
        exit_code=None,
        confirmed=False,
    )


@dataclass(frozen=True)
class ComponentContext:
    """Supply validated host settings and one invocation identity to enabled scorers."""

    root: Path
    listener: ListenerSettings
    logging: LoggingSettings
    shutdown_timeout_ms: int
    startup: StartupContext
    service_instance_id: str
    service_operation: OperationMetadata
    propagate_trace_context: bool


@dataclass(frozen=True)
class ComponentHealth:
    """Retain a native health payload with its aggregate readiness observation."""

    status: ServiceStatus
    payload: BaseModel


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiComponentRuntime(HostApiComponentRuntime[ComponentHealth]):
    """Add worker observations without teaching the host evaluator vocabulary."""

    worker_settings: WorkerSettings
    is_stopping: Callable[[], bool]
    observe_exit: Callable[[], WorkerExit]
    refuse_failure: Callable[[Request, ErrorCode], Awaitable[Response]]
