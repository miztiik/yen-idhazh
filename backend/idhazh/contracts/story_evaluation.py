"""When can a fresh article-neighbor or overlapping-cluster measurement be reported?"""

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from idhazh.contracts.base import Model, Sha256, Timestamp
from idhazh.contracts.story_source import ArticleId, Nonempty


class StoryPolicy(Model):
    expected_articles: Annotated[int, Field(gt=0)]
    expected_bytes: Annotated[int, Field(gt=0)]
    expected_sha256: Sha256
    batch_size: Annotated[int, Field(gt=0)]
    top_k: Annotated[int, Field(gt=0)]
    block_size: Annotated[int, Field(gt=0, le=512)]
    random_audit_fraction: Annotated[float, Field(ge=0, le=1)]
    representative_pair_probability: Annotated[float, Field(gt=0, le=1)]
    seed: int
    development_fraction: Annotated[float, Field(gt=0, lt=1)]
    metadata_neighbors: Annotated[int, Field(ge=0)]
    acceptance_status: Literal["unapproved"] = "unapproved"
    approved_semantics: list[Nonempty]
    engineering_defaults_notice: Nonempty
    stages: list[Nonempty]
    vector_files: dict[str, Nonempty]
    encoding_threads: Annotated[int, Field(ge=1)] = 2
    encoding_batch_size: Annotated[int, Field(ge=1)] = 16


class Partition(Model):
    source_sha256: Sha256
    catalog_revision: Sha256
    annotation_state_sha256: Sha256
    seed: int
    article_partitions: dict[ArticleId, Literal["development", "confirmation", "quarantine"]]
    component_ids: dict[ArticleId, Sha256]
    regression_article_ids: list[ArticleId]
    blocked_reasons: list[Nonempty]
    quarantine_reasons: dict[
        ArticleId,
        list[
            Literal[
                "unknown-membership",
                "regression-exposure",
                "new-crossing-link",
            ]
        ],
    ] = Field(default_factory=dict)
    crossing_policy: Literal["quarantine-entire-component-never-redraw"] = (
        "quarantine-entire-component-never-redraw"
    )
    article_exposure: dict[ArticleId, Literal["development", "confirmation"]] = Field(
        default_factory=dict, exclude_if=lambda value: not value
    )


class RetrievalRun(Model):
    source_sha256: Sha256
    partition_sha256: Sha256
    vector_manifest_sha256: Sha256
    partition: Literal["development", "confirmation"]
    model: Nonempty
    relation: Literal["topic", "event", "story", "occurrence", "duplicate"]
    k: Annotated[int, Field(ge=1)]
    candidate_article_ids: Annotated[list[ArticleId], Field(min_length=2)]
    rankings: dict[ArticleId, list[ArticleId]]
    development_config_sha256: Sha256


class DevelopmentConfig(Model):
    source_sha256: Sha256
    partition_sha256: Sha256
    frozen_at: Timestamp
    parameters: dict[str, JsonValue]
    reason: Nonempty
    scope: Literal["development-only-no-confirmation-labels"] = (
        "development-only-no-confirmation-labels"
    )


class ClusterRun(Model):
    source_sha256: Sha256
    partition_sha256: Sha256
    vector_manifest_sha256: Sha256
    partition: Literal["development", "confirmation"]
    level: Literal["topic", "event", "story"]
    model: Nonempty
    memberships: dict[ArticleId, Annotated[list[Nonempty], Field(min_length=1)]]
    algorithm: Nonempty
    development_config_sha256: Sha256
    development_config_partition_sha256: Sha256
    parameters_frozen_before_confirmation: Literal[True]


class EvaluationReport(Model):
    source_sha256: Sha256
    state: Literal["blocked", "pilot-measured"]
    scope: Literal["declared-candidate-article-universe-not-full-archive"]
    acceptance_status: Literal["unapproved"] = "unapproved"
    blockers: list[Nonempty]
    metrics: dict[str, float]
    evaluated_queries: int
    evaluated_articles: int
    representative_pairs_judged: int
    challenge_pairs_judged: int
    limitations: list[Nonempty]


class DatasetStatus(Model):
    source_sha256: Sha256
    total_articles: int
    rows_visited: int
    annotated: int
    unresolved: int
    catalog_pending: int
    unvisited: int
    independently_reviewed: int
    review_conflicts: int
    history_records: int
    pairs_judged: int
    pairs_independently_reviewed: int = 0
    pair_review_conflicts: int = 0
    vector_covered: int
    vector_missing: int
    acceptance_status: Literal["unapproved"] = "unapproved"
    full_archive_evaluation: Literal["blocked"] = "blocked"
