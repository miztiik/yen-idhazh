"""Which dated operations route prepared text and real coverage readiness?"""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, Response

from summary_evaluator.shared.contracts.api_paths import (
    COVERAGE_EVALUATE_PATH,
    COVERAGE_HEALTH_PATH,
)
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES
from summary_evaluator.source_coverage.contracts.evaluate_request import CoverageRequest
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageResult
from summary_evaluator.source_coverage.contracts.service_health import CoverageHealth
from summary_evaluator.source_coverage.control_evaluation import CoverageController
from summary_evaluator.source_coverage.dispatch_evaluation import (
    RefusalRenderer,
    dispatch_evaluation,
)


def create_coverage_router(
    controller: CoverageController,
    render_refusal: RefusalRenderer,
    refusal_schema: dict[str, object],
) -> APIRouter:
    router = APIRouter()
    responses = {
        str(policy.http_status): {
            "description": "Fixed safe coverage refusal",
            "content": {"application/json": {"schema": refusal_schema}},
        }
        for policy in ERROR_POLICIES.values()
        if policy.http_status is not None
    }
    responses["200"] = {
        "description": "Complete source-coverage metrics",
        "content": {"application/json": {"schema": CoverageResult.model_json_schema()}},
    }

    @router.post(
        COVERAGE_EVALUATE_PATH,
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": CoverageRequest.model_json_schema()}},
            },
            "responses": responses,
        },
    )
    async def evaluate(request: Request) -> Response:
        return await dispatch_evaluation(request, controller, render_refusal)

    @router.get(COVERAGE_HEALTH_PATH, response_model=CoverageHealth)
    async def health() -> JSONResponse:
        observed = await controller.health()
        return JSONResponse(
            observed.model_dump(mode="json"), status_code=200 if observed.status == "ready" else 503
        )

    return router
