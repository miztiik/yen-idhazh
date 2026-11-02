"""How do the two texts reach a bounded request without another text-bearing file?"""

import json
import os
from pathlib import Path

from pydantic import ValidationError

from .contracts.evaluate_request import EvaluateRequest
from .contracts.service_settings import ServiceSettings
from .fail_manual_evaluation import WorkflowFailure
from .load_manual_settings import ManualSettings
from .resolve_ids import create_execution_id


def read_manual_inputs(settings: ServiceSettings, manual: ManualSettings) -> EvaluateRequest:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise WorkflowFailure("INPUT_INVALID", "input")
    allowance = settings.listener.max_body_bytes + manual.event_envelope_bytes
    try:
        with Path(event_path).open("rb") as stream:
            encoded = stream.read(allowance + 1)
    except OSError:
        raise WorkflowFailure("INPUT_INVALID", "input") from None
    if len(encoded) > allowance:
        raise WorkflowFailure("INPUT_TOO_LARGE", "input")
    try:
        event: object = json.loads(encoded)
        if not isinstance(event, dict) or not isinstance(event.get("inputs"), dict):
            raise WorkflowFailure("INPUT_INVALID", "input")
        inputs = event["inputs"]
        if set(inputs) != {"source_text", "summary_text"}:
            raise WorkflowFailure("INPUT_INVALID", "input")
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
        raise WorkflowFailure("INPUT_INVALID", "input") from None
    if len(encode_request(request)) > settings.listener.max_body_bytes:
        raise WorkflowFailure("INPUT_TOO_LARGE", "input")
    return request


def encode_request(request: EvaluateRequest) -> bytes:
    return request.model_dump_json().encode("utf-8")
