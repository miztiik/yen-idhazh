"""Which vector evidence files move with the dataset without changing their identities?"""

from typing import Literal, Self

from pydantic import TypeAdapter, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, RelPath, SchemaVersion, Sha256
from idhazh.contracts.story_candidates import VectorExtension, VectorManifest


class VectorSnapshot(VectorManifest, Contract):
    __schema_stem__ = "story-vector-snapshot"
    __changelog__ = (
        ChangelogEntry(
            version="2026-10-09",
            change="Store immutable vector evidence at dataset-relative POSIX paths.",
            why="A moved dataset must retain the exact registered bytes and settings.",
        ),
    )

    version: SchemaVersion = __changelog__[0].version
    path_base: Literal["dataset-root"]
    previous_revision: Sha256 | None = None
    input_file: RelPath
    readings_file: RelPath
    encoder_config_file: RelPath

    @model_validator(mode="after")
    def check_paths(self) -> Self:
        for cache in [*self.caches, *(extension.cache for extension in self.extensions)]:
            TypeAdapter(RelPath).validate_python(cache.file)
        return self


class VectorExtensionSnapshot(VectorExtension, Contract):
    __schema_stem__ = "story-vector-extension-snapshot"
    __changelog__ = (
        ChangelogEntry(
            version="2026-10-09",
            change="Store selected vector extensions at dataset-relative POSIX paths.",
            why="Extension descriptors must survive the same moves as base vectors.",
        ),
    )

    version: SchemaVersion = __changelog__[0].version
    path_base: Literal["dataset-root"]

    @model_validator(mode="after")
    def check_path(self) -> Self:
        TypeAdapter(RelPath).validate_python(self.cache.file)
        return self
