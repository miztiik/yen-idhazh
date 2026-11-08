"""How is one owned HTTP response bounded without redirects, proxies or retries?"""

import asyncio
import logging
from typing import Literal

import httpx
from local_api_host.propagate_trace_context import OperationMetadata, write_trace_context
from pydantic import BaseModel, ValidationError

from .contracts import FailurePhase, ServiceName
from .failures import WorkflowError
from .settings import PipelineSettings
from .trace_context import ResponseTraceObserver, read_response_trace


def loopback_url(host: Literal["127.0.0.1", "::1"], port: int) -> str:
    address = f"[{host}]" if ":" in host else host
    return f"http://{address}:{port}"


async def call_local_api[Result: BaseModel](
    client: httpx.AsyncClient,
    method: Literal["GET", "POST"],
    url: str,
    contract: type[Result],
    manual: PipelineSettings,
    timeout_ms: float,
    *,
    service: ServiceName,
    phase: FailurePhase,
    body: bytes | None = None,
    max_response_bytes: int | None = None,
    operation_metadata: OperationMetadata | None = None,
    observe_trace: ResponseTraceObserver | None = None,
) -> tuple[int, Result]:
    timeout = httpx.Timeout(timeout_ms / 1000, connect=manual.http_connect_timeout_ms / 1000)
    limit = manual.max_response_bytes if max_response_bytes is None else max_response_bytes
    headers = {"Content-Type": "application/json", "Accept-Encoding": "identity"}
    if operation_metadata is not None:
        headers.update(write_trace_context(operation_metadata))
    try:
        async with asyncio.timeout(timeout_ms / 1000):
            async with client.stream(
                method,
                url,
                content=body,
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
            ) as response:
                status = response.status_code
                if observe_trace is not None:
                    observation = read_response_trace(response.headers)
                    try:
                        observe_trace(observation)
                    except Exception:
                        # Optional callbacks cannot erase results; BaseException controls propagate.
                        logging.getLogger(__name__).warning(
                            '{"event":"scorer_trace_observation_failed"}'
                        )
                if 300 <= status < 400:
                    raise WorkflowError("HTTP_FAILED", phase, service, status)
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise WorkflowError("RESPONSE_INVALID", phase, service, status)
                length = response.headers.get("content-length")
                if length is not None and (not length.isascii() or not length.isdecimal()):
                    raise WorkflowError("RESPONSE_INVALID", phase, service, status)
                if length is not None and int(length) > limit:
                    raise WorkflowError("RESPONSE_TOO_LARGE", phase, service, status)
                encoded = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(encoded) + len(chunk) > limit:
                        raise WorkflowError("RESPONSE_TOO_LARGE", phase, service, status)
                    encoded.extend(chunk)
                try:
                    result = contract.model_validate_json(encoded)
                except ValidationError:
                    raise WorkflowError("RESPONSE_INVALID", phase, service, status) from None
                return status, result
    except (httpx.HTTPError, TimeoutError):
        raise WorkflowError("HTTP_FAILED", phase, service) from None
