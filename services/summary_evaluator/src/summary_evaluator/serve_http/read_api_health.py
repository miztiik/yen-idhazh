"""How is saved previous health validated before removing its disabled retired slot?"""

import json
from typing import Annotated

from pydantic import BeforeValidator, ValidationInfo

from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.contracts.previous_api_health import PreviousApiHealth


def resolve_saved_api_health(value: object, info: ValidationInfo) -> ApiHealth:
    if isinstance(value, ApiHealth):
        value = value.model_dump()
    contract = (
        PreviousApiHealth if isinstance(value, dict) and "coverage" in value else ApiHealth
    )
    observed = (
        contract.model_validate_json(json.dumps(value))
        if info.mode == "json"
        else contract.model_validate(value)
    )
    return (
        ApiHealth.model_validate(observed.model_dump(exclude={"coverage"}))
        if isinstance(observed, PreviousApiHealth)
        else observed
    )


ReadableApiHealth = Annotated[ApiHealth, BeforeValidator(resolve_saved_api_health)]
