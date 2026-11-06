"""Which native completion and error fields must the generation caller inspect?"""

from typing import Literal, Self

from hhem_evaluator.contracts.base import Count, NonblankText
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class NativeResponse(BaseModel):
    model_config = ConfigDict(
        extra="allow", strict=True, hide_input_in_errors=True, allow_inf_nan=False
    )


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
