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

**The first shape of this record is still read, and never written.** It filed
a step under one number, `shard` - -1 for picking the work, -2 for combining
the results, and a part's own number from 0 - and the count of parts as
`shards`. `from_csv_row` reads every such row into a step and a part, and
refuses a row it cannot place rather than guess.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any, ClassVar, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Slug, Timestamp
from idhazh.contracts.council_shard_outcome import JUDGE_ID_MAX_LENGTH, ShardOutcome


class EvaluationStep(StrEnum):
    """The three steps of a council night, in the order a night runs them."""

    #: Pick the work for one date. It runs once a date, so it has no part.
    SELECT_JUDGE_WORK = "select_judge_work"

    #: Judge one part of the split work. The one step that has a part.
    EVALUATE_WORK_PART = "evaluate_work_part"

    #: Combine what the parts sent back for one date. It runs once a date.
    COMBINE_JUDGE_RESULTS = "combine_judge_results"


#: The first shape's two headings, and the field each is read into. `shard` also
#: named the step, which `from_csv_row` reads off the same cell.
OLD_HEADINGS: Final[Mapping[str, str]] = MappingProxyType(
    {"shard": "work_part_index", "shards": "work_part_count"}
)

#: The two numbers the first shape filed the once-a-date steps under: below zero,
#: so that neither could be taken for a part.
_ONCE_A_DATE_STEPS: Final[Mapping[str, EvaluationStep]] = MappingProxyType(
    {"-1": EvaluationStep.SELECT_JUDGE_WORK, "-2": EvaluationStep.COMBINE_JUDGE_RESULTS}
)


def _in_the_current_shape(row: Mapping[str, str]) -> dict[str, str]:
    """A row's cells, with a first-shape row's step and part read off its `shard` cell.

    -1 picked the work and -2 combined the results, so neither has a part, and a
    number from 0 up was the part itself. Any other value, an empty one included,
    names no step and is refused naming the cell. An old heading beside a filled
    cell of the current shape is one row in two shapes, refused rather than read
    either way. A row in the current shape comes back as it arrived.
    """
    old = [name for name in OLD_HEADINGS if name in row]
    if not old:
        return dict(row)
    beside = [name for name in ("evaluation_step", *OLD_HEADINGS.values()) if row.get(name)]
    if beside:
        raise ValueError(f"one row in two shapes: {old} beside a filled {beside}")
    number = row.get("shard", "")
    if number in _ONCE_A_DATE_STEPS:
        step, part = _ONCE_A_DATE_STEPS[number], ""
    elif number.isascii() and number.isdigit():
        step, part = EvaluationStep.EVALUATE_WORK_PART, number
    else:
        raise ValueError(
            f"shard {number!r} names no step: the first shape filed -1, -2 or a part from 0"
        )
    cells = {name: value for name, value in row.items() if name not in OLD_HEADINGS}
    return cells | {
        "evaluation_step": step.value,
        "work_part_index": part,
        "work_part_count": row.get("shards", ""),
    }


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
        """The inverse, and the reader of every row the first shape filed.

        An empty cell is an absent value, never a zero, and a column the row does
        not carry reads as an empty cell. Every other heading reaches the model as
        it arrived, so a heading no field declares is refused rather than dropped.
        """
        payload: dict[str, Any] = dict.fromkeys(cls.model_fields, "") | _in_the_current_shape(row)
        for name, field in cls.model_fields.items():
            if payload[name] == "" and field.default is None:
                payload[name] = None
        return cls.model_validate(payload)
