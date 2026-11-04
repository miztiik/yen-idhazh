"""Which native routes expose independent UniEval readiness and real four-score work?"""

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .contracts.base import API_PREFIX
from .contracts.unieval_request import UnievalRequest
from .contracts.unieval_result import UnievalHealth, UnievalResult
from .control_unieval import UnievalController
from .dispatch_unieval import dispatch_unieval

# These are native protocol paths, not operator destinations.
UNIEVAL_PATH = f"{API_PREFIX}/summary-eval-unieval"
UNIEVAL_HEALTH_PATH = f"{UNIEVAL_PATH}/health"


def create_unieval_router(controller: UnievalController) -> APIRouter:
    router = APIRouter()

    @router.get(UNIEVAL_HEALTH_PATH, response_model=UnievalHealth)
    async def health() -> JSONResponse:
        observed = controller.health()
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
