"""What one pair of a night's items scored, which slice of the draw held it, and what a judge said.

One row is one pair put to the judge. The pair is scored by the same arithmetic the
same-story pass uses, the draw drops it into a slice of the score range, and a judge reads
the two items in file order and again in the other order. Two readings of one pair are what
makes the judge's own disagreement measurable, and a pair the two readings disagree about
is a fact about the judge rather than about the pair.

**The slice is on the row because the draw is not even.** Scores near a threshold are
sampled in thin slices and heavily, scores far from both thresholds are sampled lightly, so
a count of the judged pairs says little about the night until every pair is weighted by how
likely the draw was to take it. The row carries the slice, how many pairs it held that
night, how many the draw took, how many of those came back usable, and the chance that
follows: usable over available. A usable pair then stands for one over its chance pairs of
the night, and a night's totals are rebuilt from the rows alone. Each lightly sampled end of
the range is one slice, running out to -1.0 or to 1.0.

**Both thresholds in force are on the row, unrounded.** The slice edges sit on a fixed grid,
so they say where the pair was filed and not which threshold the draw was following. The
thresholds say that, and the two lightly sampled ends are checked against them.

**One shape for the draw and for the filed row.** The draw leaves every judge column,
`slice_pairs_usable` and `sampling_chance` empty, a judging unit fills the judge columns,
and the collecting job fills the other two once the night's readings are in, because a draw
cannot know which pairs will agree. The scratch file the units pass between jobs is this
shape in CSV; the ledger door files it as parquet under
`state/raw/content-similarity-judge/pair-verdicts/<YYYY>/<MM>/<DD>/`, and the gardener packs
it under `state/compact/content-similarity-judge/pair-verdicts/`. The folder is spelled in
`idhazh.ledger`, which is where a path belongs and which this module may not import
(CLAUDE.md section 4).

**The words a verdict is written in sit here too.** The three answers a judge may give, the
reasons a reading is refused, and the recorded model identities are declared once, beside the
row that carries them, and every contract and stage that names a verdict imports them from
here.

Nothing here decides what publishes. A verdict is a label on a pair.
"""

from __future__ import annotations

import json
import math
import re
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Final, Self

from pydantic import (
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from idhazh.contracts.base import (
    DATE_PATTERN,
    PRINTABLE_LINE_PATTERN,
    REL_PATH_PATTERN,
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    Slug,
    UrlKey,
    derive_text_digest,
)

# This date identifies emitted-evidence semantics, not an operator setting.
JUDGE_POLICY_VERSION: Final[DateStamp] = "2026-11-05"

#: How far a stored number may sit from the one its own columns give: a score from its two
#: terms, a slice edge from the score it holds, a chance from its two counts, a gap from its
#: two ends. Each is a product, a sum or a ratio of values the writer also held in floating
#: point, so the two can differ in the last bit or two without anybody having changed a
#: weight, and a writer that rounds to six places must not lose its night for it. A millionth
#: is far below the resolution any threshold is read at.
RECOMPUTED_TOLERANCE: Final = 1e-6

#: How far past 1 or -1 a cosine may land from floating-point noise alone. A cosine is a dot
#: product over two norms, and on two identical vectors the quotient can come out one bit past
#: 1.0. A billionth is far above that noise and far below any real fault.
UNIT_RANGE_NOISE: Final = 1e-9


class ReadingRefusalReason(StrEnum):
    """Why a completed model response is not a valid judge reading."""

    INVALID_LITERAL = "invalid_literal"
    MISSING_EMISSION = "missing_emission"
    INVALID_EMISSION = "invalid_emission"
    AMBIGUOUS_EMISSION = "ambiguous_emission"
    MISMATCHED_EMISSION = "mismatched_emission"


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


#: Recorded model identities use the config's slug format, not its current
#: membership. Retired weights must remain readable without relabelling them.
ScorerModelId = Slug
JudgeModelId = Slug

#: A first-token window as one cell: printable ASCII, one line, at most 1024
#: characters. A character class rather than an identity, so a writer folds the
#: decoder's own tokens into it with `base.fit_field` and a token no ASCII
#: spelling covers costs a `?` rather than the row.
FirstTokenWindow = Annotated[
    str, StringConstraints(pattern=PRINTABLE_LINE_PATTERN, max_length=1024)
]


class PairBucket(StrEnum):
    """Where a pair's score sat against the draw's five score buckets.

    Written in score order. The two ends (`fully_dissimilar` and `fully_similar`) are the
    single-slice lightly sampled buckets sitting outside the two straddling thin bands;
    `lower_thin` and `upper_thin` straddle each threshold by `thin_band_half_width` (clamped
    so each end keeps at least one `slice_width` slice), and `middle_coarse` fills the gap
    between the two thin bands. A row says which allocation took the pair.
    """

    FULLY_DISSIMILAR = "fully_dissimilar"
    LOWER_THIN = "lower_thin"
    MIDDLE_COARSE = "middle_coarse"
    UPPER_THIN = "upper_thin"
    FULLY_SIMILAR = "fully_similar"


def _snapped_to_the_unit_range(value: Any) -> Any:
    """A number a rounding error past 1, or past -1, is 1, or -1; any other is untouched.

    Declared after the range it feeds, so it runs first and the range then checks what it
    returns. A value that is further out is a real fault and keeps the refusal the range
    gives. Text is read as a number first, because the scratch CSV carries every cell as text.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if 1.0 < abs(number) <= 1.0 + UNIT_RANGE_NOISE:
        return math.copysign(1.0, number)
    return value


#: A cosine or a score: from -1 to 1, with the floating-point noise past either end folded back.
UnitRangeNumber = Annotated[
    float, Field(ge=-1.0, le=1.0), BeforeValidator(_snapped_to_the_unit_range)
]


def canonical_compact_object(text: str, *, column: str) -> dict[str, Any]:
    """The one JSON object a compact text column holds, or a refusal naming the column.

    Compact means sorted keys, no spaces, ASCII only and no trailing newline, so the same
    content is always the same text and two nights can be compared as strings. A column of
    this kind exists because a mapping cannot be a parquet column. Checked by writing the
    parsed object back out and comparing, which also refuses a repeated key.
    """
    try:
        held = json.loads(text)
    except ValueError as error:
        raise ValueError(f"{column} is not JSON text") from error
    if not isinstance(held, dict):
        raise ValueError(f"{column} is one JSON object, and this text is not")
    if json.dumps(held, separators=(",", ":"), sort_keys=True, ensure_ascii=True) != text:
        raise ValueError(
            f"{column} is compact JSON with sorted keys, no spaces and ASCII only, "
            "and this text is not written that way"
        )
    return held


def _checked_config_versions(text: str) -> str:
    """Every config file the night read, each with the date its values last changed.

    Keyed by path relative to `config/` so the name never carries a drive or a backslash.
    """
    held = canonical_compact_object(text, column="config_versions")
    if not held:
        raise ValueError("config_versions names at least the one config file the night read")
    for path, version in held.items():
        if not re.fullmatch(REL_PATH_PATTERN, path):
            raise ValueError(
                f"config_versions names {path!r}, which is not a path relative to config/"
            )
        if not isinstance(version, str) or not re.fullmatch(DATE_PATTERN, version):
            raise ValueError(
                f"config_versions gives {path} the version {version!r}, which is not a "
                "YYYY-MM-DD date"
            )
    return text


#: The config files a night read and the version of each, as one compact JSON object.
ConfigVersionsText = Annotated[str, AfterValidator(_checked_config_versions)]


class StorySimilarityPairVerdict(Contract):
    """One pair, its score and slice, and what a judge said about it in both orders."""

    model_config = ConfigDict(allow_inf_nan=False)

    __schema_stem__: ClassVar[str] = "story-similarity-pair-verdict"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-18",
            change="Initial shape: a judged pair with its draw slice and sampling chance.",
            why="A pair drawn at a known chance can be weighted back up to the whole night.",
        ),
    )

    date: DateStamp = Field(
        description="The digest date, a UTC day, whose items this pair came from."
    )
    run_id: RunId = Field(
        description=(
            "The council run that drew and judged the pair. Two runs of one night judge "
            "the same pair twice, and both rows stay: each read its own night."
        )
    )
    work_part_index: int = Field(
        ge=0,
        description=(
            "Which part of the judging split owns this row: its index in the draw mod the "
            "part count, never a contiguous block, so a truncated draw still spreads "
            "evenly across the parts."
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
    similarity_score: UnitRangeNumber = Field(
        description=(
            "The weighted score the same-story pass would give this pair. It is the number "
            "the slice and the two thresholds are read against, and the judge never sees "
            "it. It runs below zero because the draw also looks at pairs with nothing in "
            "common."
        )
    )
    cosine: UnitRangeNumber = Field(
        description=(
            "The cosine between the two vectors the day already carries. Recorded raw so "
            "a later reweighting can be computed from the row rather than re-run."
        )
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
            "Which encoder produced the two vectors. A recorded slug, independent of "
            "the models currently configured."
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
    bucket: PairBucket = Field(
        description=(
            "Which of the draw's five buckets took the pair: the two single-slice lightly "
            "sampled ends outside the straddling thin bands, the straddling thin slices "
            "around each threshold, or the coarse slices between them."
        )
    )
    slice_low: float = Field(
        description=(
            "The lower edge of the slice the pair sat in. The score is at or above it. "
            "The fully dissimilar end is one slice and starts at -1.0."
        )
    )
    slice_high: float = Field(
        description=(
            "The upper edge of the slice the pair sat in. The score is at or below it. "
            "The fully similar end is one slice and stops at 1.0."
        )
    )
    slice_pairs_available: int = Field(
        ge=1,
        description=(
            "How many pairs the slice held that night, this one included. The pool the "
            "draw sampled from."
        ),
    )
    slice_pairs_judged: int = Field(
        ge=1,
        description=(
            "How many pairs the draw took from the slice to judge, this one included. "
            "Known when the draw is made, and never recounted: a pair that left no row "
            "still counts here."
        ),
    )
    slice_pairs_usable: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many of the run's rows in this slice have two agreeing readings. Empty "
            "until the collecting job has the night's readings, because a draw cannot know "
            "which pairs will agree."
        ),
    )
    sampling_chance: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Usable pairs over available pairs for the slice: the chance a pair of this "
            "slice was both taken and usable. The same on every row of the slice, "
            "including rows whose own readings disagreed, and zero when the slice had no "
            "usable pair. A usable pair is weighted by one over this. Empty until the "
            "collecting job fills it together with the usable count."
        ),
    )
    lower_threshold_in_force: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "The lower bound threshold the draw followed that night, unrounded. Below it "
            "pairs are fully dissimilar."
        ),
    )
    upper_threshold_in_force: float = Field(
        ge=-1.0,
        le=1.0,
        description=(
            "The upper bound threshold the draw followed that night, unrounded. Above it "
            "pairs are fully similar."
        ),
    )
    verdict: SameStoryVerdict | None = Field(
        default=None,
        description=(
            "What the judge said with the items in file order. Empty until a judging unit "
            "has read the pair, and empty where the reading was refused."
        ),
    )
    verdict_swapped: SameStoryVerdict | None = Field(
        default=None,
        description=(
            "What the judge said with the same two items in the other order. Two readings "
            "of one pair, which is what makes disagreement measurable."
        ),
    )
    readings_agree: bool = Field(
        default=False,
        description=(
            "Whether two valid readings agree. Only an agreed pair is usable; a "
            "disagreement is a reading about the judge rather than about the pair."
        ),
    )
    first_token_margin: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "The gap between the two likeliest VERDICTS at the first generated position of "
            "the file-order call, over the mass the grammar admits there. Each returned "
            "token is summed into the verdict its text opens, a token opening more than one "
            "is dropped as naming none, and what is left is renormalised. A margin near "
            "zero means the grammar chose and the model did not; empty means fewer than two "
            "verdicts took any mass, which a one-word window and a window of illegal "
            "tokens both are."
        ),
    )
    judge_model: JudgeModelId | None = Field(
        default=None,
        description="Which model judged, as its recorded slug. Empty until a judge ran.",
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
        description="Wall clock for both calls on this pair, in seconds.",
    )
    judge_temperature: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "The sampler temperature both calls ran at, as the number it was set to. An "
            "operator reading a row needs the value, not a digest of it."
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
            "of the FILE-ORDER call. `first_token_margin` is renormalised out of this "
            "window, so the window is what lets that number be re-derived rather than "
            "trusted."
        ),
    )
    thinking_spans: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many reasoning spans the file-order call decoded before its answer - 0 "
            "for a cold answer, 1 under a thinking envelope. Without this cell a margin "
            "taken after reasoning and one taken cold are one population."
        ),
    )
    judge_policy_version: DateStamp | None = Field(
        default=None,
        description=(
            "UTC date identifying how the judge's emitted evidence is read; empty on an "
            "unjudged pair."
        ),
    )
    config_versions: ConfigVersionsText = Field(
        description=(
            "Every config file the night read and the version of each, as one compact JSON "
            "object keyed by path relative to config/. One text rather than one column a "
            "file, so a new config file changes no contract."
        )
    )

    @model_validator(mode="after")
    def _the_pair_is_ordered_and_named_by_its_own_contents(self) -> Self:
        """One pair has one row, and the row cannot claim to be a pair it is not.

        Sorted because the two items are symmetric: without an order, the same pair
        arrives twice under two names and the night counts one event as two. The key is
        recomputed here rather than trusted, because a writer that filled it from a stale
        variable would file the pair under another pair's identity and nothing downstream
        would notice.
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

        The score comes out of one of two rules - a shared headline is 1.0 outright,
        anything else is the cosine at its weight - and a reader looking at the row
        afterwards cannot tell which one ran. Recomputing it here is what stops a row
        recording a score no rule on this row produces.
        """
        if self.headline:
            if abs(self.similarity_score - 1.0) > RECOMPUTED_TOLERANCE:
                raise ValueError(
                    "a headline match scores 1.0 outright, and this row scores "
                    f"{self.similarity_score}"
                )
            return self
        weighted = self.cosine * self.cosine_weight
        if abs(self.similarity_score - weighted) > RECOMPUTED_TOLERANCE:
            raise ValueError(
                f"similarity_score is {self.similarity_score}, and the term and weight on "
                f"this row come to {weighted}"
            )
        return self

    @model_validator(mode="after")
    def _the_pair_sits_in_a_slice_that_fits_the_thresholds_it_followed(self) -> Self:
        """The slice has width, holds the pair's own score, and agrees with its bucket.

        The slice edges are what the draw sorted the pair by, so a score outside them is a
        pair filed under another slice's chance. The thresholds are two bounds of one range,
        and each lightly sampled end stops at the threshold it lies beyond: the draw rounds
        the lower one down and the upper one up, so the end's slice never crosses it.
        """
        if self.slice_low >= self.slice_high:
            raise ValueError(
                "a slice runs from its lower edge up to its higher one, and this row's "
                f"slice runs from {self.slice_low} to {self.slice_high}"
            )
        if not self.slice_low - RECOMPUTED_TOLERANCE <= self.similarity_score <= (
            self.slice_high + RECOMPUTED_TOLERANCE
        ):
            raise ValueError(
                f"the pair scored {self.similarity_score}, which is outside the slice "
                f"{self.slice_low} to {self.slice_high} it is filed under"
            )
        if self.lower_threshold_in_force >= self.upper_threshold_in_force:
            raise ValueError(
                f"the lower threshold {self.lower_threshold_in_force} is not below the "
                f"upper threshold {self.upper_threshold_in_force}"
            )
        if (
            self.bucket is PairBucket.FULLY_DISSIMILAR
            and self.slice_high > self.lower_threshold_in_force + RECOMPUTED_TOLERANCE
        ):
            raise ValueError(
                f"a fully dissimilar pair sits below the lower threshold "
                f"{self.lower_threshold_in_force}, and its slice runs up to {self.slice_high}"
            )
        if (
            self.bucket is PairBucket.FULLY_SIMILAR
            and self.slice_low < self.upper_threshold_in_force - RECOMPUTED_TOLERANCE
        ):
            raise ValueError(
                f"a fully similar pair sits above the upper threshold "
                f"{self.upper_threshold_in_force}, and its slice starts at {self.slice_low}"
            )
        return self

    @model_validator(mode="after")
    def _the_slice_counts_nest_and_the_chance_is_their_ratio(self) -> Self:
        """Usable pairs sit inside the judged ones, inside the pool, and the chance follows.

        `sampling_chance` is derived from two counts on the same row, so a row that carries
        a chance its own counts do not give is a row whose weight nobody can reproduce. The
        usable count and the chance are filled together, never one without the other.
        """
        if self.slice_pairs_judged > self.slice_pairs_available:
            raise ValueError(
                f"the draw took {self.slice_pairs_judged} pairs from a slice that held "
                f"{self.slice_pairs_available}"
            )
        if (self.slice_pairs_usable is None) != (self.sampling_chance is None):
            raise ValueError(
                "slice_pairs_usable and sampling_chance are filled together, once the "
                "night's readings are collected"
            )
        if self.slice_pairs_usable is None or self.sampling_chance is None:
            return self
        if self.slice_pairs_usable > self.slice_pairs_judged:
            raise ValueError(
                f"{self.slice_pairs_usable} pairs were usable of the "
                f"{self.slice_pairs_judged} the draw took from the slice"
            )
        if self.readings_agree and self.slice_pairs_usable < 1:
            raise ValueError(
                "this pair's readings agree, so its slice has at least one usable pair"
            )
        chance = self.slice_pairs_usable / self.slice_pairs_available
        if abs(self.sampling_chance - chance) > RECOMPUTED_TOLERANCE:
            raise ValueError(
                f"sampling_chance is {self.sampling_chance}, and the counts on this row "
                f"give {self.slice_pairs_usable} usable over {self.slice_pairs_available} "
                f"available, which is {chance}"
            )
        return self

    @model_validator(mode="after")
    def _a_verdict_arrives_with_the_judge_that_produced_it(self) -> Self:
        """A verdict with no judge named is a label nobody can re-read.

        The four stamp columns move together: a row that names a model but no grammar says
        the verdict came from somewhere the row cannot describe. A pair no judge has read
        carries no verdict, no agreement and no grammar flag. A judged pair says whether both
        calls held the grammar, which they did exactly when both readings are valid, and
        `readings_agree` is checked here rather than trusted, because it is the flag the
        weighted totals read and a writer that set it early would count a disagreement.

        Two agreed UNCLEAR readings ARE agreed. The judge was asked and answered the same
        way twice; that the answer is "I cannot tell" is a count the night keeps rather than
        a reading it throws away.
        """
        stamp = (
            self.judge_model,
            self.prompt_digest,
            self.grammar_digest,
            self.judge_policy_version,
        )
        if any(cell is not None for cell in stamp) and any(cell is None for cell in stamp):
            raise ValueError(
                "judge_model, prompt_digest, grammar_digest and judge_policy_version are "
                "one fact in four columns, so a row carries all four or none of them"
            )
        valid = self.verdict is not None and self.verdict_swapped is not None
        agreed = valid and self.verdict == self.verdict_swapped
        if self.judge_model is None:
            if (
                self.verdict is not None
                or self.verdict_swapped is not None
                or self.readings_agree
                or self.grammar_applied is not None
            ):
                raise ValueError(
                    "a pair no judge has read carries no verdict, no agreement and no "
                    "grammar flag"
                )
            return self
        if self.grammar_applied is not valid:
            raise ValueError(
                "a judged pair says its calls held the grammar exactly when both of its "
                "readings are valid"
            )
        if self.readings_agree != agreed:
            raise ValueError("readings_agree must equal agreement between two valid readings")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader of the scratch file agree on the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A cell nothing has filled yet is an empty one."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent value, never a zero or a false.

        Only a field that defaults to empty may be read back empty, by name from the model,
        so a required cell left blank is refused rather than filled in.
        """
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        return cls.model_validate(payload)
