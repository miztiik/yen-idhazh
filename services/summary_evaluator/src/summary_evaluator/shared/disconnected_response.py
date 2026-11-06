"""How does a disconnected caller avoid another response write?"""

from starlette.responses import Response
from starlette.types import Receive, Scope, Send


class DisconnectedResponse(Response):
    """Send no HTTP status or body after an observed ASGI disconnect."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        return
