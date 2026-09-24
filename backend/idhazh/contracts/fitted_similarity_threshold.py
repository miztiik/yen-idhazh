"""What the line was, what the evidence proposed, and what the run actually applied.

One row a run. A row is written on the days the line moved AND on the days it did
not - a line that moves itself has to leave a record on the days it stayed put, or
a reader cannot tell a held day from a day nothing ran.

The steps are readable straight off the row: `proposed` is what the record said,
`after_damping` is that proposal damped towards yesterday - or yesterday's line
unchanged, on a day the proposal sat inside the dead zone and counted as no move
at all - `applied` is what the caps and the band walls let through, and
`clamp_kind` says which of them shaped it. The three gates are on the row too, as
counts rather than as a verdict, so a held day says why it was held in numbers a
person can check.

Nothing here is a model verdict. The fit is arithmetic over counts, and the row
records the arithmetic (CLAUDE.md section 0a).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    without_retired_keys,
)
from idhazh.contracts.story_similarity_pair import JudgeModelId, ScorerModelId

#: Headings a committed day file still carries that this row no longer names and
#: that nothing replaced. `key_point_weight` went with the key points
#: themselves: the term shipped at a weight of 0.0, so it never moved a fit.
#:
#: **This is a contract, not a courtesy.** `ledger.migrate_header` refuses any
#: heading that is neither a current column nor one the reader carries, so a
#: column deleted below without an entry here leaves every committed day file
#: unrepairable. `ledger.keyed_paths` hands this set to that repair.
DROPPED_CELLS: Final[frozenset[str]] = frozenset({"key_point_weight"})

#: How far two lines may sit apart and still count as the same line. The applied
#: value is a difference of floats on a 0-to-1 scale, so a held row's "applied
#: equals previous" has to survive one subtraction. A billionth is far below the
#: 0.001 resolution any fitted line is read at.
LINE_TOLERANCE: Final = 1e-9


class ClampKind(StrEnum):
    """What shaped the applied value, in one word.

    `CEILING` and `FLOOR` are where the line came to rest on a band wall, whether
    or not the wall moved it that day. A line at `band_high` folds nothing at all
    and a line at `band_low` folds everything in the band; both look from the
    outside like the feature is switched off, so both get a word of their own
    rather than reading as `NONE`.
    """

    NONE = "none"
    STEP = "step"
    GUARD = "guard"
    CEILING = "ceiling"
    FLOOR = "floor"


class HeldReason(StrEnum):
    """Why no fit ran today. `NONE` means one did."""

    NONE = "none"
    SHEET_TOO_SMALL = "sheet_too_small"
    INPUTS_CHANGED = "inputs_changed"
    JUDGE_UNSTABLE = "judge_unstable"
    JUDGE_UNCERTAIN = "judge_uncertain"
    SHARDS_MISSING = "shards_missing"

    @classmethod
    def _missing_(cls, value: object) -> HeldReason | None:
        """`legs_missing` was renamed to `shards_missing` on 2026-09-21.

        The ledger is append-only, so a row a run wrote under the old spelling
        has to keep reading. Nothing but the name moved.
        """
        if value == "legs_missing":
            return cls.SHARDS_MISSING
        return None


class FittedSimilarityThreshold(Contract):
    """One run's fit: the five steps, the gates, and what the record held when they ran."""

    __schema_stem__: ClassVar[str] = "fitted-similarity-threshold"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-24",
            change="key_point_weight is gone. Its heading is carried and dropped on read.",
            why="The term shipped at a weight of zero and never moved a score.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="held_reason `legs_missing` is now `shards_missing`. The old value still reads.",
            why="`leg` was a second name for the shard the rest of this feature already names.",
        ),
        ChangelogEntry(
            version="2026-09-19",
            change="smoothing_weight splits into fall_weight and rise_weight; max_up_step added.",
            why="The line now damps and caps both directions, so one number cannot carry it.",
        ),
        ChangelogEntry(
            version="2026-09-18T12:00",
            change="pairs_in_band counts the pairs the draw dealt, not the pairs in the band.",
            why="The count before the budget is persisted nowhere, so nothing could write it.",
        ),
        ChangelogEntry(
            version="2026-09-18",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
        ),
    )

    date: DateStamp = Field(description="The digest date this fit was run for.")
    run_id: RunId = Field(description="The run that fitted the line.")
    record_stamp: Sha256 = Field(
        description=(
            "Which record this fit read: a digest of the band, the slot width and both "
            "model stamps. A later reader can tell two rows apart that were fitted either "
            "side of an archive."
        )
    )
    previous: float = Field(
        ge=0.0,
        le=1.0,
        description="The line that was applied yesterday. Where today started.",
    )
    proposed: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "What step 1 read off the record before damping or clamping. The raw "
            "evidence. Empty on a held day, because no fit ran and there is nothing to "
            "report."
        ),
    )
    after_damping: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "The proposal after damping. Both directions are damped, so this differs from "
            "the proposal on a rise as well as on a fall - and equals the previous line "
            "when the proposal sat inside the dead zone and the day counted as no move. "
            "Empty whenever the proposal is, since there is nothing to damp."
        ),
    )
    applied: float = Field(
        ge=0.0,
        le=1.0,
        description="The line this run wrote. What assemble will read once row 9 lands.",
    )
    clamp_kind: ClampKind = Field(
        default=ClampKind.NONE,
        description=(
            "What shaped the applied value. none is the damped proposal as it stood, step "
            "is a daily cap, guard is the step-change hold, and ceiling or floor is the "
            "line resting on a band wall. Which way a step went is read off previous "
            "against applied."
        ),
    )
    clamp_movement: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "How far the clamp held the line back. A distance, so it is at or above zero "
            "whichever direction was held. Zero when nothing clamped, and zero on a "
            "ceiling or floor row where the line was already resting on the wall."
        ),
    )
    held_reason: HeldReason = Field(
        default=HeldReason.NONE,
        description=(
            "Why no fit ran today. none means one ran. A held row carries the previous "
            "line unchanged and every count that explains the hold."
        ),
    )
    settled: bool = Field(
        default=False,
        description=(
            "Whether a whole week of fresh judgements stopped moving the answer. Judging "
            "drops to weekly while this is true and returns to daily on its own."
        ),
    )
    discard_share: float = Field(
        gt=0.0,
        lt=0.5,
        description=(
            "What share of the record's NO readings step 1 walked past before it stopped. "
            "On the row because a later reader comparing two fits has to know both were "
            "asked the same question."
        ),
    )
    fall_weight: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "How much of a downward move the damping let through against yesterday's line. "
            "On the row for the same reason the discard share is: a later reader comparing "
            "two fits has to know both were asked the same question."
        ),
    )
    rise_weight: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "How much of an upward move the damping let through. Smaller than the fall "
            "weight on every legal config, because the line falls fast and rises slow."
        ),
    )
    max_down_step: float = Field(
        gt=0.0,
        description=(
            "The furthest the line could fall in one day, in score units. On the row "
            "because clamp_kind says a cap fired and this says what it fired against."
        ),
    )
    max_up_step: float = Field(
        gt=0.0,
        description=(
            "The furthest the line could rise in one day, in score units. On the row for "
            "the same reason the fall cap is."
        ),
    )
    step_change_multiple: float = Field(
        gt=1.0,
        description=(
            "How many times the typical daily shift today's shift had to beat before the "
            "guard held the line. On the row for the same reason the daily step is."
        ),
    )
    daily_shift: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "How far today alone moved the answer: the fit with today against the fit "
            "without it. Empty when either fit has no NO verdicts to walk, because a "
            "subtraction with one side missing is not a zero."
        ),
    )
    typical_shift: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "The median daily shift over the last fourteen written rows. Empty until "
            "fourteen exist, which is how a reader sees the guard is still filling. A "
            "median rather than a sigma, because the daily shift shrinks as 1/days and is "
            "not normally distributed."
        ),
    )
    pairs_in_band: int = Field(
        ge=0,
        description=(
            "How many distinct pairs the day file holds - what the draw dealt the shards, "
            "after pair_budget cut the band down. Equal to the budget on a day that hit "
            "the cap, which is how a truncated day reads as partial rather than as a quiet "
            "one. The count before the budget is not persisted anywhere, so no writer "
            "could put it here."
        ),
    )
    pairs_judged: int = Field(
        ge=0, description="How many pairs a judging shard actually read."
    )
    pairs_usable: int = Field(
        ge=0,
        description=(
            "How many of those got two agreeing readings. Only these were counted."
        ),
    )
    disagreement_rate: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "What share of the judged pairs the two readings disagreed about. One of the "
            "three gates, and the one that reads the judge rather than the record."
        ),
    )
    unclear_rate: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "What share of the agreed readings were UNCLEAR. A judge that cannot tell is "
            "not a judge the line should move on."
        ),
    )
    negatives_on_record: int = Field(
        ge=0,
        description=(
            "Agreed NO readings the whole record holds. One of the three gates, and the "
            "one that takes longest to fill."
        ),
    )
    above_line_on_record: int = Field(
        ge=0,
        description=(
            "Judged pairs at or above the applied line. These are the entire precision "
            "measurement, so they are never sampled away."
        ),
    )
    days_on_record: int = Field(
        ge=0, description="How many dates the record has counted."
    )
    merge_count: int = Field(
        ge=0,
        description=(
            "How many groups the day published. The one number in this feature that "
            "involves no model."
        ),
    )
    scorer_model: ScorerModelId = Field(
        description="Which encoder produced the scores this fit was read off."
    )
    cosine_weight: float = Field(
        ge=0.0,
        le=1.0,
        description="What the cosine was worth in the record this fit read.",
    )
    judge_model: JudgeModelId | None = Field(
        default=None,
        description=(
            "Which model produced the verdicts this fit read. Empty on a held day whose "
            "record has never counted a date."
        ),
    )
    prompt_digest: Sha256 | None = Field(
        default=None,
        description="sha256 of the system turn those verdicts were produced under.",
    )
    grammar_digest: Sha256 | None = Field(
        default=None,
        description="sha256 of the grammar those verdicts were produced under.",
    )

    @model_validator(mode="after")
    def _the_counts_nest(self) -> Self:
        """A day cannot judge more pairs than it drew, or use more than it judged.

        The three counts are one funnel written in three columns, and a row where
        they do not nest is a row whose arithmetic nobody can reproduce - the
        gate that reads them would then pass or fail on a number that means
        nothing.
        """
        if not self.pairs_usable <= self.pairs_judged <= self.pairs_in_band:
            raise ValueError(
                f"the counts do not nest: {self.pairs_usable} usable of "
                f"{self.pairs_judged} judged of {self.pairs_in_band} in the band"
            )
        return self

    @model_validator(mode="after")
    def _the_words_agree_with_the_numbers(self) -> Self:
        """A row says what happened in words and in numbers, so the two have to match.

        This is the one validator that earns its place: the words are what a
        reader scans and the numbers are what a later fit reads, and a row where
        a `held_reason` sits beside a moved line is a row that lies to one of
        them. Every clause here is a shape the five steps cannot produce.
        """
        if self.held_reason is not HeldReason.NONE:
            if self.clamp_kind is not ClampKind.NONE:
                raise ValueError(
                    f"held_reason is {self.held_reason.value}, so no fit ran and nothing "
                    f"could be clamped, but clamp_kind is {self.clamp_kind.value}"
                )
            if abs(self.applied - self.previous) > LINE_TOLERANCE:
                raise ValueError(
                    f"held_reason is {self.held_reason.value}, so the line stays at "
                    f"{self.previous}, and this row applied {self.applied}"
                )
            if self.clamp_movement != 0.0:
                raise ValueError("a held row clamped nothing, so clamp_movement is 0.0")
            if self.proposed is not None or self.after_damping is not None:
                raise ValueError("a held row ran no fit, so it carries no proposal")
            return self
        if self.proposed is None or self.after_damping is None:
            raise ValueError(
                "held_reason is none, so a fit ran and the row carries both the proposal "
                "and the damped proposal"
            )
        if self.clamp_kind is ClampKind.GUARD:
            if abs(self.applied - self.previous) > LINE_TOLERANCE:
                raise ValueError(
                    f"the guard holds the line at {self.previous}, and this row applied "
                    f"{self.applied}"
                )
            return self
        if self.clamp_kind is ClampKind.NONE:
            if self.clamp_movement != 0.0:
                raise ValueError(
                    "clamp_kind is none, so nothing was held back and clamp_movement is 0.0"
                )
            return self
        held_back = abs(self.applied - self.after_damping)
        if abs(self.clamp_movement - held_back) > LINE_TOLERANCE:
            raise ValueError(
                f"clamp_movement is {self.clamp_movement}, and the clamp moved the line "
                f"{held_back} from {self.after_damping} to {self.applied}"
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        return tuple(cls.model_fields)

    @model_validator(mode="before")
    @classmethod
    def _without_the_columns_this_row_stopped_naming(cls, data: Any) -> Any:
        """The read-side migration `CLAUDE.md` section 11 owes a removed column.

        The keys come from `DROPPED_CELLS`, which `ledger.keyed_paths` also hands
        the header repair, so the CSV side and the JSON side cannot name
        different sets.
        """
        return without_retired_keys(data, *DROPPED_CELLS)

    def csv_row(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        payload: dict[str, Any] = {name: row.get(name, "") for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        payload["settled"] = row.get("settled", "") == "True"
        return cls.model_validate(payload)
