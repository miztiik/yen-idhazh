"""Metric observations with explicit basis, boundaries, and missing evidence."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, StrictInt, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    DateStamp,
    RunId,
    Sha256,
    Slug,
    Timestamp,
)

Count = Annotated[StrictInt, Field(ge=0)]
PositiveCount = Annotated[StrictInt, Field(gt=0)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class DiversityMetricRow(Contract):
    """One reproducible diversity reading, or a named reason it is unavailable."""

    __schema_stem__: ClassVar[str] = "feed-ingest-diversity"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-20",
            change="Declare diversity readings with explicit availability and basis.",
            why="Unavailable history and publication evidence must not look like zero.",
        ),
    )
    version: Literal["2026-10-20"] = "2026-10-20"

    date: DateStamp
    correlation_id: str = Field(min_length=1)
    run_id: RunId
    metric: Literal[
        "active_source_coverage",
        "selection_coverage",
        "effective_number_of_sources",
        "top_source_concentration",
        "source_gini",
        "source_kind_distribution",
        "lost_diversity_by_stage",
        "event_repetition_rate",
        "source_event_overlap",
        "novel_source_contribution",
    ]
    basis: Literal["eligible", "selected", "published", "leads", "stage"]
    as_of: Timestamp
    window_start: DateStamp | None
    window_end: DateStamp | None
    dimension: Literal["source", "source_kind", "event_cluster"] | None
    stage: Literal[
        "input",
        "freshness",
        "deduplication",
        "normalization",
        "selection",
        "publication",
        "lead_selection",
    ] | None
    window_days: PositiveCount | None
    dimension_value: Slug | None
    value: Finite | None
    unit: Literal["ratio", "count", "sources", "source_difference"]
    before_value: Finite | None
    after_value: Finite | None
    numerator: Count | None
    denominator: Count | None
    item_count: Count | None
    source_count: Count | None
    history_coverage_days: Count | None
    history_required_days: Count | None
    algorithm_version: str = Field(min_length=1)
    config_sha256: Sha256
    availability: Literal["available", "unavailable"]
    unavailable_reason: Literal[
        "empty_denominator",
        "incomplete_history",
        "missing_publication",
        "missing_event_evidence",
    ] | None
    top_k: Literal[1, 5, 10] | None = None

    @model_validator(mode="after")
    def validate_reading(self) -> Self:
        if self.date != self.as_of[:10]:
            raise ValueError("date must match the UTC as_of day")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("window boundaries are recorded together")
        if (
            self.window_start is not None
            and self.window_end is not None
            and self.window_start > self.window_end
        ):
            raise ValueError("window_start must not follow window_end")
        if self.availability == "available":
            if self.value is None or self.unavailable_reason is not None:
                raise ValueError("an available metric has a finite value and no missing reason")
        elif self.value is not None or self.unavailable_reason is None:
            raise ValueError("an unavailable metric has a reason and no value")
        if (self.numerator is None) != (self.denominator is None):
            raise ValueError("numerator and denominator are recorded together")
        if self.unit == "ratio" and self.value is not None and not 0.0 <= self.value <= 1.0:
            raise ValueError("ratio readings are in the range [0, 1]")
        if self.unit == "count" and self.value is not None:
            if self.value < 0 or not self.value.is_integer():
                raise ValueError("count readings are nonnegative integers")
        if self.unit == "sources" and self.value is not None and self.value < 0:
            raise ValueError("effective-source readings are nonnegative")
        if (self.history_coverage_days is None) != (self.history_required_days is None):
            raise ValueError("history coverage and its requirement are recorded together")
        if (
            self.history_coverage_days is not None
            and self.history_required_days is not None
            and self.history_coverage_days > self.history_required_days
        ):
            raise ValueError("history coverage cannot exceed the requested window")
        if self.basis == "stage" and self.stage is None:
            raise ValueError("stage-basis readings name their stage")
        if self.basis != "stage" and self.stage is not None:
            raise ValueError("only stage-basis readings name a stage")
        expected_units = {
            "active_source_coverage": {"ratio"},
            "selection_coverage": {"ratio"},
            "effective_number_of_sources": {"sources"},
            "top_source_concentration": {"ratio"},
            "source_gini": {"ratio"},
            "source_kind_distribution": {"count", "ratio"},
            "lost_diversity_by_stage": {"source_difference"},
            "event_repetition_rate": {"ratio"},
            "source_event_overlap": {"count", "ratio"},
            "novel_source_contribution": {"count", "ratio"},
        }
        if self.unit not in expected_units[self.metric]:
            raise ValueError("unit does not match the metric")
        if (self.metric == "top_source_concentration") != (self.top_k is not None):
            raise ValueError("top-source concentration records its configured k")
        if self.metric == "source_kind_distribution":
            if self.dimension != "source_kind" or self.dimension_value is None:
                raise ValueError("source-kind distribution names its kind or unknown bucket")
        elif self.dimension_value is not None:
            raise ValueError("only source-kind distribution names a dimension value")
        if self.metric == "lost_diversity_by_stage":
            if self.before_value is None or self.after_value is None or self.value is None:
                raise ValueError("lost diversity records before, after, and signed difference")
            if self.before_value < 0 or self.after_value < 0:
                raise ValueError("lost-diversity before and after readings are nonnegative")
            if self.value != self.before_value - self.after_value:
                raise ValueError("lost-diversity value equals before minus after")
        elif self.before_value is not None or self.after_value is not None:
            raise ValueError("only lost-diversity readings carry before and after values")
        if self.metric in {
            "event_repetition_rate",
            "source_event_overlap",
            "novel_source_contribution",
        } and self.window_days is None:
            raise ValueError("history-dependent metrics identify their configured UTC window")
        return self
