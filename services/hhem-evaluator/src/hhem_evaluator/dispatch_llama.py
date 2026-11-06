"""How is one native generation request admitted, validated and cancelled safely?"""

import asyncio
import time

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from .contracts.error_detail import ERROR_POLICIES
from .contracts.llama_request import LlamaRequest
from .contracts.server_event import ApiDiagnosticData
from .dispatch_evaluation import DisconnectedResponse
from .fail_evaluation import EvaluationFailure
from .forward_llama import LlamaForwarder
from .read_request_body import ClientDisconnected, read_request_body, wait_for_disconnect
from .refuse_request import refuse_request


async def dispatch_llama(request: Request, forwarder: LlamaForwarder) -> Response:
    async with forwarder.admission() as accepted:
        if not accepted:
            stopped = forwarder.stopping or forwarder.client is None
            code, status = ("SERVICE_STOPPED", 503) if stopped else ("QUEUE_FULL", 429)
            forwarder.warn(code, status)
            return refuse_request(code, "Native generation admission is unavailable.", status)
        work: asyncio.Task[Response] | None = None
        disconnect: asyncio.Task[None] | None = None
        started = time.monotonic()
        try:
            body = await read_request_body(request, forwarder.api.listener)
            try:
                LlamaRequest.model_validate_json(body)
            except ValidationError as error:
                invalid_json = error.errors(include_input=False)[0]["type"] == "json_invalid"
                code = "INVALID_JSON" if invalid_json else "INVALID_REQUEST"
                forwarder.warn(code, 400)
                return refuse_request(code, "Invalid native chat generation request.", 400)
            work = asyncio.create_task(forwarder.generate(body))
            del body
            disconnect = asyncio.create_task(wait_for_disconnect(request))
            done, _ = await asyncio.wait((work, disconnect), return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                raise ClientDisconnected
            return await work
        except EvaluationFailure as failure:
            policy = ERROR_POLICIES[failure.error.code]
            message = (
                "The request does not match the native chat contract."
                if failure.error.code == "INVALID_REQUEST"
                else policy.message
            )
            status = policy.http_status or 500
            forwarder.warn(failure.error.code, status)
            return refuse_request(failure.error.code, message, status)
        except (ClientDisconnected, asyncio.CancelledError):
            forwarder.writer.diagnostic(
                ApiDiagnosticData(
                    component="llama",
                    action="cancelled",
                    level="WARNING",
                    code="CLIENT_DISCONNECTED" if not forwarder.stopping else "SERVICE_STOPPED",
                    duration_ms=(time.monotonic() - started) * 1000,
                )
            )
            return DisconnectedResponse()
        finally:
            for task in (work, disconnect):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (work, disconnect) if task is not None),
                return_exceptions=True,
            )
