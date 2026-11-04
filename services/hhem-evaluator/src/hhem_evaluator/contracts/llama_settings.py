"""Which frozen private endpoint and declared deadline may the llama client use?"""

import ipaddress
from typing import Annotated, Self
from urllib.parse import urlsplit

from pydantic import Field, StrictStr, model_validator

from .server_contract import ServerContract


class LlamaSettings(ServerContract):
    """Accept an operator-controlled loopback origin, never a request-selected URL."""

    base_url: StrictStr
    request_timeout_ms: Annotated[float, Field(gt=0, allow_inf_nan=False)]

    @model_validator(mode="after")
    def require_private_origin(self) -> Self:
        try:
            parts = urlsplit(self.base_url)
            private = ipaddress.ip_address(parts.hostname or "").is_loopback
            valid = (
                parts.scheme == "http"
                and private
                and parts.port is not None
                and parts.port > 0
                and parts.username is None
                and parts.password is None
                and parts.path in ("", "/")
                and not parts.query
                and not parts.fragment
            )
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("model_server.base_url must name one private loopback HTTP origin")
        return self
