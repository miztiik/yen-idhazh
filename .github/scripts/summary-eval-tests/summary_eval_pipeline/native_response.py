"""Which native completion and error fields must the generation caller inspect?"""

import math
from typing import Annotated, Literal, Self

from hhem_evaluator.shared.contracts.base import Count, NonblankText
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    RootModel,
    model_validator,
)


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


class NativeResponse(BaseModel):
    model_config = ConfigDict(
        extra="allow", strict=True, hide_input_in_errors=True, allow_inf_nan=False
    )
    __pydantic_extra__: dict[str, FiniteJsonValue] = Field(init=False)


class NativeAnswer(NativeResponse):
    role: Literal["assistant"]
    content: str | None
    reasoning_content: str | None = None


class NativeChoice(NativeResponse):
    index: Count
    message: NativeAnswer
    finish_reason: str | None


class NativeCompletion(NativeResponse):
    object: Literal["chat.completion"]
    model: NonblankText
    choices: tuple[NativeChoice, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_distinct_choices(self) -> Self:
        indices = [choice.index for choice in self.choices]
        if len(indices) != len(set(indices)):
            raise ValueError("choices must have distinct indices")
        return self


class NativeError(NativeResponse):
    code: str | int | None
    message: str
    type: str


class NativeErrorResponse(NativeResponse):
    error: NativeError


class NativeHealth(NativeResponse):
    status: str


class NativeHealthReply(RootModel[NativeHealth | NativeErrorResponse]):
    pass


class NativeReply(RootModel[NativeCompletion | NativeErrorResponse]):
    pass
