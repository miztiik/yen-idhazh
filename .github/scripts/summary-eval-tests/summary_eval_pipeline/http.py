"""How is one owned HTTP response bounded without redirects, proxies or retries?"""

import asyncio
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from .contracts import FailurePhase, ServiceName
from .failures import WorkflowError
from .settings import PipelineSettings


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
) -> tuple[int, Result]:
    timeout = httpx.Timeout(timeout_ms / 1000, connect=manual.http_connect_timeout_ms / 1000)
    try:
        async with asyncio.timeout(timeout_ms / 1000):
            async with client.stream(
                method,
                url,
                content=body,
                headers={"Content-Type": "application/json", "Accept-Encoding": "identity"},
                timeout=timeout,
                follow_redirects=False,
            ) as response:
                status = response.status_code
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise WorkflowError("RESPONSE_INVALID", phase, service, status)
                length = response.headers.get("content-length")
                if length is not None and (not length.isascii() or not length.isdecimal()):
                    raise WorkflowError("RESPONSE_INVALID", phase, service, status)
                if length is not None and int(length) > manual.max_response_bytes:
                    raise WorkflowError("RESPONSE_TOO_LARGE", phase, service, status)
                encoded = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(encoded) + len(chunk) > manual.max_response_bytes:
                        raise WorkflowError("RESPONSE_TOO_LARGE", phase, service, status)
                    encoded.extend(chunk)
                try:
                    result = contract.model_validate_json(encoded)
                except ValidationError:
                    raise WorkflowError("RESPONSE_INVALID", phase, service, status) from None
                return status, result
    except (httpx.HTTPError, TimeoutError):
        raise WorkflowError("HTTP_FAILED", phase, service) from None
