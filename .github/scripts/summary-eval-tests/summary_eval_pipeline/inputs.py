"""How do source data and one model path enter from the bounded platform event?"""

import json
import os
from pathlib import Path

from hhem_evaluator.contracts.base import NativeContract, NonblankText
from hhem_evaluator.contracts.evaluate_request import EvaluateRequest
from hhem_evaluator.contracts.service_settings import ServiceSettings
from pydantic import ValidationError

from .failures import WorkflowError
from .settings import PipelineSettings


class ManualInputs(NativeContract):
    source_text: NonblankText
    models_file: str = ""


def read_manual_inputs(settings: ServiceSettings, manual: PipelineSettings) -> ManualInputs:
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
        return ManualInputs.model_validate(event["inputs"])
    except (ValueError, ValidationError, UnicodeError):
        raise WorkflowError("INPUT_INVALID", "input") from None


def encode_request(request: EvaluateRequest) -> bytes:
    return request.model_dump_json().encode("utf-8")
