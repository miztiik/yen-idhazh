"""What one borderline pair of a day's items scored, and what a judge said about it.

One row is one pair, read twice. The pair is scored by the same arithmetic the
same-story pass uses, and then a judge reads the two items in file order and
again in the other order. Two readings of one pair are what makes the judge's
own disagreement measurable, and a pair the two readings disagree about is a
fact about the judge rather than about the pair.

Nothing here decides what publishes. A verdict is a label on a pair, and the
line it eventually moves is fitted deterministically off counts (CLAUDE.md
section 0a).

The row is persisted twice on the way through: `backend/var/judge/<date>/draw.csv`
holds the day's draw before a judging leg reads it, and
`state/story-similarity/scored-pairs/<YYYY>/<MM>/<DD>.csv` holds what came back.
One shape for both, because the second file is the first one with the judge's
columns filled in.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, ClassVar, Final, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    PRINTABLE_LINE_PATTERN,
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    UrlKey,
    canonical_json,
    derive_text_digest,
)

#: How far a recomputed composite may sit from the one on the row before the row
#: is refused. The score is a sum of two products of floats, so the rule and the
#: row can differ in the last bit or two without anybody having changed a weight.
#: A millionth is far below the resolution any fitted line is read at.
SCORE_TOLERANCE: Final = 1e-6


class SameStoryVerdict(StrEnum):
    """The three words a judge may answer with, and nothing else.

    Upper case on the wire deliberately. The grammar handed to the decoder emits
    these spellings, and the three differ at the first generated token - which is
    what makes `first_token_margin` a reading about this pair rather than about
    where the three words happen to agree.
    """

    YES = "YES"
    NO = "NO"
    UNCLEAR = "UNCLEAR"


#: Which encoder produced the two vectors a cosine was taken between. A Literal
#: rather than a string, so swapping the encoder is a schema diff and a changelog
#: entry rather than a silent change of what a 0.94 means.
ScorerModelId = Literal["all-minilm-l6-v2-quantized"]

#: Every set of weights this repository ships a `config/models/` file for. A
#: Literal for the same reason the scorer is one: a judge swap changes what a
#: verdict means, and a string column would let it happen without a review.
JudgeModelId = Literal[
    "qwen3-5-9b-q4-k-m",
    "qwen3-5-9b-q4-k-m-thinking",
    "ornith-1-5-9b-q5-k-m",
    "gemma-4-e4b-it-qat-ud-q4-k-xl",
]

#: The slug this judge files its readings under. A closed set is honest here in
#: the way it could not be on the shared call stamp: that stamp is inherited by
#: judges nobody has written yet, and every row that carries this one is written
#: by this judge and no other. It sits beside the two Literals above because all
#: three are this judge's own vocabulary and three contracts already read that
#: vocabulary off this module; declared on any of them instead, this row would
#: have to import a module that imports this one back.
ContentSimilarityJudgeId = Literal["content-similarity-judge"]

#: A first-token window as one cell: printable ASCII, one line, at most 1024
#: characters. A character class rather than an identity, so a writer folds the
#: decoder's own tokens into it with `base.fit_field` and a token no ASCII
#: spelling covers costs a `?` rather than the row.
FirstTokenWindow = Annotated[
    str, StringConstraints(pattern=PRINTABLE_LINE_PATTERN, max_length=1024)
]


def scorer_stamp(
    *,
    scorer_model: ScorerModelId,
    cosine_weight: float,
    key_point_weight: float,
) -> str:
    """The three scorer columns as one value, for the places that need one."""
    return derive_text_digest(
        canonical_json(
            {
                "cosine_weight": cosine_weight,
                "key_point_weight": key_point_weight,
                "scorer_model": scorer_model,
            }
        )
    )


def judge_stamp(
    *,
    judge_model: JudgeModelId,
    prompt_digest: str,
    grammar_digest: str,
) -> str:
    """The three judge columns as one value, for the places that need one."""
    return derive_text_digest(
        canonical_json(
            {
                "grammar_digest": grammar_digest,
                "judge_model": judge_model,
                "prompt_digest": prompt_digest,
            }
        )
    )


class StorySimilarityPair(Contract):
    """One pair, what it scored, and what a judge said about it in both orders."""

    __schema_stem__: ClassVar[str] = "story-similarity-pair"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21T12:00",
            change="first_token_margin is a renormalised per-verdict gap over a 25-wide window.",
            why="A raw top-two gap over three tokens subtracted one verdict from itself.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="Added the judge-call stamp columns and the judging run id, and keyed on it.",
            why="A verdict named no sampler, and a re-judge collided with the row it replaced",
        ),
        ChangelogEntry(
            version="2026-09-18",
            change="Initial shape: one pair, two readings, and the scorer and judge behind them.",
            why="The merge line was one person's reading, and nothing recorded what it cost.",
        ),
    )

    date: DateStamp = Field(description="The digest date whose items this pair came from.")
    run_id: RunId = Field(
        description=(
            "The run that scored the pair. Two runs of one day judge the same pair twice, "
            "and both rows stay: each read its own day."
        )
    )
    shard: int = Field(
        ge=0,
        description=(
            "Which judging leg owns this row. index mod shards, never a contiguous block, "
            "so a truncated draw still spreads evenly across the legs."
        ),
    )
    pair_key: Sha256 = Field(
        description=(
            "The pair's identity: sha256 of the two url keys joined in sorted order. "
            "Recomputed on read, never trusted from the row."
        )
    )
    left_url_key: UrlKey = Field(
        description=(
            "The lower of the two address keys. Not an item id: an id is minted per day "
            "and this pair has to be recognisable across days."
        )
    )
    right_url_key: UrlKey = Field(
        description=(
            "The higher of the two address keys. Sorted so one pair has one row rather "
            "than two."
        )
    )
    composite_score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The weighted score the same-story pass would have given this pair. This is "
            "the number the fitted line is compared against, and the judge never sees it."
        ),
    )
    cosine: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The cosine between the two vectors the day already carries. Recorded raw so "
            "a later reweighting can be computed from the row rather than re-run."
        ),
    )
    key_point: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The share of key-point words the two items have in common, on the same 0 to "
            "1 scale. Recorded raw for the same reason as the cosine."
        ),
    )
    headline: bool = Field(
        description=(
            "Whether the two items shared a headline, which makes the score 1.0 outright "
            "instead of the weighted sum. On the row because the two paths give one "
            "number by two rules, and a reader cannot tell them apart afterwards."
        )
    )
    scorer_model: ScorerModelId = Field(
        description=(
            "Which encoder produced the two vectors. A Literal rather than a string, so "
            "swapping the encoder is a schema diff and a changelog entry rather than a "
            "silent change of scale."
        )
    )
    cosine_weight: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "What the cosine was worth when this row was scored, read from the committed "
            "config at scoring time. On the row rather than in a file a reader has to go "
            "and find, so a window spanning a config edit is still readable."
        ),
    )
    key_point_weight: float = Field(
        ge=0.0,
        le=1.0,
        description="What the key-point term was worth. Same reason as the cosine weight.",
    )
    verdict: SameStoryVerdict | None = Field(
        default=None,
        description=(
            "What the judge said with the items in file order. Empty until a judging leg "
            "has read the pair."
        ),
    )
    verdict_swapped: SameStoryVerdict | None = Field(
        default=None,
        description=(
            "What the judge said with the same two items in the other order. Two readings "
            "of one pair, which is what makes disagreement measurable."
        ),
    )
    usable: bool = Field(
        default=False,
        description=(
            "Whether the two readings agree. Only an agreed pair is folded into the "
            "record; a disagreement is a reading about the judge rather than about the "
            "pair."
        ),
    )
    first_token_margin: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "The gap between the two likeliest VERDICTS at the first generated "
            "position of the file-order call, over the mass the grammar admits there. "
            "Each returned token is summed into the verdict its text opens, a token "
            "opening more than one is dropped as naming none, and what is left is "
            "renormalised. A margin near zero means the grammar chose and the model did "
            "not; empty means fewer than two verdicts took any mass, which a one-word "
            "window and a window of illegal tokens both are. Rows stamped before "
            "2026-09-21T12:00 carry a raw gap between the top two TOKENS of a "
            "three-wide window instead, which subtracted one verdict from itself "
            "whenever a vocabulary spelled it two ways."
        ),
    )
    judge_model: JudgeModelId | None = Field(
        default=None,
        description="Which model judged. A Literal for the same reason the scorer is one.",
    )
    prompt_digest: Sha256 | None = Field(
        default=None,
        description=(
            "sha256 of the rendered system turn. The prompt is content, so a digest is "
            "the only honest shape for it."
        ),
    )
    grammar_digest: Sha256 | None = Field(
        default=None,
        description=(
            "sha256 of the grammar handed to the decoder. A grammar edit changes what the "
            "three words can be, so it is part of what the verdict means."
        ),
    )
    decode_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "Wall clock for both calls on this pair. A per-pair reading, so a day's spread "
            "is readable off the day file; the leg bound is sized off its own run instead."
        ),
    )
    # Seven columns at the TAIL, declared here rather than inherited from
    # `judge_call.JudgeConfigStamp`. Pydantic collects a base class's fields
    # first, so inheriting would put them at the HEAD of the header and every
    # committed row would be read one cell out of place.
    judge_id: ContentSimilarityJudgeId = Field(
        default="content-similarity-judge",
        description=(
            "Which instrument produced the verdict on this row. One member, because one "
            "judge writes this store and no other - so the column is narrowed here, where "
            "a closed set can be closed honestly."
        ),
    )
    judge_temperature: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "The sampler temperature both calls ran at, as the number it was set to. An "
            "operator reading a row needs the value, not a digest of it."
        ),
    )
    decode_digest: Sha256 | None = Field(
        default=None,
        description=(
            "sha256 of the canonical JSON of every key the caller posted that is not "
            "excluded. Taken from the payload rather than from config, because a digest "
            "built off config cannot see a payload-builder defect. The prompt is excluded "
            "because it differs every row and would make this a pair id; the grammar and "
            "the model reference are excluded because each has a column here already."
        ),
    )
    grammar_applied: bool | None = Field(
        default=None,
        description=(
            "Whether BOTH calls of this pair opened inside the grammar. The grain here is "
            "a pair, so one call that came back outside it makes this false. Empty until a "
            "judge has read the pair: a pair nothing decoded is a different fact from a "
            "decode the grammar did not hold."
        ),
    )
    first_token_probabilities: FirstTokenWindow | None = Field(
        default=None,
        description=(
            "What the decoder said it could have written at the first generated position "
            "of the FILE-ORDER call, named so because a pair makes two calls and a "
            "singular column must say which. `first_token_margin` is bucketed and "
            "renormalised out of this window, so the window is what lets that number be "
            "re-derived rather than trusted - and it is the only thing that lets a later "
            "change to the margin rule be replayed over rows already written."
        ),
    )
    thinking_spans: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many reasoning spans the file-order call decoded before its answer - 0 "
            "for a cold answer, 1 under a thinking envelope. A column of its own because "
            "`decode_digest` cannot see the envelope: the only posted key a thinking "
            "envelope moves is the prompt, and the prompt is excluded. Without this cell a "
            "margin taken after reasoning and one taken cold are one population."
        ),
    )
    judged_by_run_id: RunId | None = Field(
        default=None,
        description=(
            "The run that READ this pair, which `run_id` beside it does not say: that one "
            "names the digest run that published the day, so two judging runs over one "
            "date write the identical string there. It is in the settlement key, so a "
            "re-judged pair lands beside the row it replaces instead of being dropped as a "
            "repeat. Empty on every row written before this column existed."
        ),
    )

    @model_validator(mode="after")
    def _the_pair_is_ordered_and_named_by_its_own_contents(self) -> Self:
        """One pair has one row, and the row cannot claim to be a pair it is not.

        Sorted because the two items are symmetric: without an order, the same
        pair arrives twice under two names and the record counts one event as
        two. The key is recomputed here rather than trusted, because a writer
        that filled it from a stale variable would file the pair under another
        pair's identity and nothing downstream would notice.
        """
        if self.left_url_key >= self.right_url_key:
            raise ValueError(
                "a pair's two address keys are stored in sorted order, and "
                f"{self.left_url_key} is not below {self.right_url_key}"
            )
        derived = derive_text_digest(self.left_url_key + self.right_url_key)
        if self.pair_key != derived:
            raise ValueError(
                f"pair_key is {self.pair_key}, and the two address keys on this row "
                f"digest to {derived}"
            )
        return self

    @model_validator(mode="after")
    def _the_score_is_the_rule_the_scorer_actually_applied(self) -> Self:
        """The row carries the terms AND the answer, so the two have to agree.

        The composite comes out of one of two rules - a shared headline is 1.0
        outright, anything else is the weighted sum - and a reader looking at the
        row afterwards cannot tell which one ran. Recomputing it here is what
        stops a row recording a score no rule on this row produces.
        """
        if self.headline:
            if abs(self.composite_score - 1.0) > SCORE_TOLERANCE:
                raise ValueError(
                    "a headline match scores 1.0 outright, and this row scores "
                    f"{self.composite_score}"
                )
            return self
        weighted = self.cosine * self.cosine_weight + self.key_point * self.key_point_weight
        if abs(self.composite_score - weighted) > SCORE_TOLERANCE:
            raise ValueError(
                f"composite_score is {self.composite_score}, and the terms and weights on "
                f"this row sum to {weighted}"
            )
        return self

    @model_validator(mode="after")
    def _a_verdict_arrives_with_the_judge_that_produced_it(self) -> Self:
        """A verdict with no judge named is a label nobody can re-read.

        The three judge columns move together: a row that names a model but no
        grammar says the verdict came from somewhere the row cannot describe.
        `usable` is derived here rather than trusted, because it is the flag the
        fold reads and a writer that set it early would fold a disagreement.

        Two agreed UNCLEAR readings ARE usable. The judge was asked and answered
        the same way twice; that the answer is "I cannot tell" is a count the
        record keeps rather than a reading it throws away.
        """
        named = (self.judge_model, self.prompt_digest, self.grammar_digest)
        if any(cell is not None for cell in named) and any(cell is None for cell in named):
            raise ValueError(
                "judge_model, prompt_digest and grammar_digest are one fact in three "
                "columns, so a row carries all three or none of them"
            )
        if self.verdict is not None and self.judge_model is None:
            raise ValueError("a verdict names the judge that produced it")
        agreed = (
            self.verdict is not None
            and self.verdict_swapped is not None
            and self.verdict == self.verdict_swapped
        )
        if self.usable and not agreed:
            raise ValueError(
                "usable says the two readings agree, and this row carries "
                f"{self.verdict} and {self.verdict_swapped}"
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        for name in ("headline", "usable"):
            payload[name] = row.get(name, "") == "True"
        # By name, never by a predicate over "any default that is not None". A
        # required field has no default at all, so such a predicate would also
        # drop `version` - and the before-validator would then refill it with
        # this build's own stamp, erasing the one cell that says which rows
        # predate the widening.
        if payload["judge_id"] == "":
            del payload["judge_id"]
        return cls.model_validate(payload)
