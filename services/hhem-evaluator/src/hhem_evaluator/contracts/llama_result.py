"""Which native llama result or explicit failure can the forwarding route deliver?"""

from typing import Literal, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from .base import Count, NonblankText
from .evaluate_request import is_absent
from .llama_request import NativeLlamaObject
from .server_contract import ServerContract


class LlamaAnswer(NativeLlamaObject):
    """Retain answer and reasoning channels without extracting a final summary."""

    role: Literal["assistant"]
    content: StrictStr | None
    reasoning_content: StrictStr | None = Field(default=None, exclude_if=is_absent)


class LlamaChoice(NativeLlamaObject):
    """Preserve the native finish reason, including a truncated generation."""

    index: Count
    message: LlamaAnswer
    finish_reason: StrictStr | None


class LlamaResult(NativeLlamaObject):
    """Require a real chat result without removing native usage or timing fields."""

    object: Literal["chat.completion"]
    model: NonblankText
    choices: tuple[LlamaChoice, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_distinct_choices(self) -> Self:
        indices = [choice.index for choice in self.choices]
        if len(indices) != len(set(indices)):
            raise ValueError("choices must have distinct indices")
        return self


class LlamaError(NativeLlamaObject):
    """Read a native error body without promoting its message into diagnostics."""

    code: StrictStr | StrictInt | None
    message: StrictStr
    type: StrictStr


class LlamaErrorResult(NativeLlamaObject):
    """Use the native error shape for upstream failures and safe local refusals."""

    error: LlamaError


class LlamaHealth(ServerContract):
    """Report observed native health, not merely an open forwarding socket."""

    status: Literal["disabled", "loading", "ready", "stopping", "failed"]
    http_status: StrictInt | None
    failure_code: NonblankText | None

    @model_validator(mode="after")
    def require_observed_readiness(self) -> Self:
        if self.status == "ready" and (self.http_status != 200 or self.failure_code is not None):
            raise ValueError("Ready requires a successful native health observation")
        if self.status == "failed" and self.failure_code is None:
            raise ValueError("Failed health requires an explicit failure code")
        if self.status == "disabled" and (
            self.http_status is not None or self.failure_code is not None
        ):
            raise ValueError("Disabled health has no native observation")
        return self
