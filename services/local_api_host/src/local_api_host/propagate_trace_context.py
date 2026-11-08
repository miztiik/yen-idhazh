"""How does one local request retain valid W3C context and receive a fresh API span?"""

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from secrets import token_hex
from typing import Annotated, Final, Self, cast

from opentelemetry.context import Context
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
    get_current_span,
    set_span_in_context,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue, SkipJsonSchema
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_TRACE_PROPAGATOR = TraceContextTextMapPropagator()
OPERATION_METADATA_VERSION: Final = "2026-11-03"
W3C_TRACESTATE_MAX_BYTES: Final = 512


class _DiscardUnsafeTraceStateWarnings(logging.Filter):
    """Leave invalid-carrier reporting to the receiving operation's safe callback."""

    def filter(self, record: logging.LogRecord) -> bool:
        return False


logging.getLogger("opentelemetry.trace.span").addFilter(_DiscardUnsafeTraceStateWarnings())


class OperationLink(BaseModel):
    """Name one distinct operation related to the current operation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    trace_id: str = Field(alias="traceId", pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(alias="spanId", pattern=r"^[0-9a-f]{16}$")

    @model_validator(mode="after")
    def require_nonzero_identifiers(self) -> Self:
        if self.trace_id == "0" * 32 or self.span_id == "0" * 16:
            raise ValueError("Operation link identifiers must be nonzero")
        return self


def _normalize_json_links(value: object, info: ValidationInfo) -> object:
    """Keep decoded JSON arrays as the immutable native link sequence."""
    return tuple(value) if info.mode == "json" and isinstance(value, list) else value


def _omit_default(schema: JsonSchemaValue) -> None:
    """Do not advertise the internal omission marker as a wire default."""
    schema.pop("default", None)


class OperationMetadata(BaseModel):
    """Carry one W3C operation, its parent, links and canonical trace state."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        json_schema_extra={
            "version": OPERATION_METADATA_VERSION,
            "changelog": [
                {
                    "version": OPERATION_METADATA_VERSION,
                    "change": (
                        "Declare native execution, operation, parent and input-link metadata."
                    ),
                }
            ],
        },
    )

    trace_id: str = Field(alias="traceId", pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(alias="spanId", pattern=r"^[0-9a-f]{16}$")
    parent_span_id: (
        Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")] | SkipJsonSchema[None]
    ) = Field(
        default=None,
        alias="parentSpanId",
        json_schema_extra=_omit_default,
    )
    links: Annotated[tuple[OperationLink, ...], BeforeValidator(_normalize_json_links)]
    trace_state: Annotated[str, StringConstraints(min_length=1)] | SkipJsonSchema[None] = Field(
        default=None,
        alias="traceState",
        json_schema_extra=_omit_default,
    )

    @model_validator(mode="before")
    @classmethod
    def refuse_explicit_null_optional_fields(cls, value: object) -> object:
        if isinstance(value, Mapping):
            optional_names = (
                "parentSpanId",
                "parent_span_id",
                "traceState",
                "trace_state",
            )
            if any(name in value and value[name] is None for name in optional_names):
                raise ValueError("Optional operation metadata must be omitted instead of null")
        return value

    @field_validator("trace_state")
    @classmethod
    def require_canonical_trace_state(cls, value: str | None) -> str | None:
        if value is not None and (
            len(value) > W3C_TRACESTATE_MAX_BYTES
            or TraceState.from_header([value]).to_header() != value
        ):
            raise ValueError("traceState must be canonical W3C tracestate")
        return value

    @model_validator(mode="after")
    def require_valid_relationships(self) -> Self:
        if self.trace_id == "0" * 32 or self.span_id == "0" * 16:
            raise ValueError("Operation identifiers must be nonzero")
        if self.parent_span_id == "0" * 16:
            raise ValueError("Operation parent identifier must be nonzero")
        if self.parent_span_id == self.span_id:
            raise ValueError("An operation cannot be its own parent")
        return self

    @model_serializer(mode="wrap")
    def serialize_without_nulls(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        serialized = cast(dict[str, object], handler(self))
        return {key: value for key, value in serialized.items() if value is not None}


type TraceWarningHandler = Callable[[Request, OperationMetadata], Awaitable[Response | None]]


def _create_nonzero_identifier(byte_length: int, excluded: str | None = None) -> str:
    zero = "0" * (byte_length * 2)
    while True:
        identifier = token_hex(byte_length)
        if identifier != zero and identifier != excluded:
            return identifier


def create_root_operation(
    *,
    links: tuple[OperationLink, ...] = (),
    trace_state: str | None = None,
) -> OperationMetadata:
    """Create one unsampled operation root."""
    trace_id = _create_nonzero_identifier(16)
    span_id = _create_nonzero_identifier(8)
    if trace_state is None:
        return OperationMetadata(trace_id=trace_id, span_id=span_id, links=links)
    return OperationMetadata(
        trace_id=trace_id,
        span_id=span_id,
        links=links,
        trace_state=trace_state,
    )


def create_child_operation(
    parent: OperationMetadata,
    *,
    links: tuple[OperationLink, ...] = (),
) -> OperationMetadata:
    """Create one fresh operation inside an existing trace."""
    span_id = _create_nonzero_identifier(8, parent.span_id)
    if parent.trace_state is None:
        return OperationMetadata(
            trace_id=parent.trace_id,
            span_id=span_id,
            parent_span_id=parent.span_id,
            links=links,
        )
    return OperationMetadata(
        trace_id=parent.trace_id,
        span_id=span_id,
        parent_span_id=parent.span_id,
        links=links,
        trace_state=parent.trace_state,
    )


def read_trace_context(
    headers: Headers,
    *,
    on_invalid: Callable[[], None] | None = None,
) -> OperationMetadata | None:
    """Read one valid incoming W3C operation without treating it as received work."""
    traceparents = headers.getlist("traceparent")
    if len(traceparents) != 1:
        if on_invalid is not None and (traceparents or headers.getlist("tracestate")):
            on_invalid()
        return None
    carrier: dict[str, str | list[str]] = {"traceparent": traceparents}
    tracestate = headers.getlist("tracestate")
    if tracestate:
        carrier["tracestate"] = tracestate
    incoming = get_current_span(
        _TRACE_PROPAGATOR.extract(carrier, context=Context())
    ).get_span_context()
    if not incoming.is_valid:
        if on_invalid is not None:
            on_invalid()
        return None
    canonical_state = incoming.trace_state.to_header()
    if len(canonical_state) > W3C_TRACESTATE_MAX_BYTES:
        canonical_state = ""
    if not canonical_state:
        if tracestate and on_invalid is not None:
            on_invalid()
        return OperationMetadata(
            trace_id=f"{incoming.trace_id:032x}",
            span_id=f"{incoming.span_id:016x}",
            links=(),
        )
    return OperationMetadata(
        trace_id=f"{incoming.trace_id:032x}",
        span_id=f"{incoming.span_id:016x}",
        links=(),
        trace_state=canonical_state,
    )


def create_request_operation(
    headers: Headers,
    *,
    on_invalid: Callable[[], None] | None = None,
) -> OperationMetadata:
    """Create the receiving operation for one optional incoming carrier."""
    parent = read_trace_context(headers, on_invalid=on_invalid)
    return create_root_operation() if parent is None else create_child_operation(parent)


def write_trace_context(operation: OperationMetadata) -> dict[str, str]:
    """Write the canonical unsampled W3C carrier for one API operation."""
    span_context = SpanContext(
        trace_id=int(operation.trace_id, 16),
        span_id=int(operation.span_id, 16),
        is_remote=False,
        trace_flags=TraceFlags(0),
        trace_state=(
            TraceState()
            if operation.trace_state is None
            else TraceState.from_header([operation.trace_state])
        ),
    )
    carrier: dict[str, str] = {}
    _TRACE_PROPAGATOR.inject(
        carrier,
        context=set_span_in_context(NonRecordingSpan(span_context), Context()),
    )
    return carrier


def observe_request_operation(request: Request) -> OperationMetadata | None:
    """Read the receiving operation selected before guards or body access."""
    operation = getattr(request.state, "operation_metadata", None)
    return operation if isinstance(operation, OperationMetadata) else None


def observe_request_started_at(request: Request) -> float:
    """Read the monotonic instant captured before request guards or body access."""
    started_at = getattr(request.state, "request_started_at", None)
    if not isinstance(started_at, float):
        raise RuntimeError("The local API host did not capture the request start")
    return started_at


class PropagateTraceContext:
    """Capture request timing and optionally write W3C context on every response."""

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool,
        *,
        invalid_trace_context: TraceWarningHandler | None = None,
    ) -> None:
        self.app = app
        self.enabled = enabled
        self.invalid_trace_context = invalid_trace_context

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        state["request_started_at"] = time.monotonic()
        state["invalid_trace_context"] = False

        def mark_invalid() -> None:
            state["invalid_trace_context"] = True

        operation = (
            create_request_operation(Headers(scope=scope), on_invalid=mark_invalid)
            if self.enabled
            else None
        )
        state["operation_metadata"] = operation

        async def send_with_trace(message: Message) -> None:
            if operation is not None and message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                carrier = write_trace_context(operation)
                headers["traceparent"] = carrier["traceparent"]
                if "tracestate" in carrier:
                    headers["tracestate"] = carrier["tracestate"]
                elif "tracestate" in headers:
                    del headers["tracestate"]
            await send(message)

        if (
            state["invalid_trace_context"]
            and operation is not None
            and self.invalid_trace_context is not None
        ):
            refusal = await self.invalid_trace_context(Request(scope, receive), operation)
            if refusal is not None:
                await refusal(scope, receive, send_with_trace)
                return
        await self.app(scope, receive, send_with_trace)
