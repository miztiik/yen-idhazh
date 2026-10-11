"""Which closed facts may a council program write to its event log?"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, computed_field

from idhazh.contracts.base import DateStamp, Model, RunId, Slug
from idhazh.contracts.council_run_record import EvaluationStep, ShardOutcome
from idhazh.contracts.knobs.council import JudgeLifecycleStatus

# These grammars name code, never messages, paths, source lines or exception notes.
ErrorName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$", max_length=128)]
CodePlace = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_.]*:[0-9]+$", max_length=256)
]


class CouncilExit(IntEnum):
    """The council's fixed exit vocabulary, not a publisher's internal status."""

    OK = 0
    FAILED = 1
    REFUSED = 2
    PUSH_REFUSED = 3

    @property
    def label(self) -> str:
        return {
            self.OK: "ok",
            self.FAILED: "failed",
            self.REFUSED: "refused",
            self.PUSH_REFUSED: "push_refused",
        }[self]

    @property
    def sentence(self) -> str:
        return {
            self.OK: "every unit finished and the rows landed",
            self.FAILED: "a unit failed, or the rows did not land (stale or lost)",
            self.REFUSED: "stopped before any unit ran",
            self.PUSH_REFUSED: "main refused every push, so nothing landed",
        }[self]


class CouncilProgram(StrEnum):
    """The council entrypoints that share one exit vocabulary."""

    IDENTITY = "run-identity"
    PLAN = "night-plan"
    MATRIX = "matrix"
    PREPARE = "prepare"
    SHARD = "shard"
    SETTLE = "settle"
    PUBLISH = "publish"


class JudgeDeclared(Model):
    """One registered judge's committed status, before code is resolved."""

    judge_id: Slug
    status: JudgeLifecycleStatus
    runs_model: bool


class NightPlanned(Model):
    """The bounded dates and unit counts this invocation plans."""

    dates: tuple[DateStamp, ...]
    judges: int | None = Field(default=None, ge=0)
    units: int | None = Field(default=None, ge=0)


class RunIdentified(Model):
    """The identity minted for one UTC night."""

    run_id: RunId


class UnitFinished(Model):
    """One attempted unit's result, including a raised or row-filing failure."""

    date: DateStamp
    run_id: RunId
    judge_id: Slug
    evaluation_step: EvaluationStep
    work_part_index: int | None = Field(default=None, ge=0)
    work_part_count: int = Field(ge=1)
    outcome: ShardOutcome | Literal["failed"]
    error: ErrorName | None = None
    where: CodePlace | None = None


class RowsCollected(Model):
    """How many existing council records were collected for one date."""

    date: DateStamp
    rows: int = Field(ge=0)


class NightPublished(Model):
    """The publisher's closed result, without its diagnostic text or file paths."""

    dates: tuple[DateStamp, ...]
    run_id: RunId
    landing: Literal[
        "landed",
        "already-on-main",
        "no-changes",
        "stale",
        "lost",
        "integrity-refused",
        "refused",
        "preparation-failure",
    ]
    pushes: int = Field(ge=0)
    writes: int = Field(ge=0)
    code: CouncilExit


class Diagnostic(Model):
    """A non-event log or caught exception with its text omitted at the boundary."""

    kind: Literal["log", "exception", "refusal"]
    error: ErrorName | None = None
    where: CodePlace | None = None


class ProgramFinished(Model):
    """The code, label and fixed sentence printed together for an entrypoint."""

    program: CouncilProgram
    code: CouncilExit

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        return self.code.label

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sentence(self) -> str:
        return self.code.sentence
