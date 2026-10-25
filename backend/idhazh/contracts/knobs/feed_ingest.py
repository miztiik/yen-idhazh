"""Which authored settings control feed planning and its per-vertical policy patches?"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from idhazh.contracts.base import Model

# JSON numbers cross into JavaScript; larger integers cannot retain their identity.
MAX_JSON_INTEGER = 2**53 - 1
PositiveCount = Annotated[int, Field(strict=True, gt=0, le=MAX_JSON_INTEGER)]
Count = Annotated[int, Field(strict=True, ge=0, le=MAX_JSON_INTEGER)]
Positive = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
NonNegative = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Share = Annotated[float, Field(strict=True, gt=0, le=1, allow_inf_nan=False)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
NonEmpty = Annotated[str, Field(min_length=1)]
Relaxation = Literal["distinct_sources", "source_share"]


class FeedScreeningPolicy(Model):
    """Which word-count and age settings apply to one candidate?"""

    min_words_article: PositiveCount
    min_words_abstract: PositiveCount
    max_age_hours: Positive
    recency_half_life_hours: Positive
    recency_weight: NonNegative


class FeedPenaltyWeights(Model):
    """How strongly does each independent portfolio dimension affect selection?"""

    lambda_source: NonNegative
    lambda_source_kind: NonNegative
    lambda_domain: NonNegative
    lambda_vertical: NonNegative
    lambda_desk: NonNegative
    lambda_lens: NonNegative
    lambda_event_type: NonNegative
    lambda_event_cluster: NonNegative
    lambda_entity: NonNegative
    lambda_coverage: NonNegative


class FeedCurationPolicy(Model):
    """Which source opportunity and scoring settings apply to one candidate?"""

    source_authority_weight: NonNegative
    base_source_allowance: Count
    bonus_uncovered_event_cluster: Count
    bonus_underrepresented_vertical: Count
    bonus_unique_evidence: Count
    mmr_weights: FeedPenaltyWeights


def describe_patch_input(schema: dict[str, Any]) -> None:
    """Expose omitted fields, not the internal absent-value marker, in JSON Schema."""
    for field in schema.get("properties", {}).values():
        if field.get("default", ...) is None:
            field.pop("default")
            branches = [branch for branch in field.pop("anyOf") if branch != {"type": "null"}]
            field.update(branches[0] if len(branches) == 1 else {"anyOf": branches})


class PolicyPatch(Model):
    """An omitted field inherits; an explicit null is invalid."""

    model_config = ConfigDict(json_schema_extra=describe_patch_input)

    @model_validator(mode="before")
    @classmethod
    def refuse_null_fields(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            for name, field in value.items():
                if field is None:
                    raise ValueError(f"{name} must be omitted to inherit, not null")
        return value


# None is only the in-memory marker for a field absent from authored JSON.
class FeedScreeningPatch(PolicyPatch):
    min_words_article: PositiveCount | None = None
    min_words_abstract: PositiveCount | None = None
    max_age_hours: Positive | None = None
    recency_half_life_hours: Positive | None = None
    recency_weight: NonNegative | None = None


class FeedPenaltyWeightsPatch(PolicyPatch):
    lambda_source: NonNegative | None = None
    lambda_source_kind: NonNegative | None = None
    lambda_domain: NonNegative | None = None
    lambda_vertical: NonNegative | None = None
    lambda_desk: NonNegative | None = None
    lambda_lens: NonNegative | None = None
    lambda_event_type: NonNegative | None = None
    lambda_event_cluster: NonNegative | None = None
    lambda_entity: NonNegative | None = None
    lambda_coverage: NonNegative | None = None


class FeedCurationPatch(PolicyPatch):
    source_authority_weight: NonNegative | None = None
    base_source_allowance: Count | None = None
    bonus_uncovered_event_cluster: Count | None = None
    bonus_underrepresented_vertical: Count | None = None
    bonus_unique_evidence: Count | None = None
    mmr_weights: FeedPenaltyWeightsPatch | None = None


class VerticalPolicyOverride(PolicyPatch):
    triage: FeedScreeningPatch | None = None
    curate: FeedCurationPatch | None = None


class PlanningRunOverrides(PolicyPatch):
    freshness_hours: Positive | None = None


class EffectiveFeedPolicy(Model):
    triage: FeedScreeningPolicy
    curate: FeedCurationPolicy


class FeedUrlExclusion(Model):
    """Which host and path does the isolated planner exclude before an article request?"""

    host: Annotated[str, Field(
        pattern=re.compile(
            r"^(?=.{1,253}\.?$)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
            r"(?:\.[a-zA-Z0-9](?:[-0-9a-zA-Z]{0,61}[0-9a-zA-Z])?)*\.?$"
        ),
        json_schema_extra={"format": "hostname"},
    )]
    path_prefix: Annotated[str, Field(
        pattern=r"^\/.*", json_schema_extra={"format": "starts_with"},
    )]
    include_subdomains: bool = Field(strict=True)

    @field_validator("path_prefix")
    @classmethod
    def validate_path_prefix(cls, value: str) -> str:
        if (
            not value.isascii()
            or any(ord(char) <= 32 or ord(char) == 127 or char in '?#\\`{}<>"' for char in value)
            or value.startswith("//")
            or (value != "/" and value.endswith("/"))
            or re.search(r"(?:^|/)(?:\.|%2e){1,2}(?:/|$)", value, re.IGNORECASE)
        ):
            raise ValueError(
                "path_prefix must be an absolute path without query, fragment, "
                "dot segments or trailing slash"
            )
        return value


class FeedHarvestConfig(Model):
    concurrency: PositiveCount
    fetch_timeout_ms: PositiveCount
    user_agent: NonEmpty
    blocked_categories: list[NonEmpty]
    url_exclusions: list[FeedUrlExclusion]


class FeedTriageConfig(FeedScreeningPolicy):
    blocked_http_statuses: list[Annotated[int, Field(strict=True, ge=100, le=599)]]


class FeedSoftCaps(Model):
    max_source_share: Share
    max_parent_domain_share: Share
    max_event_cluster_items: PositiveCount
    min_distinct_sources: PositiveCount
    relaxation_order: list[Relaxation]

    @model_validator(mode="after")
    def refuse_repeated_limits(self) -> Self:
        if len(set(self.relaxation_order)) != len(self.relaxation_order):
            raise ValueError("relaxation_order must not repeat a limit")
        return self


class FeedCurateConfig(FeedCurationPolicy):
    article_limit: PositiveCount | None
    source_reliability_penalty_enabled: bool = Field(
        default=True,
        strict=True,
        description=(
            "Apply measured source reliability separately from article quality. Remove this switch "
            "and its disabled path when isolated selection becomes the sole planner."
        ),
    )
    soft_caps: FeedSoftCaps
    exploration_slot_share: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class FeedPartitionConfig(Model):
    default_strategy: Literal["bin-pack", "round-robin", "none"]
    default_shards: PositiveCount
    min_shards: PositiveCount
    max_shards: PositiveCount

    @model_validator(mode="after")
    def check_shard_bounds(self) -> Self:
        if self.min_shards > self.max_shards:
            raise ValueError("min_shards exceeds max_shards")
        if not self.min_shards <= self.default_shards <= self.max_shards:
            raise ValueError("default_shards must be within min_shards and max_shards")
        return self


class FeedSealConfig(Model):
    dispatches_prefix: Annotated[list[Slug], Field(min_length=1)]
    rejections_prefix: Annotated[list[Slug], Field(min_length=1)]
    compression: Literal["snappy", "zstd", "none"]


class FeedWorkflowReportingConfig(Model):
    enabled: bool = Field(
        default=True,
        strict=True,
        description=(
            "External reporting only. Remove this key, adapter, tests, and workflow invocation "
            "together when development reporting is no longer needed."
        ),
    )
    removal_condition: NonEmpty


class FeedMetricsConfig(Model):
    rolling_window_days: PositiveCount
    overlap_windows_days: Annotated[list[PositiveCount], Field(min_length=1)]
    top_source_counts: Annotated[list[PositiveCount], Field(min_length=1)]


class FeedFeedbackConfig(Model):
    lifecycle_window_days: PositiveCount = 31
    window_days: PositiveCount = 7
    minimum_measured_opportunities: PositiveCount = 20
    minimum_measured_coverage: Annotated[
        float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    ] = 0.8
    request_weight: NonNegative = 1 / 3


class PlanningVertical(Model):
    model_config = ConfigDict(extra="ignore")
    id: Slug


class PlanningTaxonomy(Model):
    """Read only the taxonomy fields this configuration reader computes on."""

    model_config = ConfigDict(extra="ignore")
    verticals: Annotated[list[PlanningVertical], Field(min_length=1)]

    @model_validator(mode="after")
    def refuse_duplicate_verticals(self) -> Self:
        ids = [vertical.id for vertical in self.verticals]
        if len(set(ids)) != len(ids):
            raise ValueError("verticals contains duplicate ids")
        return self


class FeedIngestConfig(Model):
    version: Literal["2026-10-20"]
    harvest: FeedHarvestConfig
    triage: FeedTriageConfig
    curate: FeedCurateConfig
    vertical_overrides: dict[Slug, VerticalPolicyOverride]
    partition: FeedPartitionConfig
    seal: FeedSealConfig
    workflow_reporting: FeedWorkflowReportingConfig
    metrics: FeedMetricsConfig
    feedback: FeedFeedbackConfig = Field(
        default_factory=FeedFeedbackConfig, json_schema_extra={"default": {}},
    )

    def validate_verticals(self, taxonomy: PlanningTaxonomy) -> None:
        """Refuse a planning patch that names an unconfigured vertical."""
        ids = {vertical.id for vertical in taxonomy.verticals}
        for vertical in self.vertical_overrides:
            if vertical not in ids:
                raise ValueError(f"vertical_overrides.{vertical}: unknown taxonomy vertical")
