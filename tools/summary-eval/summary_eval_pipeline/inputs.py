"""How do exact texts and scorer/model controls enter from the bounded platform event?"""

import json
import os
from pathlib import Path

from pydantic import Field, StrictBool, ValidationError, field_validator
from pydantic.json_schema import SkipJsonSchema
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.shared.contracts.base import NativeContract, NonblankText
from summary_evaluator.shared.contracts.optional_fields import is_absent, omit_default
from summary_evaluator.unieval.contracts.unieval_contract import SourceMode
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest

from .contracts import text_sha256
from .failures import WorkflowError
from .settings import PipelineSettings


class ManualInputs(NativeContract):
    source_text: NonblankText
    reference_summary_text: NonblankText | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    evaluate_relevance: StrictBool = False
    consistency_source_mode: SourceMode | SkipJsonSchema[None] = Field(
        default=None, exclude_if=is_absent, json_schema_extra=omit_default
    )
    models_file: str = ""

    @field_validator("reference_summary_text", "consistency_source_mode")
    @classmethod
    def refuse_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit an unused input instead of supplying null")
        return value

    @property
    def reference_summary_sha256(self) -> str | None:
        return (
            text_sha256(self.reference_summary_text)
            if self.reference_summary_text is not None else None
        )


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
        supplied = dict(event["inputs"])
        if supplied.get("reference_summary_text") == "":
            del supplied["reference_summary_text"]
        if supplied.get("consistency_source_mode") == "":
            del supplied["consistency_source_mode"]
        if "evaluate_relevance" in supplied:
            boolean = supplied["evaluate_relevance"]
            if type(boolean) is bool:
                pass
            elif isinstance(boolean, str) and boolean in ("true", "false"):
                supplied["evaluate_relevance"] = boolean == "true"
            else:
                raise WorkflowError("INPUT_INVALID", "input")
        inputs = ManualInputs.model_validate(supplied)
        if len(inputs.model_dump_json().encode("utf-8")) > manual.max_input_bytes:
            raise WorkflowError("INPUT_TOO_LARGE", "input")
        return inputs
    except (ValueError, ValidationError, UnicodeError):
        raise WorkflowError("INPUT_INVALID", "input") from None


def encode_request(request: EvaluateRequest | UnievalRequest) -> bytes:
    return request.model_dump_json().encode("utf-8")
