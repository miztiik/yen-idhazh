"""What the judge has said, slot by slot, across the band the line can move in.

A fixed row of slots and three counts in each. The record is the whole input to
the fit, so the fit reads one file of a size that never changes rather than
sorting every pair ever judged (CLAUDE.md Guardrail #12): a day is counted in
once, its counts are added, and the day tree is never read again.

`counted_dates` is what makes a re-run free. A date already on the record is
refused a second time rather than doubling its counts, so re-running a day costs
nothing instead of damaging the record.

Six stamp fields say what a count here means - which encoder, at which weights,
judged by which model, under which prompt and grammar. Change any of them and
the counts describe a different question, so the record is archived rather than
reinterpreted.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    Sha256,
    canonical_json,
    derive_text_digest,
    records_json,
    without_retired_keys,
)
from idhazh.contracts.story_similarity_pair import (
    DROPPED_CELLS,
    JudgeModelId,
    ScorerModelId,
)

#: How far off its own grid a slot edge may sit before the record is refused.
#: A band divided into 120 slots is 120 additions of a float, so the top edge
#: lands a few bits off the number a person typed without anybody having moved
#: it. A billionth is far below the width of any slot worth cutting.
GRID_TOLERANCE: Final = 1e-9


class ScoreSlot(Model):
    """One 0.001-wide slice of the band, and what the judge said inside it."""

    bin_low: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "The slot's lower edge. A pair scoring exactly this lands in this slot; a "
            "pair scoring the upper edge lands in the next one."
        ),
    )
    same_count: int = Field(
        default=0, ge=0, description="Agreed YES readings in this slot."
    )
    different_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Agreed NO readings. This is the count step 1 walks down and the only one "
            "that moves the line."
        ),
    )
    unclear_count: int = Field(
        default=0,
        ge=0,
        description=(
            "Agreed UNCLEAR readings. Counted and never fitted on, so a rising share here "
            "is visible rather than silent."
        ),
    )


class StorySimilarityDistribution(Contract):
    """The band, slot by slot, and the dates already counted into it."""

    __schema_stem__: ClassVar[str] = "story-similarity-distribution"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21T14:00",
            change="decode_digest is gone. A record that still carries the key loads.",
            why="It proved two runs asked alike, and this project does not claim that.",
        ),
        ChangelogEntry(
            version="2026-09-21T12:00",
            change="`folded_dates` is now `counted_dates`. The old key still reads.",
            why="Borrowed vocabulary for the count this field already holds.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="Added judge_temperature, decode_digest and judge_thinks, and stamped them.",
            why="Two samplers and two decode envelopes were counted as one population.",
        ),
        ChangelogEntry(
            version="2026-09-18",
            change="Initial shape: a fixed row of slots, three counts each, and the dates counted.",
            why="A fit that sorted every pair ever judged would cost more every day.",
        ),
    )

    band_low: float = Field(
        ge=0.0,
        lt=1.0,
        description=(
            "The lowest score the record holds a slot for. Below it nothing was ever "
            "judged, so the record can say nothing about it."
        ),
    )
    band_high: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "The top of the band. 1.00 is the highest a cosine goes, so the top slot is "
            "never short of room."
        ),
    )
    bin_width: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "How wide each slot is. This is the resolution of the fitted line: the fit "
            "can only ever answer to the nearest slot edge."
        ),
    )
    scorer_model: ScorerModelId | None = Field(
        default=None,
        description=(
            "Which encoder produced the scores these counts were filed under. Null until "
            "the first day is counted."
        ),
    )
    cosine_weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "What the cosine was worth for every count in this record. A different weight "
            "puts the same pair in a different slot, so a change archives the record "
            "rather than reinterpreting it."
        ),
    )
    key_point_weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="What the key-point term was worth. Same reason as the cosine weight.",
    )
    judge_model: JudgeModelId | None = Field(
        default=None,
        description="Which model produced these verdicts. Null until the first day is counted.",
    )
    prompt_digest: Sha256 | None = Field(
        default=None,
        description="sha256 of the system turn the verdicts were produced under.",
    )
    grammar_digest: Sha256 | None = Field(
        default=None,
        description="sha256 of the grammar the verdicts were produced under.",
    )
    judge_temperature: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "The sampler temperature every verdict in this record was decoded at. Null "
            "on a record written before the column existed, which is the one value it "
            "means: a sampler nobody recorded, not a sampler set to nothing."
        ),
    )
    judge_thinks: bool | None = Field(
        default=None,
        description=(
            "Whether a reasoning span ran in front of every verdict counted here. A "
            "column of its own because no other column moves with it: an envelope "
            "moves only the prompt, which nothing here stamps. Without it a record "
            "counted cold and a record counted after reasoning are one population."
        ),
    )
    counted_dates: tuple[DateStamp, ...] = Field(
        default=(),
        description=(
            "Every date already counted, sorted. A date already here is refused a second "
            "time rather than doubling its counts, which makes a re-run free instead of "
            "damaging."
        ),
    )
    slots: tuple[ScoreSlot, ...] = Field(
        description=(
            "The band, slot by slot, lowest first. Fixed size: the record never grows as "
            "the archive does, which is why the fit reads it and never the day tree "
            "(Guardrail #12)."
        )
    )

    @model_validator(mode="before")
    @classmethod
    def _the_old_key_still_reads(cls, data: Any) -> Any:
        """`folded_dates` was renamed to `counted_dates` on 2026-09-21. Both spellings load.

        Nothing but the name moved, so the old value is carried across whole. The
        model forbids unknown keys, so without this the committed record an
        earlier build wrote would be refused outright and the day list behind the
        fitted line would be lost (section 11). The next run rewrites the record
        under the new key.

        `decode_digest` is dropped here in the same pass, and the two cases are
        different: that column was deleted rather than renamed, so there is
        nothing to carry the value into. The committed record and every archive
        under `state/content-similarity-judge/archive/` still hold the key, and
        both have to keep loading.
        """
        if isinstance(data, dict) and "folded_dates" in data and "counted_dates" not in data:
            migrated = dict(data)
            migrated["counted_dates"] = migrated.pop("folded_dates")
            return without_retired_keys(migrated, *DROPPED_CELLS)
        return without_retired_keys(data, *DROPPED_CELLS)

    @model_validator(mode="after")
    def _the_band_divides_into_whole_slots(self) -> Self:
        """A band that ends mid-slot has a last slot narrower than every other one.

        Every count in it would then be drawn from a smaller catchment, and the
        fit would read a dip that is an artefact of the arithmetic rather than a
        fact about the judge.
        """
        span = self.band_high - self.band_low
        slots = span / self.bin_width
        remainder = abs(slots - round(slots))
        if remainder > GRID_TOLERANCE:
            raise ValueError(
                f"a band of {span} does not divide into whole slots of {self.bin_width}: "
                f"it leaves {remainder * self.bin_width} over"
            )
        return self

    @model_validator(mode="after")
    def _the_slot_count_matches_the_band(self) -> Self:
        """The band and the slots are one fact written twice, so they have to agree.

        A validator rather than a `min_length` on the field: the count is
        derived from three other numbers on this record, and a class-level bound
        would be a fourth number nobody can keep in step with them.
        """
        expected = round((self.band_high - self.band_low) / self.bin_width)
        if len(self.slots) != expected:
            raise ValueError(
                f"a band of {self.band_low} to {self.band_high} at {self.bin_width} is "
                f"{expected} slots, and this record carries {len(self.slots)}"
            )
        for index, slot in enumerate(self.slots):
            edge = self.band_low + index * self.bin_width
            if abs(slot.bin_low - edge) > GRID_TOLERANCE:
                raise ValueError(
                    f"slot {index} opens at {slot.bin_low}, and the grid puts its edge "
                    f"at {edge}"
                )
        return self

    @model_validator(mode="after")
    def _a_date_is_counted_once(self) -> Self:
        """A repeated date is a day counted twice, which no later read can undo."""
        dates = list(self.counted_dates)
        if dates != sorted(dates):
            raise ValueError("counted_dates is kept sorted, so a reader can scan it")
        if len(set(dates)) != len(dates):
            repeated = sorted({date for date in dates if dates.count(date) > 1})
            raise ValueError(f"counted_dates already holds {', '.join(repeated)}")
        return self

    def record_stamp(self) -> str:
        """Everything that decides what a count in this record means.

        **The read-side migration for the two decode values is this method.**
        A record written before they existed carries them null, loads under this
        build, and stamps to a value it never stamped to - so the first day
        counted after the widening archives it and counts on from zero. That
        reset is by construction rather than by an input moving, it happens once,
        and it is the price of the two populations this record used to merge in
        silence.

        **A value leaving moves the stamp the same way.** `decode_digest` was in
        this payload until 2026-09-21, so the first record counted after that
        archives under its old name and the new one starts empty. Nothing ever
        re-derives an archive's name, so every file already written stays
        readable under the name it has.
        """
        payload: dict[str, Any] = {
            "band_high": self.band_high,
            "band_low": self.band_low,
            "bin_width": self.bin_width,
            "cosine_weight": self.cosine_weight,
            "grammar_digest": self.grammar_digest,
            "judge_model": self.judge_model,
            "judge_temperature": self.judge_temperature,
            "judge_thinks": self.judge_thinks,
            "key_point_weight": self.key_point_weight,
            "prompt_digest": self.prompt_digest,
            "scorer_model": self.scorer_model,
        }
        return derive_text_digest(canonical_json(payload))

    def to_json(self) -> str:
        """One slot a line - see `records_json`."""
        return records_json(self.model_dump(mode="json"))
