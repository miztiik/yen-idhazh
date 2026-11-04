"""How are browser origins and unexpected listener hosts refused before body reads?"""

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from .contracts.api_settings import ApiSettings
from .contracts.base import EVALUATE_PATH
from .contracts.error_detail import ErrorDetail
from .control_service import EvaluationController
from .dispatch_evaluation import dispatch_evaluation
from .forward_llama import llama_error


class GuardLocalRequests:
    """Apply the shared listener's authority without redirects or input echoes."""

    def __init__(
        self, app: ASGIApp, settings: ApiSettings, controller: EvaluationController | None
    ) -> None:
        self.app, self.settings, self.controller = app, settings, controller

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
            response = (
                await dispatch_evaluation(request, self.controller, error)
                if scope["path"] == EVALUATE_PATH and self.controller is not None
                else llama_error(error.code, error.message, 403)
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
