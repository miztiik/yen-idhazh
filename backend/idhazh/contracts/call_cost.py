"""What one model call cost, as the call itself reported it.

An item is read by more than one model call, and the five numbers below are
per request: the server reports them when that request returns. Folded into one
set they stop being readable - two calls whose `cached_tokens` are 0 and 1,493
fold to 1,493 against 3,886 prompt tokens, which is neither call's answer.

The kind is carried beside the numbers rather than inferred from the slot the
cost sits in. A slot says which call ran first; only the kind says what that
call was, and the two answers stop agreeing the day the call structure moves -
which is exactly the day an operator is reading these numbers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class CallKind(StrEnum):
    """Which model call these numbers came from.

    Four members and not two, because the call structure moves under this
    vocabulary rather than beside it. `summarize` and `visual_plan` are what the
    pipeline dispatches today, on two different models in two different jobs.
    `label` and `summarize_and_plan` are the pair `idhazh.classify.calls` builds,
    which plan 11 row #5b wires in behind a flag and row #6 then makes the only
    pair. A reading that spans the flip needs all four names, or the step change
    in every series reads as a regression rather than as the design change it is.
    """

    #: Today's summarizer call: one article in, one summary out.
    SUMMARIZE = "summarize"
    #: Today's small-model visual plan, dispatched in the separate visuals job.
    VISUAL_PLAN = "visual_plan"
    #: Call 1 of the two-call planner: labels what the candidate pass found.
    LABEL = "label"
    #: Call 2 of the two-call planner: writes the summary and then the plan.
    SUMMARIZE_AND_PLAN = "summarize_and_plan"


class CallCost(Model):
    """One model call's own five numbers.

    Nested rather than flattened because the same five have to be described once
    and checked once. The two CSV ledgers cannot nest, so they spell these names
    with a `call_1_`/`call_2_` prefix and `idhazh.telemetry` is the one place
    that flattens - one translator, against one copy of this validator per
    contract that would otherwise carry it.
    """

    kind: CallKind
    prefill_ms: int = Field(
        default=0,
        ge=0,
        description=(
            "Milliseconds this call spent reading its prompt. A duration and never "
            "a rate: a prompt token costs more the deeper into the context it sits, "
            "so dividing this by the tokens the call evaluated gives a figure that "
            "cannot be compared with another call's."
        ),
    )
    decode_ms: int = Field(
        default=0, ge=0, description="Milliseconds this call spent writing its reply."
    )
    input_tokens: int = Field(default=0, ge=0, description="Prompt tokens, cached part included.")
    output_tokens: int = Field(default=0, ge=0, description="Tokens this call wrote.")
    cached_tokens: int = Field(
        default=0,
        ge=0,
        description=(
            "Prompt tokens the runtime reused instead of reading. Zero is a real "
            "answer and means the slot was cold; `input_tokens` minus this is what "
            "`prefill_ms` paid for."
        ),
    )

    @model_validator(mode="after")
    def _cache_fits_inside_the_prompt(self) -> Self:
        if self.cached_tokens > self.input_tokens:
            raise ValueError("cached_tokens cannot exceed input_tokens")
        return self


#: The five per-call numbers, in the order every flattened spelling uses them.
COST_FIELDS: tuple[str, ...] = (
    "prefill_ms",
    "decode_ms",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
)
