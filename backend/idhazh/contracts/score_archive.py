"""One archived month of the eval ledger (`state/score-archive/<YYYY-MM>.json`).

`state/scores/` is the largest thing under `state/`: measured on this checkout on
2026-09-03, 5,335 rows in 4,266,655 bytes across two monthly shards. Nothing
bounded it, and monthly sharding bounds one file rather than the tree.

Deleting an old month outright would answer the bytes and cost two things that
cannot be bought back. Every published quality claim about a past month would
lose the rows behind it, which Rule #10 then forbids citing at all. And every
measurement in that month would become re-scoreable: `evals.writer` refuses a
repeat by comparing against every row the ledger holds, so a deleted row is a
row the next run has never seen.

So a month past `observability.scores_full_grain_months` is summarised into this
shape first, and the shard is unlinked only after the summary has been written,
read back and reconciled against it.

**Two things survive the deletion, and they are different things.** The cohorts
carry the numbers: counts, rates, distributions, ranges and spread, at the grain
of one (date, run, row version, model, pipeline, scorer) group. The observation
index carries the identity: one digest per distinct measurement, sorted, so the
dedupe that stops an old observation being scored again as if it were new keeps
working against a month whose rows are gone.

**What is deliberately lost after the shard goes**, stated rather than implied:
item-level lookup, a late draw for the human label queue, re-banding old rows
under new thresholds, any percentile the deciles do not carry, correlation work
between two columns, and any slice the cohort key does not name.

**A moment is `{n, sum, sum_squares, min, max}`, and that is the whole reason a
mean and a spread survive.** A stored mean cannot be re-added into a total and a
stored standard deviation cannot be pooled across cohorts; these five numbers
can do both. `n` is counted over the rows that carried a value rather than over
the cohort, because a column added mid-month is null on the rows before it and
zero would say the row measured nothing.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Annotated, ClassVar, Final, Self

from pydantic import Field, StringConstraints, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    Model,
    MonthStamp,
    RunId,
    SchemaVersion,
    Sha256,
    Slug,
)
from idhazh.contracts.eval_row import ConfidenceBand

#: Ten `hhem` buckets: [0.0,0.1), [0.1,0.2) ... [0.9,1.0]. Defined here rather
#: than in the draw that first needed it, because the bucket count is now a
#: persisted shape - ten counts land in every cohort - and `evals.labels` reads
#: it from here so the draw and the archive can never disagree about what a
#: decile is.
DECILES: Final = 10

#: A column of the eval ledger, as the CSV header spells it. The archive names
#: the measurements it summarises rather than positioning them, so a column
#: added to `EvalRow` later appears as a new key and an archive written before
#: it simply has no key - which reads as never measured, not as zero.
ColumnName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]


def decile_of(hhem: float) -> int:
    """Which decile a faithfulness score falls in, with 1.0 in the top one."""
    return min(int(hhem * DECILES), DECILES - 1)


class Moment(Model):
    """One numeric column of one cohort, as the five numbers that rebuild it.

    Deliberately not a mean and a standard deviation. Those are answers rather
    than evidence: two cohorts' means cannot be added, and a pooled spread
    cannot be recovered from two pooled spreads. `sum` and `sum_squares` can be
    added across any set of cohorts and give back both.
    """

    n: int = Field(
        ge=0,
        description=(
            "Rows of this cohort that carried a value for this column. Never the "
            "cohort's row count: a nullable column is empty on every row written "
            "before it existed, and counting those as zero would say the row measured "
            "the value and got nothing."
        ),
    )
    sum: float = Field(description="Every value added together. A total survives; a mean does not.")
    sum_squares: float = Field(
        ge=0.0,
        description=(
            "Every value squared, added together. With n and sum this gives the "
            "variance and so the spread, which Rule #10 asks for beside any number "
            "read off this archive."
        ),
    )
    min: float | None = Field(
        default=None, description="The smallest value. Absent when n is zero - absent is not zero."
    )
    max: float | None = Field(default=None, description="The largest value.")

    @model_validator(mode="after")
    def _the_range_fits_what_was_counted(self) -> Self:
        if self.n == 0:
            if self.min is not None or self.max is not None:
                raise ValueError("a column nothing measured carries no range")
            if self.sum != 0.0 or self.sum_squares != 0.0:
                raise ValueError("a column nothing measured carries no total")
            return self
        if self.min is None or self.max is None:
            raise ValueError("a column something measured carries both ends of its range")
        if self.min > self.max:
            raise ValueError("the smallest value must not be above the largest")
        # Floating-point sums do not land on an exact bound, so this refuses only
        # a total that could not have come from these values at all.
        tolerance = 1e-6 * max(1.0, abs(self.min), abs(self.max)) * self.n
        if self.sum < self.min * self.n - tolerance or self.sum > self.max * self.n + tolerance:
            raise ValueError("the total does not fit between n copies of the smallest and largest")
        return self

    @property
    def mean(self) -> float | None:
        return None if self.n == 0 else self.sum / self.n

    @property
    def stdev(self) -> float | None:
        """The population spread, or None when fewer than two rows carried a value.

        Population and not sample, because the cohort IS the population: every
        row that carried this column in this group is counted, and there is no
        wider set it was drawn from.
        """
        if self.n < 2:
            return None
        variance = self.sum_squares / self.n - (self.sum / self.n) ** 2
        return math.sqrt(max(0.0, variance))


class ScoreCohort(Model):
    """One (date, run, row version, model, pipeline, scorer) group of scored items.

    Six fields of key, because every one of them changes what a number over the
    group means. A day and a run separate two executions that published the same
    date. The row version says which columns the rows carried at all. The model
    and the pipeline fingerprint say what produced the words, and the scorer
    version says which instrument read them - and the scorer version is the one
    that makes a rate from two cohorts unmixable rather than merely awkward.
    """

    date: DateStamp
    run_id: RunId
    row_version: SchemaVersion = Field(
        description=(
            "The eval-row schema stamp these rows carried. Part of the key because a "
            "column is null on every row stamped before it existed, so a cohort that "
            "mixed two stamps would report a coverage hole as a measurement."
        )
    )
    model_id: Slug
    pipeline_fingerprint: Sha256
    scorer_version: str = Field(min_length=1)

    rows: int = Field(ge=1, description="Rows the shard held for this group, counted as written.")
    hhem_deciles: list[int] = Field(
        min_length=DECILES,
        max_length=DECILES,
        description=(
            "How the group's faithfulness scores fall across ten buckets, lowest "
            "first. The distribution a percentile question can still be asked of "
            "approximately once the rows are gone, and the reason an exact percentile "
            "cannot be."
        ),
    )
    bands: dict[ConfidenceBand, int] = Field(
        description=(
            "How many rows the run banded high, medium and low. All three keys are "
            "present, zero included, so a reader never has to decide whether a missing "
            "band means none or means unrecorded."
        )
    )
    signals: dict[ColumnName, int] = Field(
        description=(
            "How many rows set each boolean column. Counted rather than folded into a "
            "rate, so a count over several cohorts is a sum instead of an average of "
            "averages."
        )
    )
    cut_known: int = Field(
        ge=0,
        description=(
            "Rows that recorded the article's length before the truncation cap, so the "
            "cut is answerable at all. It is not the row count: a row stamped before "
            "2026-08-27T21:00 can carry no pre-cap length."
        ),
    )
    cut: int = Field(
        ge=0,
        description=(
            "Of those, the rows where the model read less than the whole article. Read "
            "as the arithmetic and never as truncation_flagged, which means two "
            "different things either side of 2026-08-29T09:00."
        ),
    )
    premise_recorded: int = Field(
        ge=0,
        description=(
            "Rows carrying the digest of the text the scorer read. Zero on a month "
            "scored before 2026-08-27, when no run recorded a premise."
        ),
    )
    premise_distinct: int = Field(
        ge=0,
        description=(
            "Distinct premise digests among those. Below premise_recorded means two "
            "items were scored against the same text, which is the shape a broken "
            "extractor takes."
        ),
    )
    measurements: dict[ColumnName, Moment] = Field(
        description=(
            "One moment per numeric column of the eval row. Keyed by the column name, "
            "so a column added later is a new key rather than a shifted position."
        )
    )

    @model_validator(mode="after")
    def _the_parts_fit_the_whole(self) -> Self:
        if sum(self.hhem_deciles) != self.rows:
            raise ValueError("the deciles must account for every row of the cohort")
        if set(self.bands) != set(ConfidenceBand):
            raise ValueError("every band is present, zero included")
        if sum(self.bands.values()) != self.rows:
            raise ValueError("the bands must account for every row of the cohort")
        if any(count < 0 or count > self.rows for count in self.signals.values()):
            raise ValueError("a signal cannot fire on fewer than none or more than every row")
        if self.cut_known > self.rows:
            raise ValueError("more rows know their cut than the cohort holds")
        if self.cut > self.cut_known:
            raise ValueError("a cut cannot be counted on a row that does not know its own length")
        if self.premise_recorded > self.rows:
            raise ValueError("more rows recorded a premise than the cohort holds")
        if self.premise_distinct > self.premise_recorded:
            raise ValueError("more distinct premises than rows that recorded one")
        for name, moment in self.measurements.items():
            if moment.n > self.rows:
                raise ValueError(f"{name} was measured on more rows than the cohort holds")
        return self

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        """What makes this cohort one cohort. The sort order of the archive, too."""
        return (
            self.date,
            self.run_id,
            self.row_version,
            self.model_id,
            self.pipeline_fingerprint,
            self.scorer_version,
        )


class ScoreArchive(Contract):
    """One month of `state/scores/`, after the full-grain rows are gone."""

    __schema_stem__: ClassVar[str] = "score-archive"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-03",
            change=(
                "Initial shape: one archived month, its source hash and row count, its "
                "sorted observation digests, and one cohort per (date, run, row "
                "version, model, pipeline, scorer)."
            ),
            why=(
                "state/scores/ is the largest store under state/ - 5,335 rows in "
                "4,266,655 bytes on 2026-09-03 - and nothing bounded it. Deleting an "
                "old month outright would erase the evidence behind every published "
                "quality claim about it, and would let every measurement in it be "
                "scored again as if it were new, because evals.writer refuses a repeat "
                "by reading the rows themselves. This shape is what a month is turned "
                "into before its shard is unlinked: the cohorts keep the totals, "
                "rates, distributions, ranges and spread, and the digest index keeps "
                "the dedupe exact."
            ),
        ),
    )

    month: MonthStamp = Field(description="The shard this replaces, spelled the way it was filed.")
    source_rows: int = Field(
        ge=0,
        description=(
            "Data rows the shard held, header excluded. Reconciled against the shard "
            "before it is unlinked, so a summary of a truncated read can never be the "
            "reason a file is deleted."
        ),
    )
    source_sha256: Sha256 = Field(
        description=(
            "The shard's bytes, digested whole. The one field that says WHICH file "
            "this summarises rather than describing what was in it."
        )
    )
    observation_digests: list[Sha256] = Field(
        description=(
            "One digest per distinct measurement the month held - the SHA-256 of the "
            "eval writer's observation key - sorted and distinct. This is what keeps "
            "the dedupe exact after the rows are gone: without it, the day a shard is "
            "deleted every observation in it becomes scoreable again as if it were "
            "new, and a count over the ledger stops being a count of items."
        )
    )
    cohorts: list[ScoreCohort] = Field(
        description="Every group the month held, in key order. Their row counts sum to source_rows."
    )

    @model_validator(mode="after")
    def _the_index_and_the_cohorts_describe_one_month(self) -> Self:
        digests = self.observation_digests
        if any(later <= earlier for earlier, later in pairwise(digests)):
            raise ValueError("the observation digests are sorted and distinct")
        if len(digests) > self.source_rows:
            raise ValueError("more distinct measurements than rows to hold them")
        keys = [cohort.key for cohort in self.cohorts]
        if any(later <= earlier for earlier, later in pairwise(keys)):
            raise ValueError("the cohorts are in key order and distinct")
        if sum(cohort.rows for cohort in self.cohorts) != self.source_rows:
            raise ValueError("the cohorts must account for every row of the shard")
        return self
