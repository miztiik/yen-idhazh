"""Which authored global settings control the isolated feed planner?"""

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
NonEmpty = Annotated[str, Field(min_length=1)]
Relaxation = Literal["distinct_sources", "source_share"]
BrowserHeaders = Annotated[
    dict[str, Annotated[str, Field(min_length=1, pattern=r"^[\x20-\x7e]+$")]],
    Field(json_schema_extra={"propertyNames": {"type": "string"}}),
]


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


class FeedCurationPolicy(Model):
    """Which source opportunity and scoring settings apply to one candidate?"""

    source_authority_weight: NonNegative
    base_source_allowance: Count
    bonus_unique_evidence: Count
    mmr_weights: FeedPenaltyWeights


def describe_patch_input(schema: dict[str, Any]) -> None:
    """Expose omitted fields, not the internal absent-value marker, in JSON Schema."""
    for field in schema.get("properties", {}).values():
        if field.get("default", ...) is None:
            field.pop("default")
            branches = [branch for branch in field.pop("anyOf") if branch != {"type": "null"}]
            field.update(branches[0] if len(branches) == 1 else {"anyOf": branches})


class PlanningRunOverrides(Model):
    """Only an explicit freshness value overrides the planner's global policy."""

    model_config = ConfigDict(json_schema_extra=describe_patch_input)
    freshness_hours: Positive | None = None

    @model_validator(mode="before")
    @classmethod
    def refuse_null_fields(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            for name, field in value.items():
                if field is None:
                    raise ValueError(f"{name} must be omitted to inherit, not null")
        return value


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


class FeedRequestHeaders(Model):
    """Which navigation headers can recover an otherwise permitted request?"""

    primary: BrowserHeaders
    secondary: BrowserHeaders | None
    recoverable_http_statuses: list[Annotated[int, Field(strict=True, ge=400, le=599)]]
    recovery_min_body_bytes: Count

    @field_validator("primary", "secondary")
    @classmethod
    def validate_browser_headers(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return value
        # Navigation metadata cannot replace request authority, credentials or crawler identity.
        permitted = {
            "user-agent", "accept", "accept-language", "sec-ch-ua", "sec-ch-ua-mobile",
            "sec-ch-ua-platform",
            "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-fetch-user",
            "upgrade-insecure-requests",
        }
        if not value:
            raise ValueError("a browser header profile must not be empty")
        if value.keys() - permitted:
            raise ValueError("unsupported browser header")
        return value

    @field_validator("recoverable_http_statuses")
    @classmethod
    def validate_recovery_statuses(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("recoverable_http_statuses must not repeat a status")
        return value


class FeedMetadataSelector(Model):
    selector: NonEmpty
    attribute: NonEmpty | None


class FeedSemanticFallbackConfig(Model):
    """Which actual page elements can supply fallback prose and metadata?"""

    content_roots: Annotated[list[NonEmpty], Field(min_length=1)]
    remove_elements: Annotated[list[NonEmpty], Field(min_length=1)]
    paragraph_elements: Annotated[list[NonEmpty], Field(min_length=1)]
    min_root_chars: Count
    min_paragraph_chars: Count
    title_sources: Annotated[list[FeedMetadataSelector], Field(min_length=1)]
    author_sources: Annotated[list[FeedMetadataSelector], Field(min_length=1)]


class FeedHarvestConfig(Model):
    concurrency: PositiveCount
    fetch_timeout_ms: PositiveCount
    tidy_urls: bool = Field(
        strict=True,
        description=(
            "Clean request targets only. Remove this switch and the disabled path "
            "when request cleanup becomes mandatory."
        ),
    )
    user_agent: NonEmpty
    request_headers: FeedRequestHeaders
    semantic_fallback: FeedSemanticFallbackConfig
    blocked_categories: list[NonEmpty]
    url_exclusions: list[FeedUrlExclusion]


class FeedTriageConfig(FeedScreeningPolicy):
    blocked_http_statuses: list[Annotated[int, Field(strict=True, ge=100, le=599)]]


class FeedSoftCaps(Model):
    max_source_share: Share
    max_parent_domain_share: Share
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


class FeedFeedbackConfig(Model):
    lifecycle_window_days: PositiveCount = 31
    request_report_closed_days: PositiveCount = 7


class FeedIngestConfig(Model):
    version: Literal["2026-10-20"]
    harvest: FeedHarvestConfig
    triage: FeedTriageConfig
    curate: FeedCurateConfig
    partition: FeedPartitionConfig
    seal: FeedSealConfig
    workflow_reporting: FeedWorkflowReportingConfig
    feedback: FeedFeedbackConfig = Field(
        default_factory=FeedFeedbackConfig, json_schema_extra={"default": {}},
    )
