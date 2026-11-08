"""Where does the evaluator adapt its generic refusal body to the neutral guard?"""

from collections.abc import Mapping

from local_api_host.create_api_component import HostRefusalCode
from local_api_host.guard_requests import GuardRequests
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from summary_evaluator.serve_http.compose_api import create_host_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES
from summary_evaluator.shared.create_api_component import RefusalHandler


class GuardLocalRequests(GuardRequests):
    """Retain the evaluator's existing middleware construction surface."""

    def __init__(
        self,
        app: ASGIApp,
        settings: ApiSettings,
        refuse_requests: Mapping[str, RefusalHandler],
    ) -> None:
        async def default_refusal(
            _request: Request,
            code: HostRefusalCode,
        ) -> Response:
            policy = ERROR_POLICIES[code]
            return refuse_request(code, policy.message, 403)

        super().__init__(
            app,
            create_host_settings(settings),
            refuse_requests,
            default_refusal,
        )
