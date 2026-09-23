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
            version="2026-09-13T22:00",
            change="pipeline_fingerprint stays on this one shape after leaving the other nine.",
            why="The console still reads its column on every day that recorded no input manifest.",
        ),
        ChangelogEntry(
            version="2026-09-12T21:00",
            change="pipeline_fingerprint is optional and nothing sets it.",
            why="It keyed the eval window, and the window stopped being keyed on a stamp.",
        ),
        ChangelogEntry(
            version="2026-09-12T18:40",
            change="item_id accepts a second shape: sixteen Crockford base32 symbols.",
            why="Ten decimal digits is 33 bits of an address, which collides on a busy day.",
        ),
        ChangelogEntry(
            version="2026-09-07T01:00",
            change="Added new_fact_rate, nullable, at the end of the row.",
            why="A summary can add a fact the article never carried and nothing counted it.",
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Earlier changes are in this file's git history.",
            why="A changelog says what moved lately; git is the archive.",
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
        description=(
            "hhem minus hhem_full, on the same 0-to-1 faithfulness scale. Derived, "
            "never independent: _delta_is_rebuilt_not_trusted recomputes it from the "
            "two scores on every read and raises if the stored cell disagrees, so it "
            "carries no information the two scores beside it do not. It is 0.0 on an "
            "article nobody cut, by construction - both scores read the same text and "
            "the scorer is deterministic - and 2,945 of the 2,945 uncut rows that "
            "carry both word counts are exactly 0.0 (measured 2026-08-30). It is "
            "non-zero on 3 of all 3,113 committed rows, because a row stamped before "
            "2026-08-27T20:30 scored one text twice and almost no article is cut. "
            "Recorded only - no band reads it, and nothing on the published site "
            "prints it. Read it with the confound stated: measured 2026-08-29, a "
            "3-window article scores 0.40 lower than the same article read whole, "
            "against bands at 0.80 and 0.50, so the window geometry alone is wider "
            "than the whole medium band and this number mixes the cost of the cut "
            "with the cost of the slicing. Until that settles it is not the cost of "
            "truncation on its own. See docs/concepts/evaluation.md."
        )
    )
    truncation_flagged: bool = Field(
        description=(
            "True when extract cut the article body before the model read it - "
            "Article.truncated, a fact from the stage that did the cutting, not a "
            "score. That is what the name always promised and what the column holds "
            "from 2026-08-29T09:00. A row stamped earlier holds a DIFFERENT fact: "
            "hhem_delta above a configured gap, which is the distance between two "
            "faithfulness scores and says nothing about a cut. Measured 2026-08-30 "
            "over all 3,113 committed rows of state/scores.csv, which are exact "
            "counts over a committed file and carry no spread. Of the 2,683 rows on "
            "the old side of the boundary it is true on 0 of the 22 genuinely cut "
            "rows, and true on exactly 1 row, which read 748 words of a 748-word "
            "article and was never cut. Of the 430 rows on the new side, 4 were cut "
            "and all 4 are flagged, and the flag agrees with the word counts on 430 "
            "of 430. Prefer the pair source_word_count > source_seen_word_count for "
            "any new reader: it is true exactly when the body was cut, on every row "
            "carrying both, with no version branch to get wrong. The pair has one "
            "hole of its own, and it prints as a hole - 142 of the 3,113 rows carry a "
            "null source_word_count, 4.6 percent, every one of them on the old side, "
            "and unknown is printed as unknown rather than as uncut. Its one reader "
            "is frontend/src/lib/server/model-work.ts, which counts it only over rows "
            "stamped from CUT_FLAG_MEANS_A_CUT_FROM."
        )
    )
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
    pipeline_fingerprint: Sha256 | None = Field(
        default=None,
        description=(
            "Null on every row written after 2026-09-12. The stamp stopped being a gate "
            "and stopped keying the eval window, so no writer fills it. The field and its "
            "ledger column survive here alone, because the console reads this column to "
            "draw the model-change boundaries on every day whose identity is a digest "
            "rather than a named input manifest, and it is the only source of them. "
            "Remove it, and the column from state/scores/, once no score row the widest "
            "console window can reach carries one."
        ),
    )
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
            "Milliseconds the faithfulness scorer spent on THIS one item, after the "
            "summary was already written. Not on the critical path of the published "
            "words: no digest sentence waits on it, and a run with the scorer off "
            "publishes the same text. The shard clock does wait on it, and that is "
            "the decision this column exists to size - whether the scorer stays a "
            "census or becomes a sample. observability.sample_rate is the knob that "
            "decision produced, so this is the instrument behind that knob and not a "
            "stage timing to tune. Measured 2026-08-30 over all 3,113 committed rows "
            "of state/scores.csv: median 2,763 ms an item, 95th percentile 14,814 ms, "
            "longest 51,587 ms. Per run, the heaviest of the 25 committed runs spent "
            "859.7 s scoring 149 items - 14.3 minutes spread over that run's shards, "
            "so at today's volume of about 150 items a day the census is affordable "
            "and a rate below 1.0 is insurance rather than a rescue. Zero on the 10 "
            "rows written before the column existed, and those read as unmeasured "
            "rather than as instant."
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
    # Appended for the same layout reason as the block above, and null for the
    # same meaning reason: 0.0 is a reply whose every key point restated the
    # summary, which a row written before the column existed never measured.
    new_fact_rate: Score | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Share of the item's key points that state a fact the summary prose does "
            "not already carry - the aggregate inverse of the restatement drop "
            "to_summary makes, read at the same distinctness ceiling, so a key point "
            "that counts here is exactly one the drop keeps. The instrument for whether "
            "the key-point prompt finds facts or paraphrases the summary. Lexical, and "
            "the element table supersedes it with span-anchored ids that "
            "carry no false positive. Recorded only - no band reads it, and best-of-N "
            "against it is the Goodhart form of the number. Null on a row scored before "
            "the column existed; 0.0 only on a scored reply whose every key point "
            "restated."
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

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, keyed by column name.

        The same serialization `evals.writer.append_segment` reaches by dumping the model
        and picking the columns, spelled once here instead. A segment of these
        rows is written and read back by the generic machinery in `idhazh.ledger`,
        which takes a row that can write itself and never a dict somebody built.
        """
        payload = self.model_dump(mode="json")
        return {
            name: "" if payload[name] is None else str(payload[name])
            for name in self.csv_columns()
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> Self:
        """One row read back. An empty cell is an absent optional, which is what a CSV can say."""
        return cls.model_validate(
            {name: (row[name] or None) for name in cls.model_fields if name in row}
        )
