"""Which population and acquisition evidence produced each independently judged pair?"""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Sha256, Timestamp
from idhazh.contracts.story_source import ArticleEvidence, ArticleId, Nonempty, SourceCheck


class NeighborEvidence(Model):
    model: Nonempty
    query: ArticleId
    rank: Annotated[int, Field(ge=1)]
    cosine: Annotated[float, Field(ge=-1.00001, le=1.00001)]
    vector_sha256: Sha256
    query_vector_sha256: Sha256 | None = Field(default=None, exclude_if=lambda value: value is None)
    neighbor_vector_sha256: Sha256 | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CandidatePair(Model):
    id: Annotated[str, Field(pattern=r"^pair-[0-9a-f]{64}$")]
    a: ArticleId
    b: ArticleId
    representative_probability: Annotated[float | None, Field(gt=0, le=1)] = None
    challenge_tags: list[Nonempty] = Field(default_factory=list)
    ranks: list[NeighborEvidence] = Field(default_factory=list)
    missing_vector_articles: list[ArticleId] = Field(default_factory=list)
    source_checks: list[SourceCheck] = Field(default_factory=list)
    acquisition_notes: list[Nonempty] = Field(default_factory=list)


class ChallengeProposal(Model):
    a: ArticleId
    b: ArticleId
    tags: Annotated[list[Nonempty], Field(min_length=1)]
    reason: Nonempty
    source_checks: list[SourceCheck] = Field(default_factory=list)


class ChallengeAddition(Model):
    source_sha256: Sha256
    expected_frame_sha256: Sha256
    proposals: Annotated[list[ChallengeProposal], Field(min_length=1)]


class PairFrame(Model):
    source_sha256: Sha256
    population: Literal["all-unordered-distinct-frozen-archive-articles"]
    population_size: Annotated[int, Field(ge=1)]
    sampling: Literal["independent-bernoulli-geometric-skip"]
    seed: int
    representative_probability: Annotated[float, Field(gt=0, le=1)]
    pairs: list[CandidatePair]
    vector_manifest_sha256: Sha256 | None = None


class PairDecision(Model):
    input_sha256: Sha256
    topic: Literal["shared", "different", "unresolved"]
    event: Literal["shared", "different", "unresolved"]
    story: Literal["shared", "different", "unresolved"]
    occurrence: Literal["same", "different", "partial", "unresolved"]
    coverage: Literal["duplicate", "partial", "different", "unresolved"]
    reason: Nonempty
    unresolved_reasons: list[Nonempty] = Field(default_factory=list)
    review_flags: list[Nonempty] = Field(default_factory=list)
    source_checks: list[SourceCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_duplicate(self) -> Self:
        if self.coverage == "duplicate" and self.occurrence != "same":
            raise ValueError("whole-article duplicates require the same occurrence")
        values = (self.topic, self.event, self.story, self.occurrence, self.coverage)
        if "unresolved" in values and not self.unresolved_reasons:
            raise ValueError("unresolved relation needs a reason")
        if self.story == "shared" and (self.event != "shared" or self.topic != "shared"):
            raise ValueError("shared story requires its typed event/topic path")
        return self


class PairEvidence(Model):
    pair_id: str
    input_sha256: Sha256
    a: ArticleEvidence
    b: ArticleEvidence


class PairWorkerBatch(Model):
    batch_id: Sha256
    source_sha256: Sha256
    frame_sha256: Sha256
    pairs: list[PairEvidence]
    instructions: Nonempty
    operation: Literal["primary", "review"] = "primary"
    review_targets: dict[str, Sha256] = Field(default_factory=dict)
    correction_targets: dict[str, Sha256] = Field(default_factory=dict)
    independent_of_workers: list[Nonempty] = Field(default_factory=list)


class PairSubmission(Model):
    batch_id: Sha256
    source_sha256: Sha256
    label_source: Literal["model"] = "model"
    labeler: Literal["gpt-6.1-sol"] = "gpt-6.1-sol"
    worker_id: Nonempty
    decisions: dict[str, PairDecision]
    supersedes: dict[str, Sha256] = Field(default_factory=dict)
    operation: Literal["primary", "review"] = "primary"
    independent_of: list[Nonempty] = Field(default_factory=list)


class PairRecord(Model):
    record_id: Sha256
    recorded_at: Timestamp
    submission_sha256: Sha256
    worker_id: Nonempty
    labeler: Literal["gpt-6.1-sol"]
    label_source: Literal["model"] = "model"
    pair_id: str
    frame_sha256: Sha256
    supersedes: Sha256 | None = None
    decision: PairDecision
    operation: Literal["primary", "review"] = "primary"
    review_target: Sha256 | None = None
    independent_of: list[Nonempty] = Field(default_factory=list)


class VectorCache(Model):
    slug: Nonempty
    file: Nonempty
    file_sha256: Sha256
    rows: Annotated[int, Field(gt=0)]
    dimensions: Annotated[int, Field(gt=0)]
    reading_sha256: Sha256
    input_sha256: Sha256
    model_id: Nonempty
    revision: str | None
    settings_sha256: Sha256


class VectorManifest(Model):
    source_sha256: Sha256
    input_sha256: Sha256
    input_file: Nonempty
    readings_file: Nonempty
    readings_sha256: Sha256
    encoder_config_file: Nonempty
    encoder_config_sha256: Sha256
    max_sequence_length: Annotated[int, Field(gt=0)]
    article_ids: list[ArticleId]
    text_sha256: list[Sha256]
    missing_article_ids: list[ArticleId]
    text_conflict_article_ids: list[ArticleId] = Field(default_factory=list)
    caches: list[VectorCache]
    extensions: list["VectorExtension"] = Field(default_factory=list)


class VectorExtension(Model):
    source_sha256: Sha256
    slug: Nonempty
    article_ids: list[ArticleId]
    article_input_sha256: list[Sha256]
    summary_sha256: list[Sha256]
    cache: VectorCache
    runtime_versions: dict[str, Nonempty]


class VectorOrder(Model):
    article_ids: list[ArticleId]
    source_input_sha256: Sha256
    vectors_sha256: dict[str, Sha256]
    original_vector_sha256: dict[str, Sha256]
