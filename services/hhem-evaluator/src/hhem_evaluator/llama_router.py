"""Which single native generation route does the shared application register?"""

from fastapi import APIRouter, FastAPI
from starlette.requests import Request
from starlette.responses import Response

from .contracts.llama_request import LlamaRequest
from .contracts.llama_result import LlamaErrorResult, LlamaResult
from .dispatch_llama import dispatch_llama
from .forward_llama import LLAMA_COMPLETIONS_PATH, LlamaForwarder


def create_llama_router(forwarder: LlamaForwarder) -> APIRouter:
    router = APIRouter()
    request_schema = LlamaRequest.model_json_schema(ref_template="#/components/schemas/{model}")
    request_schema.pop("$defs", None)

    @router.post(
        LLAMA_COMPLETIONS_PATH,
        response_model=LlamaResult,
        responses={
            status: {"model": LlamaErrorResult}
            for status in (400, 403, 408, 413, 415, 429, 500, 502, 503, 504)
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": request_schema}},
            }
        },
    )
    async def generate(request: Request) -> Response:
        return await dispatch_llama(request, forwarder)

    return router


def declare_llama_request_schema(app: FastAPI) -> None:
    """Keep nested request references valid without letting FastAPI read input early."""
    native = LlamaRequest.model_json_schema(ref_template="#/components/schemas/{model}")
    schema = app.openapi()
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for name, definition in native.get("$defs", {}).items():
        if name in components and components[name] != definition:
            raise ValueError("A native request schema conflicts with an API component")
        components[name] = definition
