"""Which separate Gemma candidate was derived from unchanged native vectors without inference?"""

from typing import ClassVar, Literal

from idhazh.contracts.base import ChangelogEntry, Contract, SchemaVersion, Sha256, Slug
from idhazh.contracts.story_vectors import VectorSnapshot


class GemmaDimensionCandidate(Contract):
    __schema_stem__ = "story-gemma-dimension-candidate"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Bind Gemma prefix dimensions to native vector lineage.",
            why="A smaller prefix is a separate candidate, not new model inference.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    slug: Slug
    source_sha256: Sha256
    base_vector_revision: Sha256
    base_slug: Slug
    base_files_sha256: list[Sha256]
    base_settings_sha256: Sha256
    derived_file_sha256: Sha256
    ordered_ids_sha256: Sha256
    native_dimensions: Literal[768] = 768
    dimensions: Literal[128, 256, 512]
    transform: Literal["leading-dimensions-then-l2-normalize"] = (
        "leading-dimensions-then-l2-normalize"
    )
    roles: Literal["symmetric-query-and-candidate"] = "symmetric-query-and-candidate"
    selection: Literal["development-before-confirmation"] = "development-before-confirmation"
    inference: Literal[False] = False


class DerivedVectorSnapshot(VectorSnapshot):
    __schema_stem__ = "story-derived-vector-snapshot"
    __changelog__: ClassVar[tuple[ChangelogEntry]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Retain separate derived vector and native lineage.",
            why="Native registrations stay unchanged and query dimensions agree.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    derivation: GemmaDimensionCandidate
    native_ordered_ids_sha256: Sha256
