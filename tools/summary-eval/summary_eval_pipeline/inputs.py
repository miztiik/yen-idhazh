"""How do source data and one model path enter from the bounded platform event?"""

import json
import os
from pathlib import Path

from pydantic import ValidationError
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.shared.contracts.base import NativeContract, NonblankText
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest

from .failures import WorkflowError
from .settings import PipelineSettings


class ManualInputs(NativeContract):
    source_text: NonblankText
    reference_summary_text: NonblankText
    models_file: str = ""


def read_manual_inputs(manual: PipelineSettings) -> ManualInputs:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise WorkflowError("INPUT_INVALID", "input")
    allowance = manual.max_input_bytes + manual.event_envelope_bytes
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
        inputs = ManualInputs.model_validate(event["inputs"])
        if len(inputs.model_dump_json().encode("utf-8")) > manual.max_input_bytes:
            raise WorkflowError("INPUT_TOO_LARGE", "input")
        return inputs
    except (ValueError, ValidationError, UnicodeError):
        raise WorkflowError("INPUT_INVALID", "input") from None


def encode_request(request: EvaluateRequest | UnievalRequest) -> bytes:
    return request.model_dump_json().encode("utf-8")
