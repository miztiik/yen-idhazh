"""How is one reserved HTTP body read within its byte and absolute time bounds?"""

import asyncio
from email.message import Message
from typing import Literal, Protocol

from starlette.requests import ClientDisconnect, Request

BodyFailureCode = Literal[
    "UNSUPPORTED_MEDIA",
    "INVALID_REQUEST",
    "BODY_TOO_LARGE",
    "INPUT_TIMEOUT",
]


class RequestBodySettings(Protocol):
    """Provide only the two bounds body reading consumes."""

    @property
    def max_body_bytes(self) -> int: ...

    @property
    def body_read_timeout_ms(self) -> int: ...


class RequestBodyError(Exception):
    """Name a bounded read failure for the service adapter to render."""

    def __init__(self, code: BodyFailureCode) -> None:
        super().__init__(code)
        self.code = code


class ClientDisconnectedError(Exception):
    """Signal cancellation without constructing an HTTP response."""


async def read_request_body(request: Request, settings: RequestBodySettings) -> bytes:
    media = Message()
    media["content-type"] = request.headers.get("content-type", "")
    if (
        len(request.headers.getlist("content-type")) != 1
        or len(request.headers.getlist("content-encoding")) > 1
        or media.get_content_type() != "application/json"
        or media.get_content_charset("utf-8").lower() != "utf-8"
        or request.headers.get("content-encoding", "identity").lower() != "identity"
    ):
        raise RequestBodyError("UNSUPPORTED_MEDIA")
    length = request.headers.get("content-length")
    if length is not None:
        if (
            len(request.headers.getlist("content-length")) != 1
            or not length.isascii()
            or not length.isdecimal()
        ):
            raise RequestBodyError("INVALID_REQUEST")
        normalized = length.lstrip("0") or "0"
        if (
            len(normalized) > len(str(settings.max_body_bytes))
            or int(normalized) > settings.max_body_bytes
        ):
            raise RequestBodyError("BODY_TOO_LARGE")
    body = bytearray()
    try:
        async with asyncio.timeout(settings.body_read_timeout_ms / 1000):
            async for chunk in request.stream():
                if len(body) + len(chunk) > settings.max_body_bytes:
                    raise RequestBodyError("BODY_TOO_LARGE")
                body.extend(chunk)
    except TimeoutError:
        raise RequestBodyError("INPUT_TIMEOUT") from None
    except ClientDisconnect:
        raise ClientDisconnectedError from None
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        raise RequestBodyError("UNSUPPORTED_MEDIA") from None
    return bytes(body)


async def wait_for_disconnect(request: Request) -> None:
    """Wait on ASGI's explicit disconnect signal, not a polling interval."""
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return
