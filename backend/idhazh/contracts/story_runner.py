"""Which exact missing inputs, runtime and returned files belong to an approved runner shard?"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, model_validator

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
from idhazh.contracts.encoder_reading import EncoderReading
from idhazh.contracts.story_encoder_candidate import CandidateVectorUnit, PinnedEncoderCandidate
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_source import ArticleEvidence, ArticleId, SourceFreeze
from idhazh.contracts.story_vectors import VectorExtensionSnapshot


class RunnerFile(Model):
    version: SchemaVersion = "2026-10-11"
    path: RelPath
    sha256: Sha256
    bytes: Annotated[int, Field(ge=0)]


class RunnerShard(Contract):
    __schema_stem__ = "story-runner-shard"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Bind missing-only runner inputs and lineage.",
            why="A runner must not rediscover a different archive window.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    shard: Slug
    source: SourceFreeze
    policy: StoryPolicy
    parent_revision: Sha256
    candidate: PinnedEncoderCandidate | None = None
    reading: EncoderReading | None = None
    articles: Annotated[list[ArticleEvidence], Field(min_length=1, max_length=400)]
    ordered_ids_sha256: Sha256
    prefixed_texts_sha256: Sha256
    unit_rows: Annotated[int, Field(ge=1, le=20)] = 20
    dimensions: Annotated[int, Field(gt=0)]
    roles: Literal["symmetric-query-and-candidate"] = "symmetric-query-and-candidate"
    model_files: list[RunnerFile] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_source_and_encoder(self) -> Self:
        if (self.candidate is None) == (self.reading is None):
            raise ValueError("name exactly one pinned candidate or saved encoder reading")
        if (
            self.source.source_sha256 != self.policy.expected_sha256
            or self.source.articles != self.policy.expected_articles
            or self.source.source_bytes != self.policy.expected_bytes
            or len({a.article_id for a in self.articles}) != len(self.articles)
            or self.unit_rows != self.policy.batch_size
        ):
            raise ValueError("source, policy or distinct bounded unit inputs differ")
        if self.candidate and (
            self.candidate.source_sha256 != self.source.source_sha256
            or self.candidate.dimensions != self.dimensions
        ):
            raise ValueError("candidate source or native dimensions differ")
        if self.reading and self.reading.numbers_an_article != self.dimensions:
            raise ValueError("saved reading dimensions differ")
        return self

    @property
    def encoder(self) -> PinnedEncoderCandidate | EncoderReading:
        value = self.candidate or self.reading
        assert value is not None
        return value


class RunnerPackage(Contract):
    __schema_stem__ = "story-runner-package"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Hash exact outbound files without granting consent.",
            why="Preparing a file is not permission to disclose it.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    prepared_at: Timestamp
    source_sha256: Sha256
    code_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    files: list[RunnerFile]
    shards: dict[Slug, RelPath]
    code_files: list[RunnerFile]
    runtime_lock: RunnerFile
    runtime_versions: dict[str, str]
    runner_cpus: Literal[4] = 4
    runner_min_memory_bytes: Annotated[int, Field(gt=0)] = 15_000_000_000
    consent: Literal["not-granted-by-this-manifest"] = "not-granted-by-this-manifest"


class RunnerRuntimeLock(Contract):
    __schema_stem__ = "story-runner-runtime-lock"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Pin Linux CPU wheels and dependency metadata.",
            why="Windows wheel hashes cannot lock a Linux inference runtime.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    python: Literal["3.14"] = "3.14"
    platform: Literal["linux-x86_64"] = "linux-x86_64"
    versions: dict[str, str]
    wheels: dict[str, RunnerFile]
    urls: dict[str, str]
    metadata_sha256: dict[str, Sha256]


class RunnerResult(Contract):
    __schema_stem__ = "story-runner-result"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Describe complete and pending immutable runner units.",
            why="Partial jobs preserve only validated completed rows.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    shard_sha256: Sha256
    package_sha256: Sha256
    shard: Slug
    code_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    run_id: Annotated[str, Field(pattern=r"^[0-9]+$")]
    run_attempt: Annotated[str, Field(pattern=r"^[0-9]+$")]
    repository: str
    started_at: Timestamp
    finished_at: Timestamp
    runtime_versions: dict[str, str]
    model_files: list[RunnerFile]
    host: dict[str, str]
    files: list[RunnerFile]
    units: list[CandidateVectorUnit | VectorExtensionSnapshot]
    pending_article_ids: list[ArticleId]
    state: Literal["complete", "partial", "failed"]
    error: str | None = None
    resumed_from: Sha256 | None = None
