"""Which typed callbacks let one service use the host without leaking its vocabulary?"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from fastapi import APIRouter
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from local_api_host.propagate_trace_context import OperationMetadata

HealthT = TypeVar("HealthT")
EventT = TypeVar("EventT")
HostRefusalCode = Literal["HOST_FORBIDDEN", "ORIGIN_FORBIDDEN"]
RefusalHandler = Callable[[Request, HostRefusalCode], Awaitable[Response]]


class ComponentShutdownFailures(BaseException):
    """Report independent component cleanup failures without nesting them."""

    def __init__(self, failures: tuple[BaseException, ...]) -> None:
        super().__init__("Component shutdown failed")
        self.failures = failures


@dataclass(frozen=True, slots=True)
class HostEventContext:
    """Identify one host lifecycle event without owning its service data."""

    service_instance_id: str
    operation: OperationMetadata | None


@dataclass(frozen=True, slots=True)
class HostRequestContext(HostEventContext):
    """Expose one request's trace and monotonic start to service-owned renderers."""

    request_started_at: float


@dataclass(frozen=True, slots=True)
class RenderedHealth:
    """Return exact service HTTP output plus its independent readiness observation."""

    response: Response
    ready: bool


@dataclass(frozen=True, slots=True)
class HealthRenderer(Generic[HealthT]):
    """Keep the health schema and response construction service-owned."""

    response_model: type[BaseModel]
    render: Callable[[HostRequestContext, HealthT], RenderedHealth]


@dataclass(frozen=True, slots=True)
class HostFailure:
    """Name the host lifecycle phase without retaining an exception."""

    phase: Literal["startup", "shutdown"]


@dataclass(frozen=True, slots=True)
class HostEventDataFactory(Generic[HealthT, EventT]):
    """Build typed service data for lifecycle facts the host observes."""

    started: Callable[[], EventT]
    ready: Callable[[HealthT, float], EventT]
    stopped: Callable[[], EventT]
    failed: Callable[[HostFailure], EventT]


@dataclass(frozen=True, slots=True)
class HostEventSink(Generic[HealthT, EventT]):
    """Deliver service-owned lifecycle events through async-safe callbacks."""

    data: HostEventDataFactory[HealthT, EventT]
    started: Callable[[HostEventContext, EventT], Awaitable[None]]
    ready: Callable[[HostEventContext, EventT], Awaitable[None]]
    stopped: Callable[[HostEventContext, EventT], Awaitable[None]]
    failed: Callable[[HostEventContext, EventT], Awaitable[None]]
    aclose: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiComponentRuntime(Generic[HealthT]):
    """Bind one service component to neutral host lifecycle and request guards."""

    router: APIRouter
    state: object
    start: Callable[[], Awaitable[None]]
    shutdown: Callable[[], Awaitable[None]]
    observe_health: Callable[[], Awaitable[HealthT]]
    refuse_requests: Mapping[str, RefusalHandler]
    default_refusal: RefusalHandler | None = None
