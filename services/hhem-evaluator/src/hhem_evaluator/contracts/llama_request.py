"""Which native nonstreaming text request may reach the fixed llama operation?"""

import math
from typing import Annotated, Literal

from pydantic import AfterValidator, ConfigDict, Field, JsonValue, field_validator

from .base import NonblankText
from .server_contract import ServerContract


def require_finite_json(value: JsonValue) -> JsonValue:
    """Reject non-JSON numbers at every extension depth without changing valid values."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Native JSON numbers must be finite")
    if isinstance(value, dict):
        for item in value.values():
            require_finite_json(item)
    elif isinstance(value, list):
        for item in value:
            require_finite_json(item)
    return value


FiniteJsonValue = Annotated[JsonValue, AfterValidator(require_finite_json)]


class NativeLlamaObject(ServerContract):
    """Preserve native JSON extension fields rather than translate model parameters."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, FiniteJsonValue] = Field(init=False)


class LlamaMessage(ServerContract):
    """Keep supplied text in its existing chat role without rewriting it."""

    role: Literal["system", "user", "assistant"]
    content: NonblankText


class LlamaRequest(NativeLlamaObject):
    """Validate the operation while leaving declared native sampling fields intact."""

    model: NonblankText
    messages: tuple[LlamaMessage, ...] = Field(min_length=1)
    stream: Literal[False] = False

    @field_validator("stream", mode="before")
    @classmethod
    def require_nonstreaming(cls, value: object) -> object:
        if value is not False:
            raise ValueError("Only nonstreaming generation is supported")
        return value
