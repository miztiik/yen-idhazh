"""Which native HHEM routes use the existing owned scoring controller?"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.evaluation_result import EvaluationResult
from hhem_evaluator.contracts.service_health import ServiceHealth
from hhem_evaluator.control_service import EvaluationController
from hhem_evaluator.dispatch_evaluation import dispatch_evaluation
from hhem_evaluator.shared.contracts.api_paths import EVALUATE_PATH, HHEM_HEALTH_PATH


def create_hhem_router(controller: EvaluationController) -> APIRouter:
    router = APIRouter()

    @router.get(HHEM_HEALTH_PATH, response_model=ServiceHealth)
    async def health() -> JSONResponse:
        observed = controller.health()
        return JSONResponse(observed.model_dump(mode="json"), status_code=observed.http_status)

    @router.post(
        EVALUATE_PATH,
        response_model=EvaluationResult,
        responses={
            status: {"model": EvaluationResult}
            for status in (400, 403, 408, 413, 415, 429, 500, 503, 504)
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": EvaluateRequest.model_json_schema()}},
            }
        },
    )
    async def evaluate(request: Request) -> Response:
        return await dispatch_evaluation(request, controller)

    return router
