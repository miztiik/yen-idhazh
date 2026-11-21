"""What evidence can a nightly similarity diagnostic record without storing article text?"""

import json
from datetime import date
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Final, Self

from pydantic import AfterValidator, BaseModel, Field, RootModel, model_validator

from idhazh.contracts.base import DateStamp, Model, RunId, Sha256, Slug
from idhazh.contracts.knobs.content_similarity_canaries import MAX_CANARY_PAIRS
from idhazh.contracts.story_similarity_pair_verdict import (
    JudgeModelId,
    PairBucket,
    SameStoryVerdict,
    ScorerModelId,
    canonical_compact_object,
)

# Counts must also be exact in the browser. The other maxima bound evidence on disk.
MAX_SAFE_INTEGER: Final = (1 << 53) - 1
MAX_SCORE_BINS: Final = 200
MAX_SCORE_BASELINE_DAYS: Final = 90
MAX_FIT_PAIRS: Final = 1050

DiagnosticCount = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
ScoreCutoff = Annotated[float, Field(strict=True, ge=-1.0, le=1.0, allow_inf_nan=False)]
DiagnosticShare = Annotated[float, Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)]
ProbabilityBins = Annotated[int, Field(strict=True, ge=2, le=50)]


def _calendar_day(day: str) -> str:
    date.fromisoformat(day)
    return day


DiagnosticDate = Annotated[DateStamp, AfterValidator(_calendar_day)]


class SampleStatus(StrEnum):
    MEASURED = "measured"
    NOT_FILED = "not_filed"
    DRAW_MISMATCH = "draw_mismatch"


class ScoreDriftStatus(StrEnum):
    MEASURED = "measured"
    NO_HISTOGRAM = "no_histogram"
    EMPTY_POOL = "empty_pool"
    INSUFFICIENT_BASELINE = "insufficient_baseline"


class JudgeProbabilityStatus(StrEnum):
    MEASURED = "measured"
    NO_REFERENCE_FIT = "no_reference_fit"
    NO_ELIGIBLE_PAIRS = "no_eligible_pairs"


class SliceOutcome(Model):
    """One drawn slice and the disjoint outcomes that actually came back."""

    bucket: PairBucket
    low: ScoreCutoff
    high: ScoreCutoff
    available: DiagnosticCount
    drawn: DiagnosticCount = Field(gt=0)
    yes: DiagnosticCount
    no: DiagnosticCount
    unclear: DiagnosticCount
    split: DiagnosticCount
    refused: DiagnosticCount

    @property
    def returned(self) -> int:
        return self.yes + self.no + self.unclear + self.split + self.refused

    @model_validator(mode="after")
    def _counts_fit_the_slice(self) -> Self:
        if self.low >= self.high:
            raise ValueError("a slice's low edge must be below its high edge")
        if self.drawn > self.available or self.returned > self.drawn:
            raise ValueError("slice counts must nest: returned <= drawn <= available")
        return self


class SliceOutcomes(Model):
    """Drawn slices in ascending score order, including slices with no returns."""

    slices: tuple[SliceOutcome, ...]

    @model_validator(mode="after")
    def _slices_do_not_overlap(self) -> Self:
        if any(left.high > right.low for left, right in pairwise(self.slices)):
            raise ValueError("slices must be ordered by score and must not overlap")
        return self


class ScorePoolHistogram(Model):
    """The full eligible score pool under one scoring and selection recipe."""

    stamp: Sha256 = Field(description="SHA-256 of the score and pool recipe.")
    edges: tuple[ScoreCutoff, ...] = Field(min_length=2, max_length=MAX_SCORE_BINS + 1)
    counts: tuple[DiagnosticCount, ...] = Field(min_length=1, max_length=MAX_SCORE_BINS)

    @model_validator(mode="after")
    def _counts_fit_the_edges(self) -> Self:
        if len(self.edges) != len(self.counts) + 1:
            raise ValueError("a score histogram has one count per edge interval")
        if (
            self.edges[0] != -1
            or self.edges[-1] != 1
            or any(low >= high for low, high in pairwise(self.edges))
        ):
            raise ValueError("score histogram edges must increase strictly from -1 to 1")
        return self


class ScoreDriftSource(Model):
    """One saved histogram that contributed to the baseline."""

    date: DiagnosticDate = Field(description="UTC digest date of the source histogram.")
    run_id: RunId
    histogram_sha256: Sha256


class ScoreDriftBaseline(Model):
    """Which earlier days the comparison found and how many were needed."""

    sources: tuple[ScoreDriftSource, ...] = Field(max_length=MAX_SCORE_BASELINE_DAYS)
    required_days: DiagnosticCount = Field(ge=1, le=MAX_SCORE_BASELINE_DAYS)
    share_floor: float = Field(strict=True, gt=0.0, lt=1.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _sources_are_newest_first(self) -> Self:
        if len(self.sources) > self.required_days:
            raise ValueError("baseline sources cannot outnumber required_days")
        if any(newer.date <= older.date for newer, older in pairwise(self.sources)):
            raise ValueError("baseline sources must have distinct UTC digest dates, newest first")
        return self


class UpperFitMeaningStamp(Model):
    """Everything that must be known about the score and judge for a fit to be compared."""

    judge_model: JudgeModelId
    prompt_digest: Sha256
    grammar_digest: Sha256
    scorer_model: ScorerModelId
    cosine_weight: DiagnosticShare
    judge_policy_version: DiagnosticDate = Field(description="UTC date of the judge policy.")


class UpperFitEvidence(Model):
    """Exact training membership and inclusive score support of a retained upper fit."""

    meaning_stamp: UpperFitMeaningStamp
    judge_temperature: float = Field(strict=True, ge=0.0, le=2.0, allow_inf_nan=False)
    pair_keys: tuple[Sha256, ...] = Field(min_length=1, max_length=MAX_FIT_PAIRS)
    low: ScoreCutoff
    high: ScoreCutoff
    yes: DiagnosticCount

    @model_validator(mode="after")
    def _fit_membership_is_exact(self) -> Self:
        if any(left >= right for left, right in pairwise(self.pair_keys)):
            raise ValueError("fit pair_keys must be sorted and unique")
        if self.low > self.high or self.yes > len(self.pair_keys):
            raise ValueError("fit score support and training YES count must fit its membership")
        return self


class JudgeProbabilityEvidence(Model):
    """The prior fit used and the size of this night's separate evaluation cohort."""

    source_date: DiagnosticDate = Field(description="UTC digest date of the reference fit.")
    source_run_id: RunId
    fit_sha256: Sha256
    pairs: DiagnosticCount
    yes: DiagnosticCount
    bins: ProbabilityBins

    @model_validator(mode="after")
    def _yes_fits_the_cohort(self) -> Self:
        if self.yes > self.pairs:
            raise ValueError("evaluation YES count cannot exceed its pair count")
        return self


CanaryExpectationsMap = Annotated[
    dict[Slug, SameStoryVerdict], Field(min_length=1, max_length=MAX_CANARY_PAIRS)
]


class CanaryExpectations(RootModel[CanaryExpectationsMap]):
    """The run's expected verdicts, keyed by the configured stable canary IDs."""


def diagnostic_text(evidence: BaseModel) -> str:
    """Encode typed diagnostic evidence as one canonical text cell, with no newline."""
    return json.dumps(
        evidence.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def read_diagnostic_text[E: BaseModel](text: str, *, column: str, model: type[E]) -> E:
    """Read a canonical text cell as its exact nested shape."""
    return model.model_validate(canonical_compact_object(text, column=column))
