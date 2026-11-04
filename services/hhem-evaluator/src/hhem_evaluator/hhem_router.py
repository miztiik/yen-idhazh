"""Which native HHEM routes use the existing owned scoring controller?"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .contracts.base import API_PREFIX, EVALUATE_PATH
from .contracts.evaluate_request import EvaluateRequest
from .contracts.evaluation_result import EvaluationResult
from .contracts.service_health import ServiceHealth
from .control_service import EvaluationController
from .dispatch_evaluation import dispatch_evaluation


def create_hhem_router(controller: EvaluationController) -> APIRouter:
    router = APIRouter()

    @router.get(f"{API_PREFIX}/health", response_model=ServiceHealth)
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
