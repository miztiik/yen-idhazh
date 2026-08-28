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


class BandReason(StrEnum):
    """Why an item did not reach the top band.

    An identifier, never copy: the sentence a reader sees is owned by the site
    and can be rewritten without a schema change. A `high` item has no reason,
    because there is nothing to explain.
    """

    #: The summary asserts a figure that appears nowhere in the article.
    UNSUPPORTED_NUMBER = "unsupported_number"
    #: No faithfulness score exists, so the item cannot claim the top band.
    NOT_SCORED = "not_scored"
    #: The names and figures in the article's opening did not survive.
    LEAD_MISSING = "lead_missing"
    #: The article hedged and the summary asserted.
    HEDGE_DROPPED = "hedge_dropped"
    #: The faithfulness score itself put the item here.
    FAITHFULNESS = "faithfulness"


class EvalRow(Contract):
    """The Evaluate stage's output, appended once per item."""

    __schema_stem__: ClassVar[str] = "eval-row"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-08-27T21:00",
            change=(
                "source_word_count is nullable, source_seen_word_count may not exceed "
                "it, and the committed ledger is rewritten to obey that."
            ),
            why=(
                "The stamp below fixed the writer and left the committed rows carrying "
                "the old meaning. Measured over all 2,566 rows: 610 have the seen count "
                "LARGER than the full count, and every one of them was written by the "
                "old writer - none of the 220 rows the fixed writer produced reads that "
                "way. Nothing compared the two cells, which is how the pair stayed wrong "
                "for months, so the rule is a validator now rather than a habit. Null "
                "and not zero where the length cannot be recovered: extract discards the "
                "pre-cap body, so a truncated row written before this has no full length "
                "anywhere and zero would say the article was empty. "
                "backend/utilities/migrate_score_ledger.py is the read-side migration. "
                "It recovers rather than guesses - an article under the cap IS the text "
                "the model saw, so its two counts are equal by construction, and 2,204 "
                "rows got a real number back while 142 were emptied."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T20:30",
            change=(
                "hhem_full is now scored against the article before the truncation cap, "
                "so hhem_delta and truncation_flagged can be non-zero. No column was "
                "added or removed and no row was rewritten."
            ),
            why=(
                "dual_score exists to tell a model that invented something from a model "
                "that faithfully summarized the half we gave it, and its only production "
                "caller handed it the same string twice: extract.truncate_to_tokens "
                "returned the cut text and to_article kept only that. Measured over all "
                "2,232 rows written before this, hhem_delta is exactly 0.0 on 2,232 of "
                "2,232 and hhem equals hhem_full on every one. Those rows record two "
                "scores of one text, so 'the gap was zero' means 'the gap was never "
                "measured' and must not be read as evidence that truncation costs "
                "nothing. Recorded only - no band reads either column, so "
                "METRICS_VERSION did not move."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T20:00",
            change=(
                "source_word_count is now Article.source_word_count, the pre-cap count, "
                "rather than a recount of whatever text the caller passed as full_text. "
                "No column was added or removed and no row was rewritten."
            ),
            why=(
                "The pair source_word_count / source_seen_word_count reads as "
                "before-truncation and after-truncation and was neither. Both came off "
                "the same post-cap string through two different counters - "
                "len(_WORD.findall(t)) against len(t.split()) - so the difference between "
                "them measured the counters. Measured over all 2,232 rows written before "
                "this: they agree on 287, source_word_count is larger on 1,355, and "
                "source_seen_word_count is larger on 590, which is impossible if one "
                "string is a cut of the other. Read as a truncation signal the pair said "
                "87 percent of items were truncated; counting the rows sitting on the "
                "1,923-word cap says 6.3 percent. Rows written before this stamp carry "
                "the old meaning and must not be read as a truncation rate."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change=(
                "Added source_digest, nullable, at the end of the row. The ledger's "
                "header is migrated in the same commit."
            ),
            why=(
                "The row named the words that came out and never the text they were "
                "scored against. A person re-reading an item to label it by hand had no "
                "way to prove the article in front of them was the sanitized, truncated "
                "premise the scorer read, so a disagreement between the two measured "
                "premise mismatch and not scorer error. Empty on the 2,232 rows that "
                "predate it: those runs recorded no premise, and a digest computed today "
                "would name text nobody read. Recorded only - no band reads it, so "
                "METRICS_VERSION did not move."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change=(
                "Added self_repetition, nullable, at the end of the row. The ledger's "
                "header is migrated in the same commit."
            ),
            why=(
                "Every n-gram column here reads the summary against the article. Nothing "
                "read the summary against itself, so a summary that says the same clause "
                "three times scored clean on all eleven quality columns - greedy decoding "
                "has no sampling noise to break a loop, and a repeated sentence is still "
                "perfectly supported by the source. Null and not zero on the rows that "
                "predate it: zero means measured and not repeating. Recorded only - no "
                "band reads it, so METRICS_VERSION did not move."
            ),
        ),
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
                "until enough rows exist to say what a normal value is (Rule #10)."
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
    hhem_full: Score = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Faithfulness against the article before the truncation cap. Equal to hhem "
            "on rows stamped before 2026-08-27T20:30, which scored one text twice."
        ),
    )
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

    source_word_count: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The article before the truncation cap, counted by Article.source_word_count. "
            "Null when the length is not knowable: the pre-cap body is never persisted, "
            "so a truncated row stamped before 2026-08-27T21:00 has no full length to "
            "recover. Rows stamped before 2026-08-27T20:00 recount the post-cap text."
        ),
    )
    source_seen_word_count: int = Field(
        default=0,
        ge=0,
        description=(
            "What the model actually got, after truncation. Counted the same way as "
            "source_word_count, so the difference between the two is the cut."
        ),
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
    # Appended for the same layout reason as the pair above, and null for the
    # same meaning reason: 0.0 says the summary was read and never repeated
    # itself, which is not what a row written before 2026-08-26 can claim.
    self_repetition: Score | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Share of the summary's 4-word windows that repeat one it already used. The "
            "only column that reads the summary against ITSELF: every other n-gram column "
            "reads it against the article, and a repeated sentence is perfectly supported "
            "by the article. Zero means no window repeats. Recorded only, never banded. "
            "Null on a row scored before 2026-08-26."
        ),
    )
    # Appended for the same layout reason again. Null rather than a digest of the
    # empty string: an empty premise is a real and different thing from a premise
    # nobody wrote down, and only one of the two is a defect.
    source_digest: Sha256 | None = Field(
        default=None,
        description=(
            "The premise the faithfulness scorer read, digested whole: the article text "
            "after sanitizing and truncation. Not the fetched page, and not the summary - "
            "`output_digest` already names those words. It exists so a person labelling "
            "this item by hand can prove they are reading the same text the scorer read; "
            "without it a disagreement between them measures a premise mismatch rather "
            "than a scorer error. Null on a row scored before 2026-08-27."
        ),
    )

    @model_validator(mode="after")
    def _delta_is_rebuilt_not_trusted(self) -> Self:
        expected = round(self.hhem - self.hhem_full, _DELTA_PLACES)
        if abs(self.hhem_delta - expected) > 1e-9:
            raise ValueError("hhem_delta must be hhem - hhem_full, recomputed on read")
        return self

    @model_validator(mode="after")
    def _the_model_cannot_have_read_more_than_the_article_holds(self) -> Self:
        """The seen count is a cut of the full count, so it cannot be the larger one.

        `Article` already refuses the same shape. Stating it here too is what
        makes the pair a before-and-after pair rather than two numbers that
        happen to sit side by side - the defect this rule closes was two
        different counters over one string, and only a comparison could see it.
        """
        full = self.source_word_count
        if full is not None and self.source_seen_word_count > full:
            raise ValueError(
                "source_seen_word_count is a cut of source_word_count, so it is not more"
            )
        return self

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The ledger's column order. One definition, so a writer cannot invent its own."""
        return tuple(cls.model_fields)
