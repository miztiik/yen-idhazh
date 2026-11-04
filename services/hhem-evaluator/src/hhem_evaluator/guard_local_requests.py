"""How are browser origins and unexpected listener hosts refused before body reads?"""

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from .contracts.api_settings import ApiSettings
from .contracts.base import EVALUATE_PATH
from .contracts.error_detail import ErrorDetail
from .contracts.unieval_error import UnievalError
from .control_service import EvaluationController
from .control_unieval import UnievalController
from .dispatch_evaluation import dispatch_evaluation
from .dispatch_unieval import dispatch_unieval
from .forward_llama import llama_error
from .unieval_router import UNIEVAL_PATH


class GuardLocalRequests:
    """Apply the shared listener's authority without redirects or input echoes."""

    def __init__(
        self,
        app: ASGIApp,
        settings: ApiSettings,
        controller: EvaluationController | None,
        unieval: UnievalController | None = None,
    ) -> None:
        self.app, self.settings, self.controller = app, settings, controller
        self.unieval = unieval

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
            if scope["path"] == UNIEVAL_PATH and self.unieval is not None:
                response = await dispatch_unieval(
                    request, self.unieval, UnievalError.from_code(error.code)
                )
                await response(scope, receive, send)
                return
            response = (
                await dispatch_evaluation(request, self.controller, error)
                if scope["path"] == EVALUATE_PATH and self.controller is not None
                else llama_error(error.code, error.message, 403)
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
