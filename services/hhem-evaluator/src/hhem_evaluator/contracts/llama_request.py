"""Which native nonstreaming text request may reach the fixed llama operation?"""

from typing import Literal

from pydantic import ConfigDict, Field, JsonValue, field_validator

from .base import NonblankText
from .server_contract import ServerContract


class NativeLlamaObject(ServerContract):
    """Preserve native JSON extension fields rather than translate model parameters."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)


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
