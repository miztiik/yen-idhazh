"""How do the two texts reach a bounded request without another text-bearing file?"""

import json
import os
from pathlib import Path

from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.service_settings import ServiceSettings
from hhem_evaluator.resolve_ids import create_execution_id
from pydantic import ValidationError

from .failures import WorkflowError
from .settings import PipelineSettings


def read_manual_inputs(settings: ServiceSettings, manual: PipelineSettings) -> EvaluateRequest:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise WorkflowError("INPUT_INVALID", "input")
    allowance = settings.listener.max_body_bytes + manual.event_envelope_bytes
    try:
        with Path(event_path).open("rb") as stream:
            encoded = stream.read(allowance + 1)
    except OSError:
        raise WorkflowError("INPUT_INVALID", "input") from None
    if len(encoded) > allowance:
        raise WorkflowError("INPUT_TOO_LARGE", "input")
    try:
        event: object = json.loads(encoded)
        if not isinstance(event, dict) or not isinstance(event.get("inputs"), dict):
            raise WorkflowError("INPUT_INVALID", "input")
        inputs = event["inputs"]
        if set(inputs) != {"source_text", "summary_text"}:
            raise WorkflowError("INPUT_INVALID", "input")
        request = EvaluateRequest.model_validate(
            {
                "source_text": inputs["source_text"],
                "summary_text": inputs["summary_text"],
                "hhem_full": False,
                "request_id": create_execution_id(),
                "correlation_id": create_execution_id(),
            }
        )
    except (ValueError, ValidationError, UnicodeError):
        raise WorkflowError("INPUT_INVALID", "input") from None
    if len(encode_request(request)) > settings.listener.max_body_bytes:
        raise WorkflowError("INPUT_TOO_LARGE", "input")
    return request


def encode_request(request: EvaluateRequest) -> bytes:
    return request.model_dump_json().encode("utf-8")
