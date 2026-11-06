"""How does one owned HTTPX client forward only native chat generation?"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

import httpx
from pydantic import ValidationError
from starlette.responses import Response

from .contracts.api_settings import ApiSettings
from .contracts.llama_request import NativeLlamaObject
from .contracts.llama_result import LlamaErrorResult, LlamaHealth, LlamaResult
from .contracts.llama_settings import LlamaSettings
from .contracts.server_event import ApiDiagnosticData
from .emit_events import EventWriter
from .refuse_request import refuse_request

# These are native protocol paths, not caller-selected proxy destinations.
LLAMA_COMPLETIONS_PATH: Final = "/v1/chat/completions"
LLAMA_HEALTH_PATH: Final = "/health"


class NativeHealth(NativeLlamaObject):
    status: str


class NativeResponseTooLarge(ValueError):
    """Refuse an oversized reply without logging or retaining its body."""


async def read_native_body(response: httpx.Response, allowance: int) -> bytes:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        if len(body) + len(chunk) > allowance:
            raise NativeResponseTooLarge
        body.extend(chunk)
    return bytes(body)


class LlamaForwarder:
    """Own transport and request cancellation, not the native executable or its model."""

    def __init__(
        self,
        api: ApiSettings,
        selected: LlamaSettings,
        writer: EventWriter,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api, self.selected, self.writer = api, selected, writer
        self.transport = transport
        self.client: httpx.AsyncClient | None = None
        self.active: set[asyncio.Task[object]] = set()
        self.stopping = False
        self.last_health: str | None = None

    async def start(self) -> None:
        if self.client is not None or self.stopping:
            raise RuntimeError("The native client lifetime has already started")
        self.client = httpx.AsyncClient(
            base_url=self.selected.base_url,
            timeout=httpx.Timeout(
                self.selected.request_timeout_ms / 1000,
                connect=self.api.llama.connect_timeout_ms / 1000,
            ),
            trust_env=False,
            follow_redirects=False,
            transport=self.transport,
        )
        await self.client.__aenter__()

    async def close(self) -> None:
        self.stopping = True
        for task in tuple(self.active):
            task.cancel()
        deadline = time.monotonic() + self.api.shutdown_timeout_ms / 1000
        failures: list[BaseException] = []
        try:
            async with asyncio.timeout_at(deadline):
                if self.active:
                    await asyncio.gather(*tuple(self.active), return_exceptions=True)
        except BaseException as error:
            failures.append(error)
        if self.client is not None:
            try:
                async with asyncio.timeout_at(deadline):
                    await self.client.aclose()
            except BaseException as error:
                failures.append(error)
        if failures:
            if len(failures) == 1:
                raise failures[0]
            raise BaseExceptionGroup("Native client cleanup failed", failures)

    async def health(self) -> LlamaHealth:
        if self.stopping:
            return LlamaHealth(status="stopping", http_status=None, failure_code=None)
        client = self.client
        if client is None:
            return LlamaHealth(
                status="loading", http_status=None, failure_code="CLIENT_NOT_STARTED"
            )
        status: int | None = None
        failure: str | None = None
        observed = "failed"
        try:
            timeout = self.api.llama.health_timeout_ms / 1000
            async with (
                asyncio.timeout(timeout),
                client.stream("GET", LLAMA_HEALTH_PATH, timeout=timeout) as response,
            ):
                status = response.status_code
                body = await read_native_body(response, self.api.llama.max_response_bytes)
            if status == 200 and NativeHealth.model_validate_json(body).status == "ok":
                observed = "ready"
            elif status == 503:
                observed, failure = "loading", "UPSTREAM_NOT_READY"
            else:
                failure = "UPSTREAM_HEALTH_FAILED"
        except (TimeoutError, httpx.TimeoutException):
            failure = "UPSTREAM_TIMEOUT"
        except httpx.HTTPError:
            failure = "UPSTREAM_UNREACHABLE"
        except (ValidationError, NativeResponseTooLarge):
            failure = "INVALID_UPSTREAM_RESPONSE"
        if observed != self.last_health:
            self.writer.diagnostic(
                ApiDiagnosticData(
                    component="llama",
                    action="ready" if observed == "ready" else "unavailable",
                    level="INFO" if observed == "ready" else "WARNING",
                    code=failure,
                    http_status=status,
                )
            )
            self.last_health = observed
        return LlamaHealth.model_validate(
            {"status": observed, "http_status": status, "failure_code": failure}
        )

    @asynccontextmanager
    async def admission(self) -> AsyncIterator[bool]:
        task = asyncio.current_task()
        accepted = (
            task is not None
            and not self.stopping
            and self.client is not None
            and not self.client.is_closed
            and len(self.active) < self.api.llama.max_inflight_requests
        )
        if accepted and task is not None:
            self.active.add(task)
        try:
            yield accepted
        finally:
            if accepted and task is not None:
                self.active.discard(task)

    async def generate(self, body: bytes) -> Response:
        client = self.client
        if client is None:
            return refuse_request("SERVICE_STOPPED", "The native model client is not running.", 503)
        try:
            async with (
                asyncio.timeout(self.selected.request_timeout_ms / 1000),
                client.stream(
                    "POST",
                    LLAMA_COMPLETIONS_PATH,
                    content=body,
                    headers={"Content-Type": "application/json"},
                ) as response,
            ):
                status = response.status_code
                encoded = await read_native_body(response, self.api.llama.max_response_bytes)
            if 200 <= status < 300:
                LlamaResult.model_validate_json(encoded)
            elif 400 <= status < 600:
                LlamaErrorResult.model_validate_json(encoded)
                self.warn("UPSTREAM_HTTP_ERROR", status)
            else:
                self.warn("UPSTREAM_REDIRECT", status)
                return refuse_request("UPSTREAM_REDIRECT", "The native model redirected.", 502)
            return Response(encoded, status_code=status, media_type="application/json")
        except (TimeoutError, httpx.TimeoutException):
            code, message, status = "UPSTREAM_TIMEOUT", "The native model request timed out.", 504
        except httpx.HTTPError:
            code, message, status = (
                "UPSTREAM_UNREACHABLE",
                "The native model could not be reached.",
                502,
            )
        except NativeResponseTooLarge:
            code, message, status = (
                "UPSTREAM_BODY_TOO_LARGE",
                "The native model response is too large.",
                502,
            )
        except ValidationError:
            code, message, status = (
                "INVALID_UPSTREAM_RESPONSE",
                "The native model returned an invalid response.",
                502,
            )
        self.warn(code, status)
        return refuse_request(code, message, status)

    def warn(self, code: str, status: int | None = None) -> None:
        self.writer.diagnostic(
            ApiDiagnosticData(
                component="llama", action="failed", level="WARNING", code=code, http_status=status
            )
        )
