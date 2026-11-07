"""How can an HTTP host invoke a scorer without owning its native behavior?"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter
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

RefusalHandler = Callable[[Request, ErrorCode], Awaitable[Response]]


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
        return WorkerExit(
            pid=worker.last_exit[0], exit_code=worker.last_exit[1], confirmed=True
        )
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


@dataclass(frozen=True)
class ComponentHealth:
    """Retain a native health payload with its aggregate readiness observation."""

    status: ServiceStatus
    payload: BaseModel


@dataclass(frozen=True)
class ApiComponentRuntime:
    """Bind native operations and lifecycle without a generic scoring implementation."""

    router: APIRouter
    state: object
    start: Callable[[], Awaitable[None]]
    shutdown: Callable[[], Awaitable[None]]
    observe_health: Callable[[], Awaitable[ComponentHealth]]
    refuse_requests: Mapping[str, RefusalHandler]
    worker_settings: WorkerSettings
    is_stopping: Callable[[], bool]
    observe_exit: Callable[[], WorkerExit]
