"""Which step of a council night does this row record, and how did that step end?

One row per step, per tenant, per council run. A night runs three steps for each
tenant it hosts: it picks the work for a date, judges each part of the split,
and combines what the parts sent back. A row names its step and, on a part,
which part it is and how many there were - so a part that never reported is a
row missing against the count its siblings carry.

**It carries nothing that needs a name for the work itself.** The row reads the
same whether the tenant it hosted made four hundred model calls or none, so a
tenant moving its own columns moves nothing here. A tenant's own funnel,
readings and verdicts are the tenant's, in the tenant's own ledger.

**No field here is called `shard`.** The ledger door writes a `shard` cell on
every row it files, meaning the shard of the job that filed it, and a row field
of that name would take that cell's place. So a step is a word and a part is an
index, and neither can be read as the job that saved them.

"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Slug, Timestamp

# The council records any tenant name it hosts; this bound keeps the row narrow.
JUDGE_ID_MAX_LENGTH = 64


class ShardOutcome(StrEnum):
    """The three ways one unit of hosted work ends."""

    #: The unit reached the end of the work it owned.
    COMPLETED = "completed"

    #: The unit stopped itself before its deadline with work still owned.
    STOPPED_ON_DEADLINE = "stopped_on_deadline"

    #: The unit was given nothing to do.
    NOTHING_TO_DO = "nothing_to_do"


class EvaluationStep(StrEnum):
    """The three steps of a council night, in the order a night runs them."""

    #: Pick the work for one date. It runs once a date, so it has no part.
    SELECT_JUDGE_WORK = "select_judge_work"

    #: Judge one part of the split work. The one step that has a part.
    EVALUATE_WORK_PART = "evaluate_work_part"

    #: Combine what the parts sent back for one date. It runs once a date.
    COMBINE_JUDGE_RESULTS = "combine_judge_results"


class CouncilRunRecord(Contract):
    """One step of council work for one tenant: which step, how it ended, what it cost."""

    __schema_stem__: ClassVar[str] = "council-run-record"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-04",
            change="Step and part fields replace `shard` and `shards`, and `host_model` goes.",
            why="The door's own `shard` cell names the filing job; nothing filled `host_model`.",
        ),
        ChangelogEntry(
            version="2026-09-21T12:00",
            change="`shard` carries two reserved values below zero.",
            why="The two units that run once a date could not file a row at all.",
        ),
        ChangelogEntry(
            version="2026-09-21",
            change="Initial shape: the unit, its clock, its outcome and the hosted cost.",
            why="Nothing recorded whether the council's own pipeline worked.",
        ),
    )

    date: DateStamp = Field(description="The digest date the step worked on, as a UTC day.")
    run_id: RunId = Field(
        description=(
            "The council run the step belongs to, minted once in the run's planning job "
            "from the UTC day the council ran. Every row of one night carries it."
        )
    )
    judge_id: Slug = Field(
        max_length=JUDGE_ID_MAX_LENGTH,
        description=(
            "Which tenant the step hosted. Recorded rather than checked against a list: "
            "the council writes down who ran and never declares who may exist."
        ),
    )
    evaluation_step: EvaluationStep = Field(
        description="Which of the night's three steps this row is about."
    )
    work_part_index: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Which part of the split the step judged, from 0. Empty on the two steps "
            "that run once a date, because neither has a part."
        ),
    )
    work_part_count: int = Field(
        ge=1,
        description=(
            "How many parts the date's work was split into. Every row of a date carries "
            "it, so fewer part rows than this is a part that never reported."
        ),
    )
    outcome: ShardOutcome = Field(
        description=(
            "How the step ended. A step the platform killed files no row at all, and the "
            "row missing against the count is what says so."
        )
    )
    started_at: Timestamp = Field(description="When the step began, in UTC.")
    seconds_spent: float = Field(
        ge=0,
        description=(
            "Wall clock for the step itself. Not the job: a job's checkout and weights "
            "restore are recorded where the job is."
        ),
    )
    model_calls: int | None = Field(
        default=None,
        ge=0,
        description=(
            "How many calls the hosted work made. Empty, not zero, for a tenant that runs "
            "no model: zero would read as a model that answered nothing."
        ),
    )
    tokens_in: int | None = Field(
        default=None, ge=0, description="Prompt tokens the server reported across the step."
    )
    tokens_out: int | None = Field(
        default=None, ge=0, description="Generated tokens the server reported across the step."
    )
    model_seconds: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Wall clock inside model calls. Read against `seconds_spent`, the two say how "
            "much of a step was the model and how much was everything else."
        ),
    )

    @model_validator(mode="after")
    def _a_part_is_named_only_where_the_work_was_split(self) -> Self:
        """A once-a-date step has no part, and a part sits inside the count its row carries."""
        if (self.evaluation_step is EvaluationStep.EVALUATE_WORK_PART) != (
            self.work_part_index is not None
        ):
            raise ValueError(
                "work_part_index is filled exactly when evaluation_step is "
                f"{EvaluationStep.EVALUATE_WORK_PART.value}"
            )
        if self.work_part_index is not None and self.work_part_index >= self.work_part_count:
            raise ValueError(
                f"work_part_index {self.work_part_index} is not below "
                f"work_part_count {self.work_part_count}"
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """One definition, so a writer and a reader cannot disagree about the shape."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, and an absent value an empty cell.

        Empty is not zero. A tenant that runs no model and a tenant whose model
        answered nothing are different facts, and only one of them is a defect.
        """
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse of the council's current shipped CSV row.

        An empty cell is an absent value, never a zero, and a column the row does
        not carry reads as an empty cell. Every other heading reaches the model as
        it arrived, so a heading no field declares is refused rather than dropped.
        """
        payload: dict[str, Any] = dict.fromkeys(cls.model_fields, "") | row
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        return cls.model_validate(payload)
