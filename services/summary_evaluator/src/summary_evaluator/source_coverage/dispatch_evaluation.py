"""How does the actual coverage HTTP boundary deliver only complete metrics or fixed safe errors?"""

import asyncio
from collections.abc import Callable

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from summary_evaluator.shared.contracts.diagnostic_data import LifecycleFields
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator.shared.disconnected_response import DisconnectedResponse
from summary_evaluator.shared.fail_runtime import RuntimeFailure
from summary_evaluator.shared.queue_evaluations import Reservation
from summary_evaluator.shared.read_request_body import (
    ClientDisconnected,
    read_request_body,
    wait_for_disconnect,
)
from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.evaluation_result import (
    CoverageMetrics,
    CoverageResult,
)
from summary_evaluator.source_coverage.control_evaluation import CoverageController
from summary_evaluator.source_coverage.fail_evaluation import CoverageFailure

RefusalRenderer = Callable[[str, str, int], Response]


async def dispatch_evaluation(
    request: Request,
    controller: CoverageController,
    render_refusal: RefusalRenderer,
    error: ErrorCode | None = None,
) -> Response:
    execution_id = create_execution_id()
    reservation: Reservation | None = None
    work: asyncio.Task[CoverageMetrics] | None = None
    disconnect: asyncio.Task[None] | None = None
    failure: CoverageFailure | None = None
    gone = False
    try:
        try:
            if error is not None:
                raise CoverageFailure(error)
            reservation = await controller.reserve(execution_id)
            encoded = await read_request_body(request, controller.settings.listener)
            try:
                parsed = CoverageRequest.model_validate_json(encoded)
            except ValidationError as invalid:
                details = invalid.errors(include_input=False, include_context=False)
                code: ErrorCode = (
                    "INVALID_JSON" if details[0]["type"] == "json_invalid" else "INVALID_REQUEST"
                )
                raise CoverageFailure(code) from None
            del encoded
            controller.diagnostic(
                LifecycleFields(action="started", level="INFO", execution_id=execution_id)
            )
            work = asyncio.create_task(controller.process(parsed, execution_id, reservation))
            disconnect = asyncio.create_task(wait_for_disconnect(request))
            done, _ = await asyncio.wait((work, disconnect), return_when=asyncio.FIRST_COMPLETED)
            if disconnect in done:
                gone = True
                work.cancel()
            metrics = await work
        except ClientDisconnected:
            gone = True
        except CoverageFailure as caught:
            failure = caught
        except RuntimeFailure as caught:
            failure = CoverageFailure(caught.code)
        except asyncio.CancelledError:
            if work is not None and not work.done():
                work.cancel()
                await asyncio.shield(asyncio.gather(work, return_exceptions=True))
            if not gone and (controller.stopping or controller.status == "failed"):
                failure = CoverageFailure("SERVICE_STOPPED")
            else:
                gone = True
        except Exception:
            failure = CoverageFailure("INTERNAL_ERROR")
            if reservation is not None and controller.queue.active is reservation:
                failure = await controller.stop_failed_request(failure.code)
        finally:
            if disconnect is not None:
                disconnect.cancel()
                await asyncio.gather(disconnect, return_exceptions=True)
        if gone:
            controller.diagnostic(
                LifecycleFields(
                    action="cancelled",
                    level="ERROR",
                    execution_id=execution_id,
                    code="CLIENT_DISCONNECTED",
                )
            )
            return DisconnectedResponse()
        try:
            controller.diagnostic(
                LifecycleFields(
                    action="failed" if failure else "completed",
                    level="ERROR" if failure else "INFO",
                    execution_id=execution_id,
                    code=failure.code if failure else None,
                )
            )
            if failure is not None and failure.cleanup_code is not None:
                controller.diagnostic(
                    LifecycleFields(
                        action="failed",
                        level="ERROR",
                        execution_id=execution_id,
                        code=failure.cleanup_code,
                    )
                )
        except RuntimeFailure as caught:
            failure = CoverageFailure(caught.code)
        if failure is not None:
            policy = ERROR_POLICIES[failure.code]
            response = render_refusal(failure.code, policy.message, policy.http_status or 500)
            if failure.code in ("QUEUE_FULL", "QUEUE_TIMEOUT"):
                response.headers["Retry-After"] = str(controller.settings.queue.retry_after_seconds)
            return response
        return JSONResponse(CoverageResult(metrics=metrics).model_dump(mode="json"))
    finally:
        if reservation is not None:
            controller.queue.release(reservation)
