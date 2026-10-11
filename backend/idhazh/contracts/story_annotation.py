"""How are equal memberships, proposed identities and independent reviews recorded?"""

from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    Model,
    RelPath,
    SchemaVersion,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.story_source import ArticleEvidence, ArticleId, Nonempty, SourceCheck

Kind = Literal["topic", "event", "story", "occurrence"]
EntityId = Annotated[str, Field(pattern=r"^(topic|event|story|occurrence)-[0-9a-f]{64}$")]
Ref = Annotated[
    str, Field(pattern=r"^((topic|event|story|occurrence)-[0-9a-f]{64}|proposal:[a-z0-9-]+)$")
]


class Identity(Model):
    id: EntityId
    kind: Kind
    name: Nonempty
    identity_key: Nonempty
    parent_ids: list[EntityId]
    definition: Nonempty
    evidence_article_ids: Annotated[list[ArticleId], Field(min_length=1)]


class IdentityProposal(Model):
    ref: Annotated[str, Field(pattern=r"^proposal:[a-z0-9-]+$")]
    kind: Kind
    name: Nonempty
    parent_refs: list[Ref]
    definition: Nonempty
    evidence_article_ids: Annotated[list[ArticleId], Field(min_length=1)]


class Membership(Model):
    topic: Ref
    event: Ref
    story: Ref
    occurrence_refs: list[Ref] = Field(default_factory=list)
    evidence: Nonempty


class ArticleDecision(Model):
    input_sha256: Sha256
    state: Literal["annotated", "unresolved"]
    memberships: list[Membership]
    reason: Nonempty
    unresolved_reasons: list[Nonempty] = Field(default_factory=list)
    review_flags: list[Nonempty] = Field(default_factory=list)
    source_checks: list[SourceCheck] = Field(default_factory=list)
    summary_evidence: Literal["full-stored-summary"] = "full-stored-summary"

    @model_validator(mode="after")
    def check_resolution(self) -> Self:
        if self.state == "annotated" and (not self.memberships or self.unresolved_reasons):
            raise ValueError("annotated needs supported memberships and no unresolved reasons")
        if self.state == "unresolved" and not self.unresolved_reasons:
            raise ValueError("unresolved needs explicit reasons")
        paths = [(p.topic, p.event, p.story) for p in self.memberships]
        if len(paths) != len(set(paths)):
            raise ValueError("duplicate memberships; all memberships have equal status")
        return self


class WorkerBatch(Model):
    version: Literal["2026-10-09"] = "2026-10-09"
    batch_id: Sha256
    source_sha256: Sha256
    policy_sha256: Sha256
    operation: Literal["primary", "review"]
    catalog_revision: Sha256
    articles: Annotated[list[ArticleEvidence], Field(min_length=1)]
    review_targets: dict[ArticleId, Sha256] = Field(default_factory=dict)
    correction_targets: dict[ArticleId, Sha256] = Field(default_factory=dict)
    independent_of_workers: list[Slug] = Field(default_factory=list)
    instructions: Nonempty


class WorkerSubmission(Model):
    batch_id: Sha256
    source_sha256: Sha256
    catalog_revision: Sha256
    label_source: Literal["model"] = "model"
    labeler: Literal["gpt-6.1-sol"] = "gpt-6.1-sol"
    worker_id: Slug
    operation: Literal["primary", "review"]
    independent_of: list[Slug] = Field(default_factory=list)
    proposals: list[IdentityProposal] = Field(default_factory=list)
    decisions: dict[ArticleId, ArticleDecision]
    supersedes: dict[ArticleId, Sha256] = Field(default_factory=dict)


class AnnotationRecord(Model):
    record_id: Sha256
    recorded_at: Timestamp
    submission_sha256: Sha256
    batch_id: Sha256
    article_id: ArticleId
    operation: Literal["primary", "review"]
    label_source: Literal["model"]
    labeler: Literal["gpt-6.1-sol"]
    worker_id: Slug
    independent_of: list[Slug]
    supersedes: Sha256 | None = None
    review_target: Sha256 | None = None
    decision: ArticleDecision


class CatalogSnapshot(Model):
    revision: Sha256
    entities: list[Identity]
    aliases: dict[EntityId, EntityId] = Field(default_factory=dict)
    proposal_resolutions: dict[str, EntityId] = Field(default_factory=dict)


class CatalogReview(Model):
    expected_revision: Sha256
    reviewer: Nonempty
    label_source: Literal["model"] = "model"
    reason: Nonempty
    entities: list[Identity] = Field(default_factory=list)
    aliases: dict[EntityId, EntityId] = Field(default_factory=dict)
    proposal_resolutions: dict[str, EntityId] = Field(default_factory=dict)
    source_checks: list[SourceCheck] = Field(default_factory=list)


class CheckpointFile(Model):
    path: RelPath
    sha256: Sha256
    bytes: Annotated[int, Field(ge=0)]
    rows: Annotated[int, Field(ge=0)]


class CheckpointArtifact(Model):
    kind: Literal["batch", "pair-batch", "submission", "pair-submission"]
    id: Sha256
    payload: JsonValue


class CheckpointRecord(Model):
    sequence: Annotated[int, Field(gt=0)]
    kind: Literal["annotation", "review", "pair", "pair-review", "catalog-review"]
    id: Sha256
    subject: str
    payload: JsonValue


class DatasetCheckpoint(Contract):
    __schema_stem__ = "story-dataset-checkpoint"
    __changelog__ = (
        ChangelogEntry(
            version="2026-10-10",
            change="Freeze consistent typed histories and compact resumable worker artifacts.",
            why="A local main checkpoint must not depend on a mutable worker database.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    recorded_at: Timestamp
    source_sha256: Sha256
    policy_sha256: Sha256
    files: dict[Literal["artifacts", "history", "catalog", "vectors", "partition"], CheckpointFile]
    settings: dict[str, str]
    submission_bindings: dict[
        Literal["batch-submission", "pair-batch-submission"], dict[Sha256, Sha256]
    ]
    omitted_artifacts: dict[str, list[Sha256]]
    notice: Literal[
        "Partial model-labeled dataset; not human gold, acceptance, or an encoder winner."
    ] = "Partial model-labeled dataset; not human gold, acceptance, or an encoder winner."
