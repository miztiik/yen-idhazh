"""One row of the model validation ledger, filed on the day the run measured.

The leaderboard's ranking is a better prior than a guess. It is not evidence
about this pipeline, because three variables sit between their number and ours:
their prompt, their extraction, and their corpus. This row records both numbers
side by side so the gap is a fact rather than an argument.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, DateStamp, RunId, Sha256, Slug


class ValidationVerdict(StrEnum):
    """What the decision rule concluded. Never a free-text judgement."""

    CONFIRMED = "confirmed"
    RESCORE_CANDIDATES = "rescore_candidates"
    SWITCH_AND_PAUSE = "switch_and_pause"
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"


class LeaderboardProvenance(StrEnum):
    """Whether anybody published a number for this model, on this task.

    `not_reported` is not zero. A model whose card publishes no summarization or
    faithfulness result has an unknown prior, and recording that as `0.0` would
    put a fabricated worst case into every mean, chart and comparison that ever
    reads the column (Guardrail #10).
    """

    REPORTED = "reported"
    NOT_REPORTED = "not_reported"


class ValidationRow(Contract):
    """One candidate model, scored end to end through our own pipeline."""

    __schema_stem__: ClassVar[str] = "validation-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-18",
            change="Renamed `measured_on` to `date` and appended `run_id`.",
            why="The head is named by the row's date cell, and two runs of a day are two verdicts.",
        ),
        ChangelogEntry(
            version="2026-08-26",
            change="leaderboard_hhem may be null beside a leaderboard_provenance of not_reported.",
            why="A single-model qualification has no incumbent to compare against.",
        ),
        ChangelogEntry(
            version="2026-08-22",
            change="Initial shape: the incumbent and its challengers, measured and predicted.",
            why="An escalation gate's inputs and verdict have to be a persisted record.",
        ),
    )

    model_id: Slug
    is_incumbent: bool = Field(
        description="The model currently configured. Exactly one row per run carries this."
    )
    selected: bool = Field(
        description="The model this run would run with. On a confirmed run, the incumbent."
    )
    leaderboard_hhem: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="What the published leaderboard says. A prior, never evidence about us.",
    )
    leaderboard_provenance: LeaderboardProvenance = Field(
        default=LeaderboardProvenance.REPORTED,
        description="Whether a published number exists at all. Missing stays missing.",
    )
    measured_hhem: float = Field(
        ge=0.0, le=1.0, description="Mean HHEM over the golden set, through our own pipeline."
    )
    articles: int = Field(
        ge=1, description="How many golden articles produced the mean. A mean of one is not one."
    )
    date: DateStamp = Field(description="The day this was measured, and the day file it lands in.")
    run_id: RunId = Field(
        description="Which execution measured it. Two dispatches of one candidate are two verdicts."
    )
    commit_sha: Sha256 | str = Field(
        min_length=7, description="The tree the measurement ran against."
    )
    runner: str = Field(min_length=1, description="Where it ran. A laptop number is not a gate.")
    verdict: ValidationVerdict = Field(
        description="What the run concluded. A run-level fact, identical on every row."
    )
    detail: str = Field(
        min_length=1, description="The rule's own words for why, so a reader needs no code."
    )

    @model_validator(mode="after")
    def _a_switch_selects_someone_new(self) -> Self:
        if (
            self.verdict is ValidationVerdict.SWITCH_AND_PAUSE
            and self.selected
            and (self.is_incumbent)
        ):
            raise ValueError("a switch that selects the incumbent is not a switch")
        return self

    @model_validator(mode="after")
    def _provenance_and_value_agree(self) -> Self:
        reported = self.leaderboard_provenance is LeaderboardProvenance.REPORTED
        if reported and self.leaderboard_hhem is None:
            raise ValueError("a reported leaderboard score has to carry the score")
        if not reported and self.leaderboard_hhem is not None:
            raise ValueError("a score recorded as not_reported cannot also carry a number")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The ledger's column order. One definition, so a writer cannot invent its own."""
        return tuple(cls.model_fields)

    def csv_row(self) -> dict[str, str]:
        """Every cell a string. A model nobody published a score for is an empty cell."""
        payload = self.model_dump(mode="json")
        return {name: "" if payload[name] is None else str(payload[name]) for name in payload}

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """The inverse. An empty leaderboard cell is an unknown prior, never a zero."""
        payload: dict[str, Any] = {name: row[name] for name in cls.model_fields}
        for name, field in cls.model_fields.items():
            if field.default is None and payload[name] == "":
                payload[name] = None
        return cls.model_validate(payload)
