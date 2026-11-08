"""How are browser origins and unexpected listener hosts refused before body reads?"""

from collections.abc import Mapping

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from local_api_host.contracts import HostSettings
from local_api_host.create_api_component import (
    HostRefusalCode,
    RefusalHandler,
)


class GuardRequests:
    """Apply one loopback listener's authority without redirects or input echoes."""

    def __init__(
        self,
        app: ASGIApp,
        settings: HostSettings,
        refuse_requests: Mapping[str, RefusalHandler],
        default_refusal: RefusalHandler,
    ) -> None:
        self.app = app
        self.settings = settings
        self.refuse_requests = refuse_requests
        self.default_refusal = default_refusal

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        listener = self.settings.listener
        host = f"[{listener.host}]" if ":" in listener.host else listener.host
        code: HostRefusalCode | None = None
        if "origin" in request.headers:
            code = "ORIGIN_FORBIDDEN"
        elif len(request.headers.getlist("host")) != 1 or request.headers.get("host") not in (
            host,
            f"{host}:{listener.port}",
        ):
            code = "HOST_FORBIDDEN"
        if code is not None:
            refusal = self.refuse_requests.get(scope["path"], self.default_refusal)
            response = await refusal(request, code)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
