"""How do evaluator failures adapt the neutral bounded request-body reader?"""

from typing import cast

from local_api_host.read_request_body import (
    ClientDisconnectedError as ClientDisconnected,
    RequestBodyError,
    read_request_body as read_host_request_body,
    wait_for_disconnect,
)
from starlette.requests import Request

from summary_evaluator.shared.contracts.error_policy import ErrorCode
from summary_evaluator.shared.contracts.service_settings import ListenerSettings
from summary_evaluator.shared.fail_runtime import RuntimeFailure

__all__ = ["ClientDisconnected", "read_request_body", "wait_for_disconnect"]


async def read_request_body(request: Request, settings: ListenerSettings) -> bytes:
    try:
        return await read_host_request_body(request, settings)
    except RequestBodyError as failure:
        raise RuntimeFailure(cast(ErrorCode, failure.code)) from None
