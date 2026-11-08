"""How large can the actual service-load or model operation in a worker packet be?"""

from typing import Final

from local_api_host.propagate_trace_context import (
    W3C_TRACESTATE_MAX_BYTES,
    OperationLink,
    OperationMetadata,
)

W3C_TRACESTATE_VALUE_MAX_CHARS: Final = 256
# One load may link the failed active attempt; model commands have no input links.
WORKER_OPERATION_LINK_LIMIT: Final = 1


def validate_worker_operation_metadata(operation: OperationMetadata) -> OperationMetadata:
    """Keep the native worker's one failed-attempt link within its declared packet bound."""
    if len(operation.links) > WORKER_OPERATION_LINK_LIMIT:
        raise ValueError("Worker operations may link only the failed active attempt")
    return operation


def maximum_worker_operation_metadata() -> OperationMetadata:
    """Serialize the W3C state limit with the greatest JSON escaping and one recovery link."""
    first = "a=" + "\\" * W3C_TRACESTATE_VALUE_MAX_CHARS
    separator = ",b="
    state = first + separator + "\\" * (W3C_TRACESTATE_MAX_BYTES - len(first) - len(separator))
    return OperationMetadata(
        trace_id="f" * 32,
        span_id="f" * 16,
        parent_span_id="e" * 16,
        links=(OperationLink(trace_id="e" * 32, span_id="e" * 16),),
        trace_state=state,
    )
