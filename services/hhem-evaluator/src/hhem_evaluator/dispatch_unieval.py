"""How is a bounded UniEval HTTP request delivered without losing completed dimensions?"""

import asyncio

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .contracts.server_event import ApiDiagnosticData
from .contracts.unieval_contract import DIMENSIONS
from .contracts.unieval_error import POLICIES, UnievalError, UnievalErrorCode
from .contracts.unieval_request import UnievalRequest
from .control_unieval import UnievalController
from .dispatch_evaluation import DisconnectedResponse
from .fail_evaluation import EvaluationFailure
from .fail_unieval import UnievalFailure
from .queue_evaluations import Reservation
from .read_request_body import ClientDisconnected, read_request_body, wait_for_disconnect
from .reduce_unieval import UnievalState


async def dispatch_unieval(
    request: Request,
    controller: UnievalController,
    error: UnievalError | None = None,
) -> Response:
    state = UnievalState()
    reservation: Reservation | None = None
    work: asyncio.Task[None] | None = None
    disconnect: asyncio.Task[None] | None = None
    gone = False
    try:
        try:
            if error is not None:
                raise UnievalFailure(error)
            reservation = controller.reserve(state)
            encoded = await read_request_body(request, controller.settings.listener)
            try:
                state.set_request(UnievalRequest.model_validate_json(encoded))
            except ValidationError as invalid:
                details = invalid.errors(include_input=False, include_context=False)
                code: UnievalErrorCode = (
                    "INVALID_JSON" if details[0]["type"] == "json_invalid" else "INVALID_REQUEST"
                )
                raise UnievalFailure(UnievalError.from_code(code)) from None
            del encoded
            controller.writer.diagnostic(
                ApiDiagnosticData(
                    component="unieval",
                    action="started",
                    level="INFO",
                    execution_id=state.execution_id,
                )
            )
            work = asyncio.create_task(controller.process(state, reservation))
            disconnect = asyncio.create_task(wait_for_disconnect(request))
            done, _ = await asyncio.wait((work, disconnect), return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                gone = True
                work.cancel()
            await work
        except ClientDisconnected:
            gone = True
        except UnievalFailure as failure:
            state.errors.append(failure.error)
        except EvaluationFailure as failure:
            state.errors.append(UnievalError.from_code(failure.error.code))
        except asyncio.CancelledError:
            if work is not None and not work.done():
                work.cancel()
                await asyncio.shield(asyncio.gather(work, return_exceptions=True))
            if controller.stopping or controller.status == "failed":
                state.errors.append(UnievalError.from_code("SERVICE_STOPPED"))
            else:
                gone = True
        except Exception:
            state.errors.append(UnievalError.from_code("INTERNAL_ERROR"))
            if reservation is not None and controller.queue.active is reservation:
                try:
                    await controller.fail_worker()
                except UnievalFailure as cleanup:
                    state.errors.append(cleanup.error)
        finally:
            if disconnect is not None:
                disconnect.cancel()
                await asyncio.gather(disconnect, return_exceptions=True)
        if gone:
            controller.writer.diagnostic(
                ApiDiagnosticData(
                    component="unieval",
                    action="cancelled",
                    level="ERROR",
                    execution_id=state.execution_id,
                    code=state.errors[0].code if state.errors else "CLIENT_DISCONNECTED",
                )
            )
            return DisconnectedResponse()
        if not state.errors and not any(
            getattr(state.scores, field) is not None for field in DIMENSIONS
        ):
            state.errors.append(UnievalError.from_code("INTERNAL_ERROR"))
        try:
            controller.writer.diagnostic(
                ApiDiagnosticData(
                    component="unieval",
                    action="failed" if state.errors else "completed",
                    level="ERROR" if state.errors else "INFO",
                    execution_id=state.execution_id,
                    code=state.errors[0].code if state.errors else None,
                )
            )
        except EvaluationFailure as failure:
            state.errors.append(UnievalError.from_code(failure.error.code))
        result = state.result()
        status = POLICIES[result.errors[0].code].http_status if result.errors else 200
        headers = (
            {"Retry-After": str(controller.settings.queue.retry_after_seconds)}
            if any(error.code in ("QUEUE_FULL", "QUEUE_TIMEOUT") for error in result.errors)
            else None
        )
        return JSONResponse(
            result.model_dump(mode="json"), status_code=status or 500, headers=headers
        )
    finally:
        if reservation is not None:
            controller.queue.release(reservation)
        state.request = None
