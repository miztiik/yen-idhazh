"""What the prompt may say to the model."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob

#: The `summarize` knob this block used to carry. `asks_for_a_visual_plan` said
#: whether the run asks the model for a picture, and nothing acted on it but the
#: stamp the run's prompt inputs carry. Whether a plan is asked for is decided by
#: `visuals.enabled_kinds`, so the knob is refused by name and points there.
SUPERSEDED_SUMMARIZE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"asks_for_a_visual_plan": "visuals.enabled_kinds"}
)


class SummarizeConfig(Model):
    """What the prompt may say to the model.

    A reply is published exactly as the model wrote it, so nothing here asks for
    a length, accepts a reply or trims one.

    Every number here is substituted into the prompt text at render time, so a
    prompt that states one cannot drift from the config (Guardrail #6).
    """

    max_verbatim_words: int = Field(
        default=20,
        ge=1,
        description=(
            "Longest quotation the prompt allows, and it must be attributed. Long "
            "enough to carry a real sentence somebody said, short enough that a summary "
            "cannot become the article. This is a prompt instruction, not a copied-text "
            "measurement or rejection threshold."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _a_removed_knob_is_refused_by_name(cls, data: Any) -> Any:
        return refuse_a_removed_knob("summarize", data, SUPERSEDED_SUMMARIZE_NAMES)
