"""How is one declared local refusal rendered without echoing request input?"""

from starlette.responses import Response

from .contracts.api_error_detail import ApiErrorDetail, ApiErrorResult


def refuse_request(code: str, message: str, status: int) -> Response:
    result = ApiErrorResult(error=ApiErrorDetail(code=code, type="api_error", message=message))
    return Response(result.model_dump_json(), status_code=status, media_type="application/json")
