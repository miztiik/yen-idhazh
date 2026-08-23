"""One row of the committed eval ledger (`state/scores.csv`).

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
    Sha256,
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
            version="2026-08-23",
            change=(
                "Added evidential_density and speculative_density, nullable, at the end "
                "of the row. The ledger's header is migrated in the same commit."
            ),
            why=(
                "Every other column scores our summary against the article. These two "
                "score the article, which nothing did: a faithful summary of an "
                "unsourced rumour scores high on all of them and is still an unsourced "
                "rumour. First columns to land after the ledger had rows in it, hence "
                "appended rather than filed by meaning, and null rather than zero on "
                "the ten rows that predate them. Recorded only - no band reads them "
                "until enough rows exist to say what a normal value is (Holy Law #10)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T03:00",
            change=(
                "Added unsupported_numbers, hedge_dropped, extraction_suspect, "
                "verbatim_run and source_seen_word_count."
            ),
            why=(
                "Faithfulness cannot see a wrong number, a rumour asserted as fact, or a "
                "summary of navigation chrome - it scores all three generously. The ledger "
                "is still empty, so these cost a changelog entry today and a migration ever "
                "after."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T02:00",
            change="Added pipeline_fingerprint, output_digest and determinism_violation.",
            why=(
                "The ledger is the only committed record that survives a run, so it is the "
                "only place a later run can detect that identical inputs produced different "
                "words. No payload predates this - the ledger has never been written."
            ),
        ),
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
        description="Survival of the lead's entities and numbers. The instrument for omission.",
    )
    compression: Score = Field(
        ge=0.0,
        description=(
            "Summary length over source length. Recorded, never flagged: at a fixed output "
            "budget this measures the article's length, not the summary's quality."
        ),
    )
    extractiveness: Score = Field(
        ge=0.0,
        le=1.0,
        description="Share of the summary's 4-grams found verbatim in the source.",
    )
    verbatim_run: Score = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Longest unbroken copied stretch. This is the one that names copying.",
    )
    unsupported_numbers: int = Field(
        default=0,
        ge=0,
        description="Numbers asserted by the summary that appear nowhere in the full source.",
    )
    hedge_dropped: bool = Field(
        default=False,
        description="The source hedged and the summary asserted. A rumour became a fact.",
    )
    extraction_suspect: bool = Field(
        default=False,
        description="The text looks like page furniture. A faithful summary of chrome scores high.",
    )
    band: ConfidenceBand

    source_word_count: int = Field(ge=0, description="The full article.")
    source_seen_word_count: int = Field(
        default=0, ge=0, description="What the model actually got, after truncation."
    )
    summary_word_count: int = Field(ge=0)
    pipeline_fingerprint: Sha256
    output_digest: Sha256
    determinism_violation: bool = Field(
        default=False,
        description="Identical inputs, different words. Counted and published, never fatal.",
    )
    scorer_version: str = Field(
        min_length=1,
        description=(
            "Derived, never hand-typed: the scorer, its weights, the tagger and the band "
            "thresholds, spelled so a row still explains itself years later."
        ),
    )
    scored_at: Timestamp
    score_ms: int = Field(
        default=0,
        ge=0,
        description=(
            "How long the faithfulness scorer took on this item. It decides whether the "
            "scorer can stay a census or has to become a sample."
        ),
    )

    # Appended at the end, and not filed next to `hedge_dropped` where they belong
    # by meaning. The ledger is a committed append-only CSV with rows already in
    # it; a column inserted mid-row shifts every historical cell one place right
    # under a reader that maps by position. Meaning loses to layout here.
    #
    # Null and not 0.0, for the same reason: 0.0 is a measurement that says the
    # article marked nothing. A row written before these existed measured neither,
    # and the difference is the whole value of the column.
    evidential_density: Score | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Attribution markers as a share of the ARTICLE's words. How often the story "
            "says where it got a claim. Scores the source, not our summary of it. Null "
            "on a row scored before metrics-2."
        ),
    )
    speculative_density: Score | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Unresolved-claim markers as a share of the ARTICLE's words. Read against "
            "evidential_density: speculation nobody is cited for is the fragile case. "
            "Null on a row scored before metrics-2."
        ),
    )

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
