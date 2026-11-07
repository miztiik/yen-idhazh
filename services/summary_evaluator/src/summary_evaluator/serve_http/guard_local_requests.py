"""How are browser origins and unexpected listener hosts refused before body reads?"""

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.control_service import EvaluationController
from summary_evaluator.hhem.dispatch_evaluation import dispatch_evaluation
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.api_paths import COVERAGE_EVALUATE_PATH, EVALUATE_PATH
from summary_evaluator.source_coverage.control_evaluation import CoverageController
from summary_evaluator.source_coverage.dispatch_evaluation import (
    dispatch_evaluation as dispatch_coverage,
)
from summary_evaluator.unieval.contracts.unieval_error import UnievalError
from summary_evaluator.unieval.control_unieval import UnievalController
from summary_evaluator.unieval.dispatch_unieval import dispatch_unieval
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH


class GuardLocalRequests:
    """Apply the shared listener's authority without redirects or input echoes."""

    def __init__(
        self,
        app: ASGIApp,
        settings: ApiSettings,
        controller: EvaluationController | None,
        unieval: UnievalController | None = None,
        coverage: CoverageController | None = None,
    ) -> None:
        self.app, self.settings, self.controller = app, settings, controller
        self.unieval = unieval
        self.coverage = coverage

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        listener = self.settings.listener
        host = f"[{listener.host}]" if ":" in listener.host else listener.host
        error = None
        if "origin" in request.headers:
            error = ErrorDetail.from_code("ORIGIN_FORBIDDEN", "request")
        elif len(request.headers.getlist("host")) != 1 or request.headers.get("host") not in (
            host,
            f"{host}:{listener.port}",
        ):
            error = ErrorDetail.from_code("HOST_FORBIDDEN", "request")
        if error is not None:
            if scope["path"] == COVERAGE_EVALUATE_PATH and self.coverage is not None:
                response = await dispatch_coverage(
                    request, self.coverage, refuse_request, error.code
                )
                await response(scope, receive, send)
                return
            if scope["path"] == UNIEVAL_PATH and self.unieval is not None:
                response = await dispatch_unieval(
                    request, self.unieval, UnievalError.from_code(error.code)
                )
                await response(scope, receive, send)
                return
            response = (
                await dispatch_evaluation(request, self.controller, error)
                if scope["path"] == EVALUATE_PATH and self.controller is not None
                else refuse_request(error.code, error.message, 403)
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
