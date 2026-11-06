"""How is a reserved HTTP attempt validated, scored and terminalized exactly once?"""

import asyncio
import time

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail, project_request_error
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.contracts.evaluation_event import EventDetails
from summary_evaluator.hhem.control_service import EvaluationController
from summary_evaluator.hhem.emit_events import EventEmitter
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.hhem.plan_windows import plan_windows
from summary_evaluator.hhem.resolve_ids import resolve_ids
from summary_evaluator.hhem.resolve_request import RequestResolutionError, resolve_request
from summary_evaluator.hhem.score_windows import EvaluationState
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES
from summary_evaluator.shared.disconnected_response import DisconnectedResponse
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.shared.queue_evaluations import Reservation
from summary_evaluator.shared.read_request_body import (
    ClientDisconnected,
    read_request_body,
    wait_for_disconnect,
)


def new_attempt(controller: EvaluationController) -> EvaluationState:
    return EvaluationState(
        emitter=EventEmitter(controller.writer, controller.context, controller.settings.logging),
        received_at=time.monotonic(),
    )


def prepare_evaluation(
    state: EvaluationState, body: bytes, controller: EvaluationController
) -> None:
    try:
        request = EvaluateRequest.model_validate_json(body)
    except ValidationError as failure:
        errors = failure.errors(include_input=False, include_context=False, include_url=False)
        if errors[0]["type"] == "json_invalid":
            raise EvaluationFailure(ErrorDetail.from_code("INVALID_JSON", "request")) from None
        raise EvaluationFailure(project_request_error(failure)) from None
    ids = resolve_ids(request, state.emitter.execution_id)
    state.emitter.request_id, state.emitter.correlation_id = ids.request_id, ids.correlation_id
    try:
        effective = resolve_request(request, controller.settings)
    except RequestResolutionError as failure:
        raise EvaluationFailure(failure.error) from None
    state.request, state.effective = request, effective
    maximum = controller.settings.scoring.max_windows_per_comparison
    state.primary_plan = plan_windows(
        request.source_text, effective.chunk_words, effective.chunk_overlap_words, maximum
    )
    if effective.hhem_full:
        if request.full_source_text is None:
            raise EvaluationFailure(
                ErrorDetail.from_code("INVALID_REQUEST", "request", field="full_source_text")
            )
        state.full_plan = (
            state.primary_plan
            if request.source_text == request.full_source_text
            else plan_windows(
                request.full_source_text,
                effective.chunk_words,
                effective.chunk_overlap_words,
                maximum,
            )
        )


def result_response(
    controller: EvaluationController, state: EvaluationState, terminal: str | None
) -> JSONResponse:
    result = state.result(terminal)
    status = 200
    if state.errors:
        status = ERROR_POLICIES[state.errors[0].code].http_status or 500
        if any(error.code == "LOGGING_FAILED" for error in state.errors):
            status = 500
    headers = (
        {"Retry-After": str(controller.settings.queue.retry_after_seconds)}
        if any(error.code in ("QUEUE_FULL", "QUEUE_TIMEOUT") for error in state.errors)
        else None
    )
    return JSONResponse(result.model_dump(mode="json"), status_code=status, headers=headers)


async def cancel_work(
    controller: EvaluationController,
    state: EvaluationState,
    reservation: Reservation | None,
    work: asyncio.Task[None],
) -> None:
    active = reservation is not None and controller.queue.active is reservation
    was_done = work.done()
    if active and not state.recovery_started:
        controller.queue.ready = False
        controller.status = "stopping" if controller.stopping else "replacing"
    if not was_done and not work.cancelling():
        work.cancel()
    await asyncio.shield(asyncio.gather(work, return_exceptions=True))
    if active:
        await controller.recover(state)


async def dispatch_evaluation(
    request: Request, controller: EvaluationController, error: ErrorDetail | None = None
) -> Response:
    state = new_attempt(controller)
    reservation: Reservation | None = None
    work: asyncio.Task[None] | None = None
    disconnect: asyncio.Task[None] | None = None
    gone = False
    try:
        try:
            state.emitter.emit("request", "started", EventDetails())
            if error is not None:
                raise EvaluationFailure(error)
            reservation = controller.reserve(state)
            body = await read_request_body(request, controller.settings.listener)
            prepare_evaluation(state, body, controller)
            del body
            disconnect = asyncio.create_task(wait_for_disconnect(request))
            work = asyncio.create_task(controller.process(state, reservation))
            done, _ = await asyncio.wait((work, disconnect), return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                gone = True
                await cancel_work(controller, state, reservation, work)
                raise ClientDisconnected
            await work
        except ClientDisconnected:
            gone = True
        except EvaluationFailure as failure:
            state.errors.append(failure.error)
        except RuntimeFailure as failure:
            state.errors.append(ErrorDetail.from_code(failure.code, "request"))
        except asyncio.CancelledError:
            if work is not None:
                await cancel_work(controller, state, reservation, work)
            if controller.stopping:
                state.errors.append(ErrorDetail.from_code("SERVICE_STOPPED", "request"))
            else:
                gone = True
        except Exception:
            state.errors.append(ErrorDetail.from_code("INTERNAL_ERROR", "request"))
            if reservation is not None and controller.queue.active is reservation:
                await controller.recover(state)
        finally:
            if disconnect is not None:
                disconnect.cancel()
                await asyncio.gather(disconnect, return_exceptions=True)
        terminal = controller.terminal(state, disconnected=gone)
        if terminal is None and reservation is not None and controller.queue.active is reservation:
            await controller.recover(state)
        if gone:
            return DisconnectedResponse()
        return result_response(controller, state, terminal)
    finally:
        if reservation is not None:
            controller.queue.release(reservation)
        state.forget_text()
