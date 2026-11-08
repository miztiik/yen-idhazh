"""How is one real response carrier observed without changing the caller's operation?"""

from collections.abc import Callable
from typing import Literal

import httpx
from local_api_host.propagate_trace_context import OperationMetadata, read_trace_context
from starlette.datastructures import Headers

type ResponseTraceObservation = OperationMetadata | Literal["missing", "invalid"]
type ResponseTraceObserver = Callable[[ResponseTraceObservation], None]


def read_response_trace(headers: httpx.Headers) -> ResponseTraceObservation:
    invalid = False

    def mark_invalid() -> None:
        nonlocal invalid
        invalid = True

    operation = read_trace_context(Headers(raw=headers.raw), on_invalid=mark_invalid)
    if operation is not None:
        return operation
    return "invalid" if invalid else "missing"
