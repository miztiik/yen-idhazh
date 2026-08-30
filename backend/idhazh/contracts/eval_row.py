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
            version="2026-08-30T20:00",
            change=(
                "hhem_delta, truncation_flagged and score_ms each say what they hold "
                "and how to read them. No column was added, removed or retyped."
            ),
            why=(
                "The owner had to ask what two of these columns meant, which is the "
                "definition of a description not doing its job, and each of the three "
                "carries a trap a reader cannot see from the cell. hhem_delta is "
                "derived and recomputed on read, so it is not an independent "
                "measurement, and the window geometry moves it by more than the whole "
                "medium band. truncation_flagged means one thing before "
                "2026-08-29T09:00 and another after, so a query without the version "
                "branch reads two facts as one. score_ms is off the critical path and "
                "exists to size the census-versus-sample decision, which "
                "observability.sample_rate now implements. The generated schema moves "
                "because a description is part of it; every committed row still "
                "validates unchanged."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T09:00",
            change=(
                "truncation_flagged is Article.truncated - whether extract cut the "
                "article body. It was hhem_delta above evaluation.truncation_gap_max, "
                "or a brief item copied past evaluation.brief_compression_ceiling. No "
                "column was added or removed and no row was rewritten."
            ),
            why=(
                "The column's name says the article was cut short and its only consumer "
                "prints exactly that sentence, and it was reading a faithfulness gap "
                "instead. The gap cannot answer the question: score_over_chunks takes "
                "the best of overlapping windows, and a cut article's last window is not "
                "a window of the whole article, so the two maxima are taken over "
                "different premises and the difference is not a cost. Measured "
                "2026-08-28 over all 2,683 committed rows of state/scores.csv: 22 rows "
                "were genuinely cut, hhem_delta over them runs -0.1235 to +0.0381 "
                "against a threshold of +0.100, and the flag fired on 0 of them. It "
                "fired on exactly one row in the whole ledger, and that row read 748 "
                "words of a 748-word article. The brief-copying clause went with it: "
                "verbatim_run and extractiveness already carry that fact, and one "
                "column answers one question. "
                "A row stamped before this is UNKNOWN and never False, in both "
                "directions: a row before 2026-08-27T20:30 held two scores of one text "
                "so its gap could not be non-zero, and a row between the two stamps held "
                "a real gap read by the wrong rule. Neither state is recoverable from "
                "the row, so frontend/src/lib/server/model-work.ts counts the column "
                "only over rows stamped at or after 2026-08-28 and prints absence as "
                "absence."
            ),
        ),
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
