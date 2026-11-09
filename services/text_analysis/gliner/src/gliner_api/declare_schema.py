"""How are bounded-read request contracts included in native OpenAPI?"""

from typing import Any

from fastapi import FastAPI

from gliner_api.declare_analysis_contracts import AnalyzeTextRequest
from gliner_api.declare_api_contracts import HEALTH_PATH


def install_request_schemas(app: FastAPI) -> None:
    """Derive request schemas without letting FastAPI read an unbounded body."""
    original_openapi = app.openapi

    def openapi_schema() -> dict[str, Any]:
        schema = original_openapi()
        models = schema.setdefault("components", {}).setdefault("schemas", {})
        request_schema = AnalyzeTextRequest.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        models.update(request_schema.pop("$defs", {}))
        models[AnalyzeTextRequest.__name__] = request_schema
        health_responses = schema["paths"][HEALTH_PATH]["get"]["responses"]
        health_responses["503"] = {
            "description": "The configured provider is not ready.",
            "content": health_responses["200"]["content"],
        }
        app.openapi_schema = schema
        return schema

    # FastAPI's documented OpenAPI callback extension assigns its method.
    app.openapi = openapi_schema  # type: ignore[method-assign]
