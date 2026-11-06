"""Which safe error shape can a local API refusal return without a scoring result?"""

from typing import Literal

from pydantic import StrictInt, StrictStr

from .server_contract import ServerContract


class ApiErrorDetail(ServerContract):
    """Declare local refusal facts without accepting an upstream error message."""

    code: StrictStr | StrictInt | None
    message: StrictStr
    type: Literal["api_error"]


class ApiErrorResult(ServerContract):
    """Keep non-scoring refusals separate from each scorer's native result."""

    error: ApiErrorDetail
