"""Which saved vector rows have validated order, text, model settings and file hashes?"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pydantic import TypeAdapter

from idhazh.contracts.encoder_reading import EncoderReading, ReadingState
from idhazh.contracts.story_candidate_evaluation import CandidateEvaluationSnapshot
from idhazh.contracts.story_candidates import (
    NeighborEvidence,
    VectorCache,
    VectorExtension,
    VectorManifest,
)
from idhazh.contracts.story_encoder_candidate import CandidateVectorState
from idhazh.contracts.story_source import ArticleEvidence, SourceFreeze
from idhazh.contracts.story_vector_derivation import DerivedVectorSnapshot
from idhazh.contracts.story_vectors import VectorExtensionSnapshot, VectorSnapshot
from idhazh.story_dataset.source import article_id
from idhazh.story_dataset.storage import Store, digest, file_hash
from idhazh.story_dataset.vector_files import snapshot_file, snapshot_vectors, vector_path
from utilities.score_encoder_separation import read_pairs


def register_vectors(
    store: Store,
    manifest: SourceFreeze,
    articles: dict[str, ArticleEvidence],
    input_path: Path,
    readings_path: Path,
    vector_files: dict[str, Path],
    encoder_config_path: Path,
) -> VectorManifest:
    if store.setting("vectors") is not None:
        raise ValueError("saved vectors are already registered; use relocate-vectors")
    encoded = read_pairs(input_path)
    input_hash = file_hash(input_path)
    if input_hash != manifest.regression_hashes["corpus/encoder-comparison-1/pairs.json"]:
        raise ValueError("encoder input differs from the frozen regression input")
    urls = TypeAdapter(list[str]).validate_python(encoded["urls"])
    texts = TypeAdapter(list[str]).validate_python(encoded["texts"])
    if len(urls) != len(texts) or len(set(urls)) != len(urls):
        raise ValueError("vector URL/text order is not unique and aligned")
    ids = [article_id(url) for url in urls]
    if not set(ids) <= articles.keys():
        raise ValueError("saved vector input names a foreign archive URL")
    conflicts = [
        i for i, text in zip(ids, texts, strict=True) if articles[i].source.summary != text
    ]
    readings = TypeAdapter(list[EncoderReading]).validate_python(
        json.loads(readings_path.read_bytes())["encoders"]
    )
    encoder_config = json.loads(encoder_config_path.read_bytes())
    max_sequence_length = TypeAdapter(int).validate_python(
        encoder_config["encode"]["max_sequence_length"],
        strict=True,
    )
    by_slug = {reading.slug: reading for reading in readings}
    caches = []
    for slug, path in vector_files.items():
        reading = by_slug[slug]
        if (
            reading.state != ReadingState.MEASURED
            or reading.pair_set_sha256 != input_hash
            or reading.articles_done != len(ids)
            or reading.numbers_an_article is None
        ):
            raise ValueError("saved reading lacks the exact measured input")
        saved = np.load(path, mmap_mode="r", allow_pickle=False)
        if saved.shape != (len(ids), reading.numbers_an_article) or saved.dtype.kind != "f":
            raise ValueError("saved vector shape/dtype mismatch")
        for start in range(0, len(ids), 256):
            block = saved[start : start + 256]
            if not np.isfinite(block).all() or np.any(np.linalg.norm(block, axis=1) == 0):
                raise ValueError("saved vectors contain nonfinite or zero rows")
        caches.append(
            VectorCache(
                slug=slug,
                file=str(path.resolve()),
                file_sha256=file_hash(path),
                rows=len(ids),
                dimensions=reading.numbers_an_article,
                reading_sha256=digest(reading),
                input_sha256=input_hash,
                model_id=reading.model_id,
                revision=str(reading.model_options["revision"])
                if "revision" in reading.model_options
                else None,
                settings_sha256=digest(
                    {
                        "prefix": reading.prefix,
                        "model_options": reading.model_options,
                        "encode_options": reading.encode_options,
                    }
                ),
            )
        )
    vectors = VectorManifest(
        source_sha256=manifest.source_sha256,
        input_sha256=input_hash,
        input_file=str(input_path.resolve()),
        readings_file=str(readings_path.resolve()),
        readings_sha256=file_hash(readings_path),
        article_ids=ids,
        encoder_config_file=str(encoder_config_path.resolve()),
        encoder_config_sha256=file_hash(encoder_config_path),
        max_sequence_length=max_sequence_length,
        text_sha256=[hashlib.sha256(text.encode()).hexdigest() for text in texts],
        missing_article_ids=sorted(articles.keys() - set(ids)),
        text_conflict_article_ids=conflicts,
        caches=caches,
    )
    portable = snapshot_vectors(store.root, vectors)
    with store.transaction():
        if store.setting("vectors") is not None:
            raise ValueError("saved vectors were registered during validation")
        store.save("vectors", digest(portable), portable)
        store.set_setting("vectors", digest(portable))
    return portable


def validate_vectors(vectors: VectorManifest, root: Path | None = None) -> None:
    if isinstance(vectors, CandidateEvaluationSnapshot):
        candidate = vectors.candidate
        state = CandidateVectorState.model_validate_json(
            vector_path(vectors, vectors.input_file, root).read_bytes()
        )
        ids = [i for unit in state.units for i in unit.article_ids]
        if (
            len(vectors.caches) != 1 or vectors.extensions
            or vectors.source_sha256 != candidate.source_sha256
            or vectors.ordered_ids_sha256 != digest(vectors.article_ids)
            or vectors.input_sha256 != vectors.candidate_state_sha256
            or vectors.readings_sha256 != digest(candidate)
            or vectors.encoder_config_sha256 != digest(candidate)
            or len(vectors.unit_sha256) != len(vectors.native_files_sha256)
            or vectors.max_sequence_length != candidate.max_sequence_length
            or vectors.text_conflict_article_ids
            or not state.units or state.candidate_revision != digest(candidate)
            or digest(state) != vectors.candidate_state_sha256
            or vectors.unit_sha256 != [digest(unit) for unit in state.units]
            or vectors.native_files_sha256 != [unit.cache.file_sha256 for unit in state.units]
            or ids != vectors.article_ids or len(ids) != len(set(ids))
            or vectors.text_sha256 != [h for unit in state.units for h in unit.summary_sha256]
        ):
            raise ValueError("candidate evaluation source, order or lineage differs")
        cache = vectors.caches[0]
        if (
            cache.slug != candidate.slug or cache.model_id != candidate.model_id
            or cache.revision != candidate.revision or cache.dimensions != candidate.dimensions
            or cache.rows != len(vectors.article_ids) or cache.reading_sha256 != digest(candidate)
            or cache.input_sha256 != vectors.candidate_state_sha256
            or cache.settings_sha256 != digest({
                "prefix": candidate.prefix, "model_options": candidate.model_options,
                "encode_options": candidate.encode_options,
            })
        ):
            raise ValueError("candidate evaluation dimensions, settings or pin differ")
        matrix = np.load(vector_path(vectors, cache.file, root), mmap_mode="r", allow_pickle=False)
        if (
            matrix.shape != (cache.rows, candidate.dimensions)
            or matrix.dtype != np.dtype("float32") or not np.isfinite(matrix).all()
            or np.any(np.linalg.norm(matrix, axis=1) == 0)
        ):
            raise ValueError("candidate evaluation float32 shape or numeric values differ")
        metadata = vector_path(vectors, candidate.official_metadata_file, root)
        if file_hash(metadata) != candidate.official_metadata.evidence_sha256:
            raise ValueError("candidate evaluation official metadata bytes changed")
        offset = 0
        for unit in state.units:
            native = unit.cache
            if (
                unit.candidate_revision != digest(candidate)
                or unit.source_sha256 != candidate.source_sha256
                or unit.slug != candidate.slug
                or native.slug != candidate.slug
                or native.model_id != candidate.model_id
                or native.revision != candidate.revision
                or native.dimensions != candidate.dimensions
                or native.reading_sha256 != digest(candidate)
                or native.settings_sha256 != cache.settings_sha256
                or native.rows != len(unit.article_ids)
                or len(unit.summary_sha256) != native.rows
                or len(unit.article_input_sha256) != native.rows
            ):
                raise ValueError("candidate evaluation native unit lineage differs")
            path = vector_path(vectors, native.file, root)
            saved = np.load(path, mmap_mode="r", allow_pickle=False)
            if (
                file_hash(path) != native.file_sha256
                or saved.dtype != np.dtype("float32")
                or saved.shape != (native.rows, candidate.dimensions)
                or not np.array_equal(matrix[offset : offset + native.rows], saved)
            ):
                raise ValueError("candidate evaluation differs from retained native bytes")
            offset += native.rows
    if isinstance(vectors, DerivedVectorSnapshot):
        derivation = vectors.derivation
        if (
            len(vectors.caches) != 1 or vectors.extensions
            or derivation.source_sha256 != vectors.source_sha256
            or derivation.ordered_ids_sha256 != digest(vectors.article_ids)
            or vectors.native_ordered_ids_sha256 != derivation.ordered_ids_sha256
        ):
            raise ValueError("derived snapshot source, order or lineage differs")
        cache = vectors.caches[0]
        if (
            cache.slug != derivation.slug or cache.dimensions != derivation.dimensions
            or cache.rows != len(vectors.article_ids)
            or cache.reading_sha256 != digest(derivation)
            or cache.settings_sha256 != digest(derivation)
            or cache.file_sha256 != derivation.derived_file_sha256
        ):
            raise ValueError("derived snapshot dimensions, settings or hash differ")
        matrix = np.load(vector_path(vectors, cache.file, root), mmap_mode="r", allow_pickle=False)
        if (
            matrix.shape != (cache.rows, derivation.dimensions)
            or matrix.dtype != np.dtype("float32")
            or not np.isfinite(matrix).all()
            or np.any(np.linalg.norm(matrix, axis=1) == 0)
        ):
            raise ValueError("derived snapshot float32 shape or numeric values differ")
    if (
        file_hash(vector_path(vectors, vectors.input_file, root)) != vectors.input_sha256
        or file_hash(vector_path(vectors, vectors.readings_file, root)) != vectors.readings_sha256
        or file_hash(vector_path(vectors, vectors.encoder_config_file, root))
        != vectors.encoder_config_sha256
    ):
        raise ValueError("vector evidence input/readings changed")
    for cache in vectors.caches:
        if file_hash(vector_path(vectors, cache.file, root)) != cache.file_sha256:
            raise ValueError(f"{cache.slug}: saved vector bytes changed")
    for extension in vectors.extensions:
        path = vector_path(vectors, extension.cache.file, root)
        if file_hash(path) != extension.cache.file_sha256:
            raise ValueError("selected vector extension bytes changed")


def covered_ids(vectors: VectorManifest, slug: str | None = None) -> set[str]:
    base = set(vectors.article_ids) - set(vectors.text_conflict_article_ids)
    if slug:
        return base | {
            identity
            for extension in vectors.extensions
            if extension.slug == slug
            for identity in extension.article_ids
        }
    by_model = [covered_ids(vectors, cache.slug) for cache in vectors.caches]
    return set.intersection(*by_model) if by_model else set()


def model_matrix(
    vectors: VectorManifest, slug: str, root: Path | None = None
) -> tuple[list[str], NDArray[np.float64]]:
    cache = next((cache for cache in vectors.caches if cache.slug == slug), None)
    if cache is None:
        raise ValueError("unknown saved encoder")
    saved = np.load(vector_path(vectors, cache.file, root), mmap_mode="r", allow_pickle=False)
    ids = list(vectors.article_ids)
    matrix: NDArray[np.float64] = np.array(saved, dtype=np.float64)
    matrices = [matrix]
    for extension in vectors.extensions:
        if extension.slug == slug:
            if set(ids) & set(extension.article_ids):
                # Replace changed-text base rows; never silently retain stale inputs.
                for offset, identity in enumerate(extension.article_ids):
                    if identity in ids:
                        if identity not in vectors.text_conflict_article_ids:
                            raise ValueError("extension duplicates an already-valid saved row")
                        matrix[ids.index(identity)] = np.load(
                            vector_path(vectors, extension.cache.file, root),
                            mmap_mode="r",
                            allow_pickle=False,
                        )[offset]
            added = [i for i, identity in enumerate(extension.article_ids) if identity not in ids]
            if added:
                extension_rows = np.load(
                    vector_path(vectors, extension.cache.file, root), allow_pickle=False
                )[added]
                matrices.append(np.asarray(extension_rows, dtype=np.float64))
                ids.extend(extension.article_ids[i] for i in added)
    return ids, np.concatenate(matrices, axis=0) if len(matrices) > 1 else matrix


def register_extension(
    store: Store,
    vectors: VectorManifest,
    articles: dict[str, ArticleEvidence],
    extension: VectorExtension,
) -> VectorSnapshot:
    if not isinstance(vectors, VectorSnapshot):
        raise ValueError("use relocate-vectors before importing selected vector extensions")
    validate_vectors(vectors, store.root)
    if extension.source_sha256 != vectors.source_sha256:
        raise ValueError("extension belongs to another frozen source")
    cache = next((c for c in vectors.caches if c.slug == extension.slug), None)
    if cache is None or (
        cache.settings_sha256 != extension.cache.settings_sha256
        or cache.reading_sha256 != extension.cache.reading_sha256
        or cache.revision != extension.cache.revision
        or cache.model_id != extension.cache.model_id
        or cache.slug != extension.cache.slug
        or cache.dimensions != extension.cache.dimensions
    ):
        raise ValueError("extension settings/revision do not match the pinned saved candidate")
    if not extension.article_ids or len(set(extension.article_ids)) != len(extension.article_ids):
        raise ValueError("extension article IDs must be nonempty and unique")
    if not (
        len(extension.article_ids)
        == len(extension.article_input_sha256)
        == len(extension.summary_sha256)
        == extension.cache.rows
    ):
        raise ValueError("extension evidence/order length differs")
    for identity, input_hash, summary_hash in zip(
        extension.article_ids,
        extension.article_input_sha256,
        extension.summary_sha256,
        strict=True,
    ):
        if identity not in articles or articles[identity].input_sha256 != input_hash:
            raise ValueError("extension input hash/ID differs")
        if hashlib.sha256(articles[identity].source.summary.encode()).hexdigest() != summary_hash:
            raise ValueError("extension summary text differs")
    path = vector_path(extension, extension.cache.file, store.root)
    if file_hash(path) != extension.cache.file_sha256:
        raise ValueError("extension vector bytes differ")
    array = np.load(path, mmap_mode="r", allow_pickle=False)
    if (
        array.shape != (extension.cache.rows, cache.dimensions)
        or array.dtype.kind != "f"
        or not np.isfinite(array).all()
        or np.any(np.linalg.norm(array, axis=1) == 0)
    ):
        raise ValueError("extension numeric contract differs")
    portable_file = snapshot_file(store.root, path, extension.cache.file_sha256, ".npy")
    data = extension.model_dump(mode="json")
    if isinstance(extension, VectorExtensionSnapshot):
        data.pop("version")
        data.pop("path_base")
    data["cache"]["file"] = portable_file
    extension = VectorExtension.model_validate(data)
    if extension in vectors.extensions:
        return vectors
    if set(extension.article_ids) & (
        set(vectors.article_ids) - set(vectors.text_conflict_article_ids)
    ):
        raise ValueError("extension duplicates an already-valid saved row")
    if set(extension.article_ids) & {
        i for e in vectors.extensions if e.slug == extension.slug for i in e.article_ids
    }:
        raise ValueError("extension duplicates previous selected rows")
    updated = vectors.model_copy(update={"extensions": [*vectors.extensions, extension]})
    updated.previous_revision = digest(vectors)
    with store.transaction():
        if store.setting("vectors") not in (None, digest(vectors)):
            raise ValueError("vector registration changed during extension validation")
        store.save("vectors", digest(updated), updated)
        store.set_setting("vectors", digest(updated))
    return updated


def ranked_neighbors(
    vectors: VectorManifest,
    queries: list[str],
    k: int,
    block_size: int,
    root: Path | None = None,
) -> dict[tuple[str, str], list[NeighborEvidence]]:
    """Union per-model ranks; never average scores on different cosine scales."""
    validate_vectors(vectors, root)
    union: dict[tuple[str, str], list[NeighborEvidence]] = {}
    for cache in vectors.caches:
        model_ids, normalized = model_matrix(vectors, cache.slug, root)
        provenance = dict.fromkeys(vectors.article_ids, cache.file_sha256)
        for extension in vectors.extensions:
            if extension.slug == cache.slug:
                provenance.update(
                    dict.fromkeys(extension.article_ids, extension.cache.file_sha256)
                )
        usable = covered_ids(vectors, cache.slug)
        valid = {identity: i for i, identity in enumerate(model_ids) if identity in usable}
        query_ids = [identity for identity in queries if identity in valid]
        # At most ~66 MB for 10,675 x 768 float64; one model at a time.
        normalized /= np.linalg.norm(normalized, axis=1, keepdims=True)
        conflict_rows = [i for i, identity in enumerate(model_ids) if identity not in usable]
        for start in range(0, len(query_ids), block_size):
            chunk = query_ids[start : start + block_size]
            rows = [valid[identity] for identity in chunk]
            scores = normalized[rows] @ normalized.T
            if conflict_rows:
                scores[:, conflict_rows] = -np.inf
            for j, (identity, row) in enumerate(zip(chunk, rows, strict=True)):
                scores[j, row] = -np.inf
                # Stable index tie-break avoids machine-dependent argpartition ties.
                top = np.argsort(-scores[j], kind="stable")[: min(k, len(valid) - 1)]
                for rank, neighbor_row in enumerate(top, 1):
                    other = model_ids[int(neighbor_row)]
                    left, right = sorted((identity, other))
                    key = (left, right)
                    union.setdefault(key, []).append(
                        NeighborEvidence(
                            model=cache.slug,
                            query=identity,
                            rank=rank,
                            cosine=float(scores[j, int(neighbor_row)]),
                            vector_sha256=(
                                provenance[identity]
                                if provenance[identity] == provenance[other]
                                else digest(
                                    {"query": provenance[identity], "neighbor": provenance[other]}
                                )
                            ),
                            query_vector_sha256=provenance[identity]
                            if vectors.extensions else None,
                            neighbor_vector_sha256=provenance[other]
                            if vectors.extensions else None,
                        )
                    )
        del normalized
    return union
