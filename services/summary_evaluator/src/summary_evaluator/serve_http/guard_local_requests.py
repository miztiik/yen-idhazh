"""How are browser origins and unexpected listener hosts refused before body reads?"""

from collections.abc import Mapping

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode
from summary_evaluator.shared.create_api_component import RefusalHandler


class GuardLocalRequests:
    """Apply the shared listener's authority without redirects or input echoes."""

    def __init__(
        self,
        app: ASGIApp,
        settings: ApiSettings,
        refuse_requests: Mapping[str, RefusalHandler],
    ) -> None:
        self.app, self.settings, self.refuse_requests = app, settings, refuse_requests

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        listener = self.settings.listener
        host = f"[{listener.host}]" if ":" in listener.host else listener.host
        code: ErrorCode | None = None
        if "origin" in request.headers:
            code = "ORIGIN_FORBIDDEN"
        elif len(request.headers.getlist("host")) != 1 or request.headers.get("host") not in (
            host,
            f"{host}:{listener.port}",
        ):
            code = "HOST_FORBIDDEN"
        if code is not None:
            refusal = self.refuse_requests.get(scope["path"])
            policy = ERROR_POLICIES[code]
            response = (
                await refusal(request, code)
                if refusal is not None
                else refuse_request(code, policy.message, 403)
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
