"""What the prompt may say to the model."""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import Model


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
    asks_for_a_visual_plan: bool = Field(
        default=True,
        description=(
            "Whether the run asks the summarize-and-plan call for a picture. True is what "
            "the production run does and what ships. A case of the pipeline test workflow "
            "that runs the summary-only path sets it false beside an empty "
            "`visuals.enabled_kinds`, which is what takes the plan fields off that call's "
            "grammar. The window gate reserves the model file's response cap whichever "
            "way this is set, so no sizing reads it; it is stamped with the prompt inputs."
        ),
    )
