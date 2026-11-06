"""How is one reserved HTTP body read within its byte and absolute time bounds?"""

import asyncio
from email.message import Message

from starlette.requests import ClientDisconnect, Request

from summary_evaluator.shared.contracts.service_settings import ListenerSettings
from summary_evaluator.shared.fail_runtime import RuntimeFailure


class ClientDisconnected(Exception):
    """Signal cancellation without constructing an HTTP response."""


async def read_request_body(request: Request, settings: ListenerSettings) -> bytes:
    media = Message()
    media["content-type"] = request.headers.get("content-type", "")
    if (
        len(request.headers.getlist("content-type")) != 1
        or len(request.headers.getlist("content-encoding")) > 1
        or media.get_content_type() != "application/json"
        or media.get_content_charset("utf-8").lower() != "utf-8"
        or request.headers.get("content-encoding", "identity").lower() != "identity"
    ):
        raise RuntimeFailure("UNSUPPORTED_MEDIA")
    length = request.headers.get("content-length")
    if length is not None:
        if (
            len(request.headers.getlist("content-length")) != 1
            or not length.isascii()
            or not length.isdecimal()
        ):
            raise RuntimeFailure("INVALID_REQUEST")
        normalized = length.lstrip("0") or "0"
        if (
            len(normalized) > len(str(settings.max_body_bytes))
            or int(normalized) > settings.max_body_bytes
        ):
            raise RuntimeFailure("BODY_TOO_LARGE")
    body = bytearray()
    try:
        async with asyncio.timeout(settings.body_read_timeout_ms / 1000):
            async for chunk in request.stream():
                if len(body) + len(chunk) > settings.max_body_bytes:
                    raise RuntimeFailure("BODY_TOO_LARGE")
                body.extend(chunk)
    except TimeoutError:
        raise RuntimeFailure("INPUT_TIMEOUT") from None
    except ClientDisconnect:
        raise ClientDisconnected from None
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeFailure("UNSUPPORTED_MEDIA") from None
    return bytes(body)


async def wait_for_disconnect(request: Request) -> None:
    """Wait on ASGI's explicit disconnect signal, not a polling interval."""
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return
