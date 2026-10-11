"""How are vector files resolved and copied without rewriting historical registrations?"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from idhazh.contracts.base import RelPath
from idhazh.contracts.story_candidates import VectorExtension, VectorManifest
from idhazh.contracts.story_vectors import VectorExtensionSnapshot, VectorSnapshot
from idhazh.story_dataset.storage import Store, digest, file_hash, write_model


def read_vectors(store: Store, revision: str) -> VectorManifest:
    # Read old shapes as themselves: their hashes and serialized bytes stay unchanged.
    adapter: TypeAdapter[VectorSnapshot | VectorManifest] = TypeAdapter(
        VectorSnapshot | VectorManifest
    )
    value = store.get("vectors", revision, adapter)
    if digest(value) != revision:
        raise ValueError("vector registration identity differs from its immutable payload")
    return value


def vector_path(evidence: VectorManifest | VectorExtension, name: str, root: Path | None) -> Path:
    if isinstance(evidence, (VectorSnapshot, VectorExtensionSnapshot)):
        return relative_vector_path(name, root)
    path = Path(name)
    if not path.is_absolute():
        raise ValueError("legacy vector paths must be absolute; use relocate-vectors")
    return path


def relative_vector_path(name: str, root: Path | None) -> Path:
    TypeAdapter(RelPath).validate_python(name)
    if root is None:
        raise ValueError("dataset root is required to resolve a vector snapshot")
    base = root.resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise ValueError("vector evidence path escapes the dataset root")
    return path


def snapshot_file(root: Path, source: Path, expected: str, suffix: str) -> str:
    """Copy exact bytes once; a corrupt existing object is refused, never replaced."""
    if file_hash(source) != expected:
        raise ValueError("relocated vector evidence bytes differ from the registered hash")
    name = f"vector-evidence/{expected}{suffix}"
    target = relative_vector_path(name, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if file_hash(target) != expected:
            raise ValueError("immutable vector evidence bytes changed")
        return name
    part = target.with_name(target.name + "." + uuid4().hex + ".part")
    try:
        with source.open("rb") as reader, part.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        if file_hash(part) != expected:
            raise ValueError("vector evidence changed while copying")
        try:
            os.link(part, target)
        except FileExistsError:
            if file_hash(target) != expected:
                raise ValueError("immutable vector evidence bytes changed") from None
    finally:
        part.unlink(missing_ok=True)
    return name


def snapshot_vectors(
    root: Path,
    vectors: VectorManifest,
    replacements: dict[str, Path] | None = None,
    previous_revision: str | None = None,
) -> VectorSnapshot:
    files = replacements or {}
    expected = {
        vectors.input_sha256,
        vectors.readings_sha256,
        vectors.encoder_config_sha256,
        *(cache.file_sha256 for cache in vectors.caches),
        *(extension.cache.file_sha256 for extension in vectors.extensions),
    }
    if not files.keys() <= expected:
        raise ValueError("relocation names an unregistered file hash")

    def location(name: str, sha256: str) -> Path:
        return files[sha256] if sha256 in files else vector_path(vectors, name, root)

    evidence = [
        (vectors.input_file, vectors.input_sha256, ".json"),
        (vectors.readings_file, vectors.readings_sha256, ".json"),
        (vectors.encoder_config_file, vectors.encoder_config_sha256, ".json"),
        *((cache.file, cache.file_sha256, ".npy") for cache in vectors.caches),
        *((e.cache.file, e.cache.file_sha256, ".npy") for e in vectors.extensions),
    ]
    for name, sha256, _suffix in evidence:
        if file_hash(location(name, sha256)) != sha256:
            raise ValueError("relocated vector evidence bytes differ from the registered hash")
    paths = {
        (sha256, suffix): snapshot_file(root, location(name, sha256), sha256, suffix)
        for name, sha256, suffix in evidence
    }
    data = vectors.model_dump(mode="json")
    data.update(
        path_base="dataset-root",
        previous_revision=previous_revision,
        input_file=paths[vectors.input_sha256, ".json"],
        readings_file=paths[vectors.readings_sha256, ".json"],
        encoder_config_file=paths[vectors.encoder_config_sha256, ".json"],
    )
    for cache in data["caches"]:
        cache["file"] = paths[cache["file_sha256"], ".npy"]
    for extension in data["extensions"]:
        extension["cache"]["file"] = paths[extension["cache"]["file_sha256"], ".npy"]
    return VectorSnapshot.model_validate(data)


def relocate_vectors(
    store: Store, expected_revision: str, replacements: dict[str, Path], output: Path
) -> VectorSnapshot:
    if store.setting("vectors") != expected_revision:
        raise ValueError("vector registration changed; use the current expected revision")
    previous = read_vectors(store, expected_revision)
    if store.setting("source") not in (None, previous.source_sha256):
        raise ValueError("vector registration belongs to another frozen source")
    updated = snapshot_vectors(store.root, previous, replacements, expected_revision)
    if isinstance(previous, VectorSnapshot):
        # Already-portable evidence needs no new revision when only its root moved.
        updated = updated.model_copy(update={"previous_revision": previous.previous_revision})
    with store.transaction():
        if store.setting("vectors") != expected_revision:
            raise ValueError("vector registration changed during relocation")
        write_model(output, updated)
        store.save("vectors", digest(updated), updated)
        store.set_setting("vectors", digest(updated))
    return updated
