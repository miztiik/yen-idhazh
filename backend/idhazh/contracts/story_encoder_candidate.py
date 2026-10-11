"""Which new pinned encoder runs are distinct from unproven historical control vectors?"""

from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, JsonValue, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    Contract,
    RelPath,
    SchemaVersion,
    Sha256,
    Slug,
    Timestamp,
)
from idhazh.contracts.story_source import SourceCheck
from idhazh.contracts.story_vectors import VectorExtensionSnapshot

Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class PinnedEncoderCandidate(Contract):
    __schema_stem__ = "story-pinned-encoder-candidate"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Register new pinned candidates without claiming historical vector provenance.",
            why="Current revisions cannot prove which historical weights produced a vector.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    registered_at: Timestamp
    source_sha256: Sha256
    legacy_vector_revision: Sha256
    legacy_slug: Slug
    legacy_reading_sha256: Sha256
    legacy_model_revision: str | None
    slug: Slug
    model_id: str
    revision: Revision
    prefix: str
    model_options: dict[str, JsonValue]
    encode_options: dict[str, JsonValue]
    dimensions: Annotated[int, Field(gt=0)]
    max_sequence_length: Literal[256]
    dtype: Literal["float32"] = "float32"
    roles: Literal["symmetric-query-and-candidate"] = "symmetric-query-and-candidate"
    provenance: Literal["new-pinned-run-not-historical-proof"] = (
        "new-pinned-run-not-historical-proof"
    )
    legacy_vectors_reusable: Literal[False] = False
    official_metadata_file: RelPath
    official_metadata: SourceCheck

    @model_validator(mode="after")
    def check_pin(self) -> Self:
        if self.model_options.get("revision") != self.revision:
            raise ValueError("candidate loading options must name its exact new revision")
        if self.slug == self.legacy_slug:
            raise ValueError("new pinned candidate must have a distinct legacy-control slug")
        return self


class CandidateVectorUnit(VectorExtensionSnapshot):
    __schema_stem__ = "story-candidate-vector-unit"
    __changelog__: ClassVar[tuple[ChangelogEntry]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Bind independently encoded vector units to an immutable new candidate.",
            why="A new pinned control must not extend an unknown historical control.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    candidate_revision: Sha256
    encoded_at: Timestamp


class CandidateVectorState(Contract):
    __schema_stem__ = "story-candidate-vector-state"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Retain validated candidate-only vector unit lineage and coverage.",
            why="Missing candidate rows remain missing, rather than borrowing unknown legacy rows.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    candidate_revision: Sha256
    previous_revision: Sha256 | None
    units: list[CandidateVectorUnit]
