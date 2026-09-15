"""What the prompt asks the model for, and what the pipeline accepts back."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class OverLengthAction(StrEnum):
    """What to do with a reply that overshoots its band by more than the policy allows."""

    TRIM = "trim"
    PUBLISH = "publish"


class LengthPolicy(Model):
    """What the pipeline accepts, once the prompt has asked.

    The ask lives on the band; this is the tolerance around it. Both are here
    rather than in `evaluation` because a length miss is not a quality finding -
    it is the model rounding a request - and a tolerance that cannot see which
    band an item is in cannot be right for more than one of them.

    Every number is a starting point rather than a measurement (Guardrail #10). Our
    own length figures describe a pipeline mid-repair - the prompt is being
    tuned and a fine-tune is in flight - so none of them was used to pick one.
    """

    overshoot_ratio: float = Field(
        default=0.20,
        ge=0.0,
        description=(
            "How far past the band's ask a reply may run and still publish untouched, "
            "as a share of `target_words_max`. Whichever of this and `overshoot_words` "
            "is larger wins, so a short band gets a usable allowance too: 20 percent of "
            "45 words is nine, and nine words is one clause."
        ),
    )
    overshoot_words: int = Field(
        default=25,
        ge=0,
        description=(
            "The same allowance as a flat word count, for the bands where a ratio is "
            "too small to mean anything. The larger of the two applies."
        ),
    )
    undershoot_ratio: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description=(
            "How far under the band's ask a reply may fall and still publish, as a share "
            "of `target_words_min`. Brevity is not a fault: a short summary of a long "
            "article is a thin summary, and the reader can see that it is short. Losing "
            "the story entirely tells them nothing."
        ),
    )
    absolute_floor_words: int = Field(
        default=25,
        ge=1,
        description=(
            "Below this a reply is a failed extraction wearing a summary's clothes, and "
            "it is the one length that still fails an item. Applies only to sources "
            "longer than `floor_applies_above_source_words`, because a 40-word summary "
            "of a 60-word post is the correct answer."
        ),
    )
    floor_applies_above_source_words: int = Field(
        default=700,
        ge=0,
        description=(
            "Sources shorter than this are exempt from `absolute_floor_words`. A brief "
            "has no length to lose."
        ),
    )


class SummaryBand(Model):
    """How long a summary to ask for, once the article is at least this long."""

    min_source_words: int = Field(
        ge=0, description="The band applies to articles this long and longer."
    )
    target_words_min: int = Field(ge=1, description="The shortest summary the prompt asks for.")
    target_words_max: int = Field(ge=1, description="The longest summary the prompt asks for.")
    over_length_action: OverLengthAction = Field(
        default=OverLengthAction.TRIM,
        description=(
            "What to do with a reply that overshoots past the policy's allowance. A "
            "short band trims at the last complete sentence that fits, because wire-"
            "shaped prose front-loads and a tail cut is safe. A long band publishes "
            "over-length instead: on a feature the qualification lands last, so cutting "
            "the tail is how a summary becomes wrong rather than merely long."
        ),
    )
    key_points_min: int = Field(
        default=2,
        ge=1,
        description=(
            "The fewest key points this band asks for, and the decoder's floor for the "
            "band. The prompt and the response schema read this same number. Never below "
            "1: the published digest refuses an item with no key points."
        ),
    )
    key_points_max: int = Field(
        default=5,
        ge=1,
        description=(
            "The most key points this band asks for, and the decoder's ceiling for the "
            "band. A short band asks for fewer: a 40-word summary of a 60-word post "
            "cannot carry five distinct facts on top of itself, so the extra key points "
            "only restate it. On the band, not the whole config, so the shortest band "
            "asks for one where the longest asks for five."
        ),
    )

    @model_validator(mode="after")
    def _the_range_is_ordered(self) -> Self:
        if self.target_words_min >= self.target_words_max:
            raise ValueError("target_words_min must sit below target_words_max")
        if self.key_points_min > self.key_points_max:
            raise ValueError("key_points_min must not exceed key_points_max")
        return self


def _default_bands() -> list[SummaryBand]:
    """Five sizes: note, post, report, feature, long read.

    Starting points chosen from editorial practice outside this project, not
    from our own numbers - nothing here may be quoted as a measurement (Rule
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

    Each band carries its own key-point ask, graded from one at the note to five
    at the long read: a note holds one fact, and asking it for five requests
    facts the article does not have. Each also carries what to do when a reply
    runs long - see `SummaryBand.over_length_action`.
    """
    return [
        SummaryBand(
            min_source_words=0, target_words_min=30, target_words_max=45,
            key_points_min=1, key_points_max=1,
        ),
        SummaryBand(
            min_source_words=60, target_words_min=45, target_words_max=80,
            key_points_min=1, key_points_max=2,
        ),
        SummaryBand(
            min_source_words=700, target_words_min=70, target_words_max=130,
            key_points_min=2, key_points_max=3,
        ),
        SummaryBand(
            min_source_words=2000, target_words_min=95, target_words_max=160,
            key_points_min=2, key_points_max=4,
            over_length_action=OverLengthAction.PUBLISH,
        ),
        SummaryBand(
            min_source_words=4000, target_words_min=120, target_words_max=200,
            key_points_min=2, key_points_max=5,
            over_length_action=OverLengthAction.PUBLISH,
        ),
    ]


class SummarizeConfig(Model):
    """What the prompt asks the model for, and what the pipeline accepts back.

    A prompt is a request and a gate is a rule. Asking for a tighter range than
    we accept is what stops a two-word miss from losing a story, so the ask
    (`bands`) and the tolerance around it (`length_policy`) both live here,
    where an operator editing one can see the other.

    The allowance is derived from the band rather than applied flat to all five
    rungs, so it can see which band an item is in. No length outcome except
    `length_policy.absolute_floor_words` drops an item: a reply outside the
    tolerance is still a story, and deleting it would cost the day a story to
    punish the model for rounding.

    Every band and title number here is substituted into the prompt text at
    render time, so the prompt cannot drift from the bounds the pipeline enforces
    (Guardrail #6). `key_point_restatement_ceiling` is the one value that is not asked
    for: it is a post-parse check `to_summary` runs on what the model returned,
    and it lives here because the count it protects - the band's key_points_min -
    does too.
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
            "How far a reply may miss its band's ask and still publish, and what happens "
            "when it misses by more. Config rather than code so the tolerance can move "
            "with the prompt while the prompt is still being tuned."
        ),
    )
    title_words_min: int = Field(
        default=6,
        ge=1,
        description=(
            "Shortest title the prompt asks for. Below this a headline stops naming "
            "who did what, and the reader is back to guessing from the source's own "
            "framing."
        ),
    )
    title_words_max: int = Field(
        default=14,
        ge=1,
        le=40,
        description=(
            "Longest title the prompt asks for, and the decoder's ceiling. Unlike the "
            "summary there is no floor on the decoder: a headline does not stop early, "
            "and a floor would only pad a good short one. Capped at 40 so the widest "
            "decoder ceiling this can produce still fits an UntrustedLine, which is "
            "what the payload field is."
        ),
    )
    max_verbatim_words: int = Field(
        default=20,
        ge=1,
        description=(
            "Longest quotation the prompt allows, and it must be attributed. Long "
            "enough to carry a real sentence somebody said, short enough that a summary "
            "cannot become the article. The ledger measures the run that actually came "
            "back (`verbatim_run`), so this number is the ask and that column is the "
            "answer."
        ),
    )
    key_point_words_max: int = Field(
        default=80,
        ge=1,
        description=(
            "Longest key point the decoder will emit, spent as a character rail at 12 "
            "characters a word the same way the title and the summary are. There was no "
            "rail here at all until the two-call planner needed one: with an unbounded "
            "string in the reply shape, the worst-case reply length is not arithmetic, "
            "and a budget derived from bounds that do not exist is a guess with a table "
            "next to it. Deliberately above anything observed rather than tight to it - "
            "a maxLength is a hard grammar stop that truncates mid-word, so a rail set "
            "at the observed maximum turns a slightly long key point into a parse "
            "failure for the whole item. It sits well above the longest key point the "
            "pipeline has published, so only a reply of a different order reaches it."
        ),
    )
    key_point_restatement_ceiling: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "Above this share of a key point's four-word phrases already appearing in "
            "the summary, `to_summary` drops the key point as a restatement and keeps the "
            "item with the rest. A distinctness floor, not a word ban: only the overlap "
            "ratio counts, never a single shared word, so a key point may reuse the "
            "summary's words and still add a fact. A starting point, not a calibrated "
            "threshold (Guardrail #10): it sits in the wide gap between a key point that "
            "adds a fact and one that is a verbatim slice of the summary. The drop never "
            "removes the last key point - "
            "the payload requires one - so a reply whose every key point restates still "
            "publishes with the least-restating up to the band's key_points_min."
        ),
    )
    asks_for_a_visual_plan: bool = Field(
        default=True,
        description=(
            "Whether the two-call sequence is sized for a summarize-and-plan call that "
            "asks for a picture. True is what the production run does and what ships. It "
            "exists so an arm of the pipeline test workflow can run the summary-only path "
            "end to end: setting `visuals.enabled_kinds` to nothing takes the plan fields "
            "off that call's grammar, and this takes the plan's decode budget out of the "
            "window sizing beside it. The two move together or the sizing is wrong in the "
            "expensive direction - it reserves room for a decode that never happens, and "
            "refuses articles that would have fitted."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _key_point_counts_moved_onto_the_band(cls, data: Any) -> Any:
        """Read a config that still names the old global key-point counts onto each band.

        `key_points_min` and `key_points_max` used to sit here, one pair for every
        band. They moved onto `SummaryBand` so the shortest band can ask for fewer
        than the longest - a note carries one fact, and asking it for five requests
        facts the article does not hold. `config/` is a persisted surface and every
        model here forbids unknown keys, so a file written before the move would be
        refused outright (section 11). This distributes an old global value onto any
        band that does not carry its own, then drops the global key.
        """
        if not isinstance(data, dict):
            return data
        bands = data.get("bands")
        if not isinstance(bands, list):
            return data
        migrated = dict(data)
        migrated["bands"] = list(bands)
        for name in ("key_points_min", "key_points_max"):
            if name not in migrated:
                continue
            carried = migrated.pop(name)
            migrated["bands"] = [
                {**band, name: band.get(name, carried)} if isinstance(band, dict) else band
                for band in migrated["bands"]
            ]
        return migrated

    @model_validator(mode="after")
    def _the_bands_cover_every_article(self) -> Self:
        if self.bands[0].min_source_words != 0:
            raise ValueError("the first band must start at zero, or a short article has no band")
        starts = [band.min_source_words for band in self.bands]
        if starts != sorted(set(starts)):
            raise ValueError("bands must climb, and no two may start at the same length")
        if self.title_words_min > self.title_words_max:
            raise ValueError("title_words_min must not exceed title_words_max")
        # Rung 0 asks for the shortest summary on the ladder, so a floor at or above
        # it fails every note the digest carries - and it fails them as a bad
        # extraction, which is the one length verdict that still drops an item.
        if self.length_policy.absolute_floor_words >= min(
            band.target_words_min for band in self.bands
        ):
            raise ValueError(
                "length_policy.absolute_floor_words must sit below every band's "
                "target_words_min, or the shortest band fails every item"
            )
        return self

    def band_for(self, source_words: int) -> SummaryBand:
        """The longest band the article reaches. Total, because band one starts at zero."""
        chosen = self.bands[0]
        for band in self.bands:
            if source_words >= band.min_source_words:
                chosen = band
        return chosen

    def allowance(self, band: SummaryBand) -> int:
        """Words past the band's ask that still publish untouched."""
        policy = self.length_policy
        return max(int(band.target_words_max * policy.overshoot_ratio), policy.overshoot_words)

    def decoder_words_max(self) -> int:
        """The widest reply any band can publish, which is the rail the decoder gets.

        Deliberately the loosest number in the file. The rail is enforced by the
        decoder as a character budget, so a reply that runs past it fails to parse
        at all - and a reply that cannot parse never reaches the length verdict
        that would have trimmed or published it. A tight rail would turn every
        overshoot back into the lost item this policy exists to prevent.
        """
        return max(band.target_words_max + self.allowance(band) for band in self.bands)

    def decoder_words_min(self) -> int:
        """The narrowest reply any band can publish. See `decoder_words_max`."""
        return self.length_policy.absolute_floor_words
