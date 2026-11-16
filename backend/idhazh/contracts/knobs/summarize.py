"""What the prompt may ask the model for, and how much room the reply gets."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class LengthPolicy(Model):
    """How much room the output budget leaves past a band's ask.

    Nothing here accepts, trims or rejects a reply: what the model writes is what
    is published. The two numbers only size the budget a call is given
    (`SummarizeConfig.decoder_words_max`), so a reply that runs past its ask
    still has the tokens to finish.

    Every number is a starting point rather than a measurement (Guardrail #10).
    """

    overshoot_ratio: float = Field(
        default=0.20,
        ge=0.0,
        description=(
            "How far past the band's ask the output budget leaves room for a reply to "
            "run, as a share of `target_words_max`. Whichever of this and "
            "`overshoot_words` is larger wins, so a short band gets usable room too: 20 "
            "percent of 45 words is nine, and nine words is one clause."
        ),
    )
    overshoot_words: int = Field(
        default=25,
        ge=0,
        description=(
            "The same room as a flat word count, for the bands where a ratio is "
            "too small to mean anything. The larger of the two applies."
        ),
    )


class SummaryBand(Model):
    """How long a summary to ask for, once the article is at least this long."""

    min_source_words: int = Field(
        ge=0, description="The band applies to articles this long and longer."
    )
    target_words_min: int = Field(ge=1, description="The shortest summary the prompt asks for.")
    target_words_max: int = Field(ge=1, description="The longest summary the prompt asks for.")

    @model_validator(mode="after")
    def _the_range_is_ordered(self) -> Self:
        if self.target_words_min >= self.target_words_max:
            raise ValueError("target_words_min must sit below target_words_max")
        return self


def _default_bands() -> list[SummaryBand]:
    """Five sizes: note, post, report, feature, long read.

    Starting points chosen from editorial practice outside this project, not
    from our own numbers - nothing here may be quoted as a measurement (Guardrail
    #10), and our length figures describe a pipeline mid-repair. The first band
    begins at zero so every article lands in one.

    The ask grows with the source logarithmically, not in proportion to it.
    Doubling an article does not double its distinct claims; it adds
    scene-setting and repetition. Every trade that abstracts at scale says this
    twice - an informative abstract is capped near 250 words whether the paper
    is 4,000 words or 40,000 (ANSI/NISO Z39.14), and the executive summary's
    "five to ten percent" rule is always overridden by "never more than two
    pages". So the ladder opens with a ratio and closes with a ceiling.

    **The ceiling is 200 words and it governs the rest.** An adult reads
    non-fiction at about 240 words a minute, so the two minutes this digest asks
    for is roughly 480 words. Thirty titles spend 250 to 300 of them being
    scanned. What is left buys two summaries at 90 words or one at 200, and a
    200-word item is already 50 seconds on one story out of thirty. Past that we
    stop helping a reader decide whether to click through and start being the
    article, badly.

    The last floor is the last one there may ever be, and it sits at 4,000 words
    rather than at the cut point on purpose: the model is handed at most
    `int(extract.truncation_cap_tokens / extract.TOKENS_PER_WORD)` words, so
    every source past 4,000 arrives with much the same evidence and earns the
    same ask. A rung above it would grade articles by a length the model never
    saw.
    """
    return [
        SummaryBand(
            min_source_words=0, target_words_min=30, target_words_max=45,
        ),
        SummaryBand(
            min_source_words=60, target_words_min=45, target_words_max=80,
        ),
        SummaryBand(
            min_source_words=700, target_words_min=70, target_words_max=130,
        ),
        SummaryBand(
            min_source_words=2000, target_words_min=95, target_words_max=160,
        ),
        SummaryBand(
            min_source_words=4000, target_words_min=120, target_words_max=200,
        ),
    ]


class SummarizeConfig(Model):
    """What the prompt may ask the model for, and how much room the reply gets.

    A reply is published exactly as the model wrote it, so nothing here accepts,
    trims or rejects one. `bands` is the length each article size may be asked
    for and `length_policy` the room the output budget leaves past it; the title
    numbers are the headline's own.

    Every band and title number here is substituted into the prompt text at
    render time, so a prompt that states one cannot drift from the number the
    output budget is sized by (Guardrail #6).
    """

    bands: list[SummaryBand] = Field(
        default_factory=_default_bands,
        min_length=1,
        description=(
            "One length ask per article size, ordered by min_source_words. A release "
            "note and a long read asked for the same range gives a padded summary of "
            "the first and a thin one of the second."
        ),
    )
    length_policy: LengthPolicy = Field(
        default_factory=LengthPolicy,
        description=(
            "How much room the output budget leaves for a reply to run past its band's "
            "ask. Config rather than code so it can move with the prompt while the "
            "prompt is still being tuned."
        ),
    )
    title_words_min: int = Field(
        default=6,
        ge=1,
        description=(
            "Shortest title a prompt template may ask for, as `$title_words_min`. No "
            "published headline is checked against it."
        ),
    )
    title_words_max: int = Field(
        default=14,
        ge=1,
        description=(
            "Longest title a prompt template may ask for, as `$title_words_max`, and the "
            "headline's share of the reply's output budget. A headline is published as "
            "the model wrote it and is never cut or dropped for its length against this."
        ),
    )
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
            "Whether the two-call sequence is sized for a summarize-and-plan call that "
            "asks for a picture. True is what the production run does and what ships. It "
            "exists so a case of the pipeline test workflow can run the summary-only path "
            "end to end: setting `visuals.enabled_kinds` to nothing takes the plan fields "
            "off that call's grammar, and this takes the plan's decode budget out of the "
            "window sizing beside it. The two move together or the sizing is wrong in the "
            "expensive direction - it reserves room for a decode that never happens, and "
            "refuses articles that would have fitted."
        ),
    )

    @model_validator(mode="after")
    def _the_bands_cover_every_article(self) -> Self:
        if self.bands[0].min_source_words != 0:
            raise ValueError("the first band must start at zero, or a short article has no band")
        starts = [band.min_source_words for band in self.bands]
        if starts != sorted(set(starts)):
            raise ValueError("bands must climb, and no two may start at the same length")
        if self.title_words_min > self.title_words_max:
            raise ValueError("title_words_min must not exceed title_words_max")
        return self

    def band_for(self, source_words: int) -> SummaryBand:
        """The longest band the article reaches. Total, because band one starts at zero."""
        chosen = self.bands[0]
        for band in self.bands:
            if source_words >= band.min_source_words:
                chosen = band
        return chosen

    def allowance(self, band: SummaryBand) -> int:
        """Words past the band's ask that the output budget leaves room for."""
        policy = self.length_policy
        return max(int(band.target_words_max * policy.overshoot_ratio), policy.overshoot_words)

    def decoder_words_max(self) -> int:
        """The most words any band's ask and allowance add up to.

        The union over bands rather than one band's figure, so it does not depend
        on the article in front of it. It sizes the output budget; it is not a
        limit on what is published.
        """
        return max(band.target_words_max + self.allowance(band) for band in self.bands)
