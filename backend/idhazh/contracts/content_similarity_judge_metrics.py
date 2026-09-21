"""How did this judge's own instrument behave over one unit of work?

One row per shard per council run. It says what the selection dealt the shard,
how much of that got a reading, what the readings looked like, and what they
cost - the judge's own funnel, its own rates and its own clocks.

**Every column here is this judge's own.** A second judge declares its own
contract and shares none of them. The council's record beside this one says
whether the pipeline worked; this one says whether the instrument did, and the
two never meet in a column. A reading may be compared across two judges only
when it is a count or a clock.

**It inherits the config stamp and not a per-call one.** A shard has no single
call, so a per-call grammar flag, a per-call probability window and a per-call
clock have nothing to point at here. The three shard-level equivalents are
`pairs_refused`, `first_token_margin_median` and the two decode totals.

**The funnel closes, and a validator is what holds it closed.** The four terms
added together are what the shard was dealt, and the abandoned term is one of
them - without it the identity goes red on exactly the shard that stopped on its
own deadline, which is the shard this row exists to let report at all.

**A rate over no rows is empty rather than zero.** An empty shard measured
nothing, and a zero there reads as a shard that measured everything and found
nothing wrong. Those are opposite facts.

**This row is a record and never an alarm.** The line-setting gates already fire
on the day-grain rates, and a second threshold here would be an answer nobody
could reconcile with the first.

The store is `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv`. The
directory name is spelled in `idhazh.ledger`, which is where a path belongs and
which this module may not import (CLAUDE.md section 4).
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId
from idhazh.contracts.judge_call import JudgeConfigStamp
from idhazh.contracts.story_similarity_pair import JudgeModelId

#: The slug column of this judge's own rows, closed to the one member that can
#: ever write them. A closed set is honest here in the way it could not be on the
#: shared stamp: that stamp is inherited by judges nobody has written yet, and
#: this store holds one judge's readings and no other's.
ContentSimilarityJudgeId = Literal["content-similarity-judge"]


class ContentSimilarityJudgeMetrics(JudgeConfigStamp, Contract):
    """One shard of one night: what this judge was dealt, what it read, what it cost."""

    __schema_stem__: ClassVar[str] = "content-similarity-judge-metrics"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the shard's funnel, its two rates, its margin and its clocks.",
            why="Nothing recorded how this judge's own instrument behaved over a shard.",
        ),
    )

    judge_id: ContentSimilarityJudgeId = Field(
        default="content-similarity-judge",
        description=(
            "Which instrument wrote this reading. One member, because this store holds "
            "the readings of one judge and no other - so the column is narrowed here, "
            "where a closed set can be closed honestly."
        ),
    )
    judge_model: JudgeModelId | None = Field(
        default=None,
        description=(
            "Which weights judged. Narrowed to the sets this repository ships a model "
            "file for, so swapping the judge is a schema diff rather than a silent "
            "change in what a reading means. Empty where no model ran."
        ),
    )

    date: DateStamp = Field(description="The digest date judged.")
    run_id: RunId = Field(description="The council run this shard belonged to.")
    shard: int = Field(ge=0, description="Which unit of the split this row is about.")
    pairs_dealt: int = Field(
        ge=0, description="How many pairs the selection gave this shard."
    )
    pairs_read: int = Field(
        ge=0, description="How many of them got a reading inside the grammar."
    )
    pairs_agreed: int = Field(
        ge=0,
        description=(
            "How many read pairs answered the same way in both orders. A subset of the "
            "pairs read, never of the pairs dealt."
        ),
    )
    pairs_unreadable: int = Field(
        ge=0,
        description=(
            "How many pairs the window no longer reaches, because the day either item "
            "was published on has aged out."
        ),
    )
    pairs_refused: int = Field(
        ge=0,
        description=(
            "How many pairs came back outside the grammar. Pairs rather than calls: a "
            "pair is two calls, so counting calls would count a pair that failed twice "
            "twice and put the funnel out on a real event rather than on a defect."
        ),
    )
    pairs_abandoned: int = Field(
        ge=0,
        description=(
            "How many pairs this shard owned and never reached, because it stopped on "
            "its own deadline. A column of its own so the funnel still closes on the "
            "shard the deadline exists to let report."
        ),
    )
    disagreement_rate: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "What share of the pairs read answered differently in the two orders. Empty "
            "when nothing was read, because a rate over no rows is not zero. Per shard "
            "over pairs read, where the line-setting gate is per day over pairs agreed - "
            "two different quantities."
        ),
    )
    unclear_rate: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "What share of the pairs agreed answered UNCLEAR. Empty on a shard that "
            "agreed nothing, for the reason above, and per shard for the reason above."
        ),
    )
    first_token_margin_median: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "The median gap at the deciding position, over the three verdict openings. "
            "Not comparable to another judge's reading: a flat distribution means the "
            "grammar chose here, and a legitimate middle score for a judge whose "
            "distribution is the answer."
        ),
    )
    decode_seconds_total: float | None = Field(
        default=None,
        ge=0,
        description=(
            "How long the shard's calls took, added up. Empty where no call was made."
        ),
    )
    decode_seconds_max: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The longest single call. A shard with an ordinary total and a bad worst "
            "call is the one that runs out of clock next, and the total alone hides it."
        ),
    )

    @model_validator(mode="after")
    def _the_funnel_closes(self) -> Self:
        """Every pair dealt was read, refused, unreachable or never got to.

        The four terms are one funnel written in four columns, and a row where
        they do not add up to what the shard was dealt is a row whose arithmetic
        nobody can reproduce - every rate read off it would then be a share of a
        denominator that means nothing.
        """
        accounted = (
            self.pairs_read + self.pairs_refused + self.pairs_unreadable + self.pairs_abandoned
        )
        if accounted != self.pairs_dealt:
            raise ValueError(
                f"pairs_dealt is {self.pairs_dealt} and the shard accounts for {accounted} "
                "(read, refused, unreadable, abandoned). Every pair dealt has exactly one "
                "of those four endings."
            )
        if self.pairs_agreed > self.pairs_read:
            raise ValueError(
                f"pairs_agreed is {self.pairs_agreed} over {self.pairs_read} read. A pair "
                "agrees only if both of its readings arrived."
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A reading this shard could not take is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent reading, never a zero.

        A column the file does not carry at all reads as an empty cell too, so a
        row written before a column existed still opens and a widening stays
        additive.
        """
        payload: dict[str, Any] = dict.fromkeys(cls.model_fields, "") | dict(row)
        for name in cls._absent_when_blank():
            if payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)

    @classmethod
    def _absent_when_blank(cls) -> tuple[str, ...]:
        """Every optional cell, derived rather than listed a second time."""
        return tuple(name for name, field in cls.model_fields.items() if field.default is None)
