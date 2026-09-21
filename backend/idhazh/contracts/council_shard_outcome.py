"""How did one unit of council work end, and what did the work it hosted cost?

One row per unit of work per council run. It says whether the pipeline worked -
which units started, which finished, which stopped on their own clock - and the
aggregate cost of whatever ran inside them.

**It carries nothing that needs a name for the unit of work.** That is the whole
of the separation between the venue and its tenants: this row reads the same
whether the judge it hosted made four hundred model calls or none, so a second
tenant moving its own columns moves nothing here. A tenant's own funnel, its own
instrument readings and its own verdicts are the tenant's, in the tenant's own
store.

The outcome vocabulary is three members, because a free-text cell would split
silently on a typo - `completed` and `Completed` are two outcomes to a group-by
and one outcome to a reader. The council files the value the hosted work hands
back and never infers it, so the vocabulary is declared here rather than inside
whatever decides which member applies.

**Nothing here names a judge and nothing here needs one.** A repository with no
judge in it still imports this module, builds a row and compares every outcome.
`judge_id` is recorded rather than validated: the council writes down who ran and
never declares who may exist.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, ClassVar, Self

from pydantic import Field, StringConstraints

from idhazh.contracts.base import (
    PRINTABLE_LINE_PATTERN,
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Slug,
    Timestamp,
)

#: How long a recorded tenant slug may be. The council checks the shape of the
#: cell and nothing else, so this is the only bound the column carries.
JUDGE_ID_MAX_LENGTH = 64

#: The processor name as one printable line. Read from the kernel's own file, so
#: it is the machine's words rather than ours, and a newline in it would split
#: the row for any reader that takes a day file a line at a time.
ProcessorName = Annotated[str, StringConstraints(pattern=PRINTABLE_LINE_PATTERN, max_length=96)]


class ShardOutcome(StrEnum):
    """The three ways one unit of hosted work ends."""

    #: The unit reached the end of the work it owned.
    COMPLETED = "completed"

    #: The unit stopped itself before its deadline with work still owned.
    STOPPED_ON_DEADLINE = "stopped_on_deadline"

    #: The unit was given nothing to do. A settle that had nothing to count is
    #: this, the same as any other empty unit.
    NOTHING_TO_DO = "nothing_to_do"


class CouncilShardOutcome(Contract):
    """One unit of council work: how it ended, what it cost, and who it hosted."""

    __schema_stem__: ClassVar[str] = "council-shard-outcome"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the unit, its clock, its outcome and the hosted cost.",
            why="Nothing recorded whether the council's own pipeline worked.",
        ),
    )

    date: DateStamp = Field(description="The digest date this run judged.")
    run_id: RunId = Field(
        description="The council run, minted from the day the council ran."
    )
    judge_id: Slug = Field(
        max_length=JUDGE_ID_MAX_LENGTH,
        description=(
            "Which tenant this unit hosted. Without it a night running two tenants "
            "files rows nobody can attribute. Recorded rather than validated: there "
            "is no membership check, because the council records who ran and never "
            "declares who may exist. The value arrives from the tenant's own module "
            "constant, so a typo is a source edit a reviewer sees."
        ),
    )
    shard: int = Field(ge=0, description="Which unit of the split this row is about.")
    shards: int = Field(
        ge=1,
        description=(
            "How many units the work was split across. A run reporting fewer rows "
            "than this left work unread, and the pair alone says so."
        ),
    )
    outcome: ShardOutcome = Field(
        description=(
            "How the unit ended. A unit killed by the platform writes no row at all, "
            "and absence against the recorded count is what says so."
        )
    )
    started_at: Timestamp = Field(description="When the unit began.")
    seconds_spent: float = Field(
        ge=0,
        description=(
            "Wall clock for the unit of work. Not the job: the job's own clock "
            "includes a checkout and a weights restore this row is not about, and "
            "those are recorded where the job is."
        ),
    )
    model_calls: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many calls the hosted work made. Empty, not zero, for a tenant that "
            "runs no model - zero would read as a model that answered nothing. One "
            "call, one count, derived from no other column."
        ),
    )
    tokens_in: int | None = Field(
        default=None,
        ge=0,
        description="Prompt tokens the server reported across the unit.",
    )
    tokens_out: int | None = Field(
        default=None, ge=0, description="Generated tokens the server reported across the unit."
    )
    model_seconds: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall clock inside model calls. Read against `seconds_spent`, the two say "
            "how much of a unit was the model and how much was everything else."
        ),
    )
    host_model: ProcessorName | None = Field(
        default=None,
        description=(
            "The processor name, one line read from the kernel's own file. Without it "
            "a slow night and a slower processor read identically, and there is no "
            "join key onto what already characterises the runner pool."
        ),
    )

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A reading this unit could not take is an empty cell.

        Empty is not zero. A tenant that runs no model and a tenant whose model
        answered nothing are different facts, and only one of them is a defect.
        """
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty cell is an absent reading, never a zero.

        A column the file does not carry at all reads as an empty cell too, so a
        row written before a column existed still opens and a widening stays
        additive. Every other cell fails its own field parser by name rather than
        raising on a bare key.
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
