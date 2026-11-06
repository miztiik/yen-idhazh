"""Which native routes expose independent UniEval readiness and real four-score work?"""

from typing import Final

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from hhem_evaluator.contracts.unieval_request import UnievalRequest
from hhem_evaluator.contracts.unieval_result import UnievalHealth, UnievalResult
from hhem_evaluator.control_unieval import UnievalController
from hhem_evaluator.dispatch_unieval import dispatch_unieval
from hhem_evaluator.shared.contracts.api_paths import API_PREFIX

# These are native protocol paths, not operator destinations.
UNIEVAL_PATH: Final = f"{API_PREFIX}/evaluate-summary-unieval"
UNIEVAL_HEALTH_PATH: Final = f"{API_PREFIX}/get-unieval-health"


def create_unieval_router(controller: UnievalController) -> APIRouter:
    router = APIRouter()

    @router.get(UNIEVAL_HEALTH_PATH, response_model=UnievalHealth)
    async def health() -> JSONResponse:
        observed = await controller.health()
        return JSONResponse(
            observed.model_dump(mode="json"),
            status_code=200 if observed.status == "ready" else 503,
        )

    @router.post(
        UNIEVAL_PATH,
        response_model=UnievalResult,
        responses={
            status: {"model": UnievalResult}
            for status in (400, 403, 408, 413, 415, 429, 500, 503, 504)
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": UnievalRequest.model_json_schema()}},
            }
        },
    )
    async def evaluate(request: Request) -> Response:
        return await dispatch_unieval(request, controller)

    return router
