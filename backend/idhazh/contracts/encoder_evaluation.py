"""The current offline, model-judged comparison of saved encoder vectors."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    Model,
    RelPath,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.encoder_judgment import PairVerdict
from idhazh.contracts.encoder_reading import EncoderReading

Count = Annotated[int, Field(ge=0)]
Finite = Annotated[float, Field(allow_inf_nan=False)]
Rate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class EvaluationSettings(Model):
    expected_judgments: Annotated[int, Field(ge=1)]
    calibration_fraction: Annotated[float, Field(gt=0, lt=1)]
    split_seed: Annotated[int, Field(ge=0)]
    precision_target: Annotated[float, Field(gt=0, le=1)]
    bootstrap_rounds: Annotated[int, Field(ge=1)]
    bootstrap_seed: Annotated[int, Field(ge=0)]
    interval_level: Annotated[float, Field(gt=0, lt=1)]
    minimum_valid_draws: Annotated[int, Field(ge=1)]
    reference: Slug


class VectorSource(Model):
    slug: Slug
    file: RelPath
    run_id: Annotated[str, Field(pattern=r"^[0-9]+$")]
    artifact: Annotated[str, Field(min_length=1)]


class RepeatAudit(Model):
    pair_ids: list[str]
    verdicts: dict[str, PairVerdict]
    agreement: bool
    reversed_ids: list[str]


class CoverageAudit(Model):
    judged_ids: list[str]
    verdict_counts: dict[PairVerdict, Count]
    selection_strata: dict[str, Count]
    unique_pairs: Count
    repeated_rows: Count
    repeats: list[RepeatAudit]
    cannot_tell_ids: list[str]
    missing_vector_ids: list[str]
    changed_summary_ids: list[str]
    url_covered_rows: Count
    exact_text_covered_rows: Count
    excluded_unique_ids: dict[str, list[str]]
    removed_duplicate_ids: list[str]
    eligible_ids: list[str]
    eligible_strata: dict[str, Count]

    @model_validator(mode="after")
    def check_counts(self) -> Self:
        if len(self.judged_ids) != sum(self.verdict_counts.values()):
            raise ValueError("judged ids and verdict counts differ")
        if self.unique_pairs + self.repeated_rows != len(self.judged_ids):
            raise ValueError("unique pairs and repeated rows do not cover the frame")
        excluded = [pair_id for ids in self.excluded_unique_ids.values() for pair_id in ids]
        if len(excluded) + len(self.eligible_ids) != self.unique_pairs:
            raise ValueError("unique exclusions and eligible pairs do not cover the frame")
        if len(set(excluded + self.eligible_ids)) != self.unique_pairs:
            raise ValueError("a unique pair appears in more than one audit category")
        return self


class LabelProvenance(Model):
    history_rows: Count
    labeler_counts: dict[str, Count]
    label_source: Literal["model"]
    human_reviewed: Literal[0]
    labels_commit: CommitSha
    judgments_sha256: Sha256
    frame_sha256: Sha256


class Partition(Model):
    component_ids: list[str]
    pair_ids: list[str]
    articles: Count
    eligible_articles: Count
    same: Annotated[int, Field(ge=1)]
    different: Annotated[int, Field(ge=1)]
    prevalence: Rate

    @model_validator(mode="after")
    def check_counts(self) -> Self:
        if self.same + self.different != len(self.pair_ids):
            raise ValueError("partition class counts differ from its pair ids")
        if self.prevalence != self.same / len(self.pair_ids):
            raise ValueError("partition prevalence differs from its class counts")
        return self


class SplitAudit(Model):
    method: Literal["all-frame article-connected components"]
    total_components: Count
    active_components: Count
    excluded_only_components: Count
    frame_articles: Count
    shared_articles: Literal[0]
    calibration: Partition
    held_out: Partition

    @model_validator(mode="after")
    def check_disjointness(self) -> Self:
        for field in ("component_ids", "pair_ids"):
            if set(getattr(self.calibration, field)) & set(getattr(self.held_out, field)):
                raise ValueError(f"calibration and held-out share {field}")
        if self.active_components != (
            len(self.calibration.component_ids) + len(self.held_out.component_ids)
        ):
            raise ValueError("active component count differs from the split")
        if self.total_components != self.active_components + self.excluded_only_components:
            raise ValueError("component counts do not cover the frame")
        return self


class RankingMetrics(Model):
    average_precision: Rate
    area_under_curve: Rate


class OperatingPoint(Model):
    threshold: Finite | None
    precision: Rate | None
    recall: Rate | None
    tp: Count | None
    fp: Count | None
    fn: Count | None
    tn: Count | None
    reason: str | None

    @model_validator(mode="after")
    def check_defined(self) -> Self:
        counts = (self.tp, self.fp, self.fn, self.tn)
        if self.threshold is None:
            if not self.reason or any(value is not None for value in (
                self.precision, self.recall, *counts,
            )):
                raise ValueError("an unavailable threshold needs null metrics and a reason")
        else:
            if any(value is None for value in counts) or self.recall is None:
                raise ValueError("a chosen threshold needs confusion counts and recall")
            if self.tp is not None and self.fp is not None:
                if self.tp + self.fp == 0:
                    if self.precision is not None or not self.reason:
                        raise ValueError("no predicted positives needs null precision and a reason")
                elif self.precision is None or self.reason is not None:
                    raise ValueError("predicted positives need precision and no undefined reason")
                elif self.precision != self.tp / (self.tp + self.fp):
                    raise ValueError("precision differs from its confusion counts")
            if self.tp is not None and self.fn is not None:
                if self.tp + self.fn == 0 or self.recall != self.tp / (self.tp + self.fn):
                    raise ValueError("recall differs from its confusion counts")
        return self


class MetricInterval(Model):
    lower: Finite | None
    upper: Finite | None
    reason: str | None

    @model_validator(mode="after")
    def check_bounds(self) -> Self:
        if self.lower is None or self.upper is None:
            if self.lower is not None or self.upper is not None or not self.reason:
                raise ValueError("an undefined interval needs two null bounds and a reason")
        elif self.lower > self.upper or self.reason is not None:
            raise ValueError("an interval needs ordered bounds and no undefined reason")
        return self


class BootstrapAudit(Model):
    method: Literal["paired held-out component percentile bootstrap"]
    rounds: Count
    valid_draws: Count
    one_class_draws: Count

    @model_validator(mode="after")
    def check_draws(self) -> Self:
        if self.valid_draws + self.one_class_draws != self.rounds:
            raise ValueError("bootstrap counts do not cover all draws")
        return self


class EvaluatedEncoder(Model):
    reading: EncoderReading
    vectors: VectorSource
    vector_sha256: Sha256
    vector_dtype: str
    calibration: OperatingPoint
    held_out: RankingMetrics
    held_out_operating_point: OperatingPoint
    held_out_ap_interval: MetricInterval
    held_out_ap_minus_reference: Finite
    held_out_ap_difference_interval: MetricInterval
    whole_data_descriptive: RankingMetrics


class EncoderEvaluation(Contract):
    __schema_stem__: ClassVar[str] = "encoder-evaluation"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-09",
            change="Declare the coverage, split, calibration and paired saved-vector report.",
            why="Model-written labels and dependent pairs need visible limits and provenance.",
        ),
    )
    version: str = "2026-10-09"
    written_at: Timestamp
    code_commit: CommitSha
    source_sha256: dict[RelPath, Sha256]
    runtime_versions: dict[str, str]
    settings: EvaluationSettings
    labels: LabelProvenance
    coverage: CoverageAudit
    split: SplitAudit
    bootstrap: BootstrapAudit
    encoders: list[EvaluatedEncoder]
    limitations: list[str]

    @model_validator(mode="after")
    def check_sample_identity(self) -> Self:
        if len(self.coverage.judged_ids) != self.settings.expected_judgments:
            raise ValueError("the report does not cover the configured judgment frame")
        partitions = self.split.calibration.pair_ids + self.split.held_out.pair_ids
        if set(partitions) != set(self.coverage.eligible_ids):
            raise ValueError("the split does not cover the eligible unique pairs")
        slugs = [encoder.reading.slug for encoder in self.encoders]
        if len(slugs) != len(set(slugs)) or self.settings.reference not in slugs:
            raise ValueError("encoder slugs must be unique and contain the reference")
        if self.labels.history_rows != len(self.coverage.judged_ids):
            raise ValueError("this evaluation requires one initial judgment per id")
        if sum(self.labels.labeler_counts.values()) != self.labels.history_rows:
            raise ValueError("labeler counts differ from judgment rows")
        if self.bootstrap.rounds != self.settings.bootstrap_rounds:
            raise ValueError("bootstrap rounds differ from the configured count")
        for encoder in self.encoders:
            if encoder.reading.slug != encoder.vectors.slug:
                raise ValueError("reading and vector slug differ")
            if encoder.calibration.threshold != encoder.held_out_operating_point.threshold:
                raise ValueError("held-out threshold differs from calibration")
            if encoder.calibration.threshold is not None:
                if (
                    encoder.calibration.precision is None
                    or encoder.calibration.precision < self.settings.precision_target
                ):
                    raise ValueError("calibration does not reach its configured precision target")
            for point, partition in (
                (encoder.calibration, self.split.calibration),
                (encoder.held_out_operating_point, self.split.held_out),
            ):
                if point.threshold is not None:
                    if (
                        point.tp is None or point.fn is None
                        or point.fp is None or point.tn is None
                        or point.tp + point.fn != partition.same
                        or point.fp + point.tn != partition.different
                    ):
                        raise ValueError("confusion counts differ from partition class counts")
        return self
