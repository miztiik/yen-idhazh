"""One row of the committed eval ledger (`evals/scores.csv`).

Every field is a scalar, because the ledger is a CSV that is appended by CI and
read by the dashboard, never recomputed at read time.

The row is deliberately self-describing - it carries `date`, `source_url` and
`title` - so that a row still means something after the day it describes has
been pruned from the published site. Those columns exist before retention is
ever enabled, not after.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import Field, model_validator

from idhazh.contracts.article import UntrustedLine
from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    ItemId,
    RunId,
    Slug,
    Timestamp,
    Url,
    UrlKey,
)

Score = float
_DELTA_PLACES = 6


class ConfidenceBand(StrEnum):
    """The band, not the number, is what drives behaviour and what a reader sees."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvalRow(Contract):
    """The Evaluate stage's output, appended once per item."""

    __schema_stem__: ClassVar[str] = "eval-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: dual faithfulness scores, the counterweights, and the band.",
            why="Contracts before logic - the columns are fixed before the first row lands.",
        ),
    )

    date: DateStamp
    run_id: RunId
    item_id: ItemId
    url_key: UrlKey
    source_url: Url
    title: UntrustedLine
    vertical: Slug
    model_id: Slug
    attempt: int = Field(ge=1)

    hhem: Score = Field(ge=0.0, le=1.0, description="Faithfulness against the text the model saw.")
    hhem_full: Score = Field(ge=0.0, le=1.0, description="Faithfulness against the full article.")
    hhem_delta: Score = Field(
        description="hhem - hhem_full. The cost of truncation, invisible unless both are scored."
    )
    truncation_flagged: bool
    coverage: Score = Field(
        ge=0.0,
        le=1.0,
        description="Named-entity and numeric survival. The instrument for selective omission.",
    )
    compression: Score = Field(ge=0.0, description="Summary length as a fraction of source length.")
    extractiveness: Score = Field(
        ge=0.0, le=1.0, description="Verbatim overlap. High here plus high hhem means copying."
    )
    band: ConfidenceBand

    source_word_count: int = Field(ge=0)
    summary_word_count: int = Field(ge=0)
    scorer_version: str = Field(min_length=1)
    scored_at: Timestamp

    @model_validator(mode="after")
    def _delta_is_rebuilt_not_trusted(self) -> Self:
        expected = round(self.hhem - self.hhem_full, _DELTA_PLACES)
        if abs(self.hhem_delta - expected) > 1e-9:
            raise ValueError("hhem_delta must be hhem - hhem_full, recomputed on read")
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The ledger's column order. One definition, so a writer cannot invent its own."""
        return tuple(cls.model_fields)
