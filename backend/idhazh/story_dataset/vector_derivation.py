"""How are separate Gemma prefix candidates created without changing native registrations?"""

import hashlib
import io
import json
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import TypeAdapter

from idhazh.contracts.encoder_reading import EncoderReading
from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_vector_derivation import DerivedVectorSnapshot, GemmaDimensionCandidate
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.storage import digest, file_hash, write_model
from idhazh.story_dataset.vector_files import snapshot_file, vector_path
from idhazh.story_dataset.vectors import covered_ids, model_matrix, validate_vectors


def normalize_prefix(matrix: NDArray[np.float64], dimensions: int) -> NDArray[np.float32]:
    if matrix.ndim != 2 or not 0 < dimensions <= matrix.shape[1] or not np.isfinite(matrix).all():
        raise ValueError("native matrix shape, dimensions or finite values differ")
    prefix = np.array(matrix[:, :dimensions], dtype=np.float64)
    norms = np.linalg.norm(prefix, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms == 0):
        raise ValueError("native leading dimensions contain zero or nonfinite norms")
    return np.asarray(prefix / norms, dtype=np.float32)


def derive_gemma(
    base: VectorSnapshot,
    root: Path,
    output_root: Path,
    slug: str,
    dimensions: Literal[128, 256, 512],
) -> DerivedVectorSnapshot:
    validate_vectors(base, root)
    cache = next((c for c in base.caches if c.slug == slug), None)
    readings = TypeAdapter(list[EncoderReading]).validate_python(
        json.loads(vector_path(base, base.readings_file, root).read_bytes())["encoders"]
    )
    reading = next((r for r in readings if r.slug == slug), None)
    if (
        cache is None
        or reading is None
        or cache.model_id != "google/embeddinggemma-2"
        or cache.dimensions != 768
        or reading.numbers_an_article != 768
        or cache.revision is None
        or reading.model_options.get("revision") != cache.revision
        or digest(reading) != cache.reading_sha256
        or cache.settings_sha256
        != digest(
            {
                "prefix": reading.prefix,
                "model_options": reading.model_options,
                "encode_options": reading.encode_options,
            }
        )
    ):
        raise ValueError("derivation requires the exact pinned native Gemma768 reading")
    native_caches = [cache, *(e.cache for e in base.extensions if e.slug == slug)]
    for native in native_caches:
        matrix = np.load(vector_path(base, native.file, root), mmap_mode="r", allow_pickle=False)
        if (
            native.dimensions != 768
            or native.model_id != cache.model_id
            or native.revision != cache.revision
            or native.settings_sha256 != cache.settings_sha256
            or native.reading_sha256 != cache.reading_sha256
            or matrix.shape != (native.rows, 768)
            or matrix.dtype != np.dtype("float32")
            or not np.isfinite(matrix).all()
            or np.any(np.linalg.norm(matrix, axis=1) == 0)
        ):
            raise ValueError("native vector shape, dtype, values or extension lineage differ")
    native_ids, matrix = model_matrix(base, slug, root)
    usable = covered_ids(base, slug)
    ids = [i for i in native_ids if i in usable]
    derived = normalize_prefix(
        matrix[[n for n, i in enumerate(native_ids) if i in usable]], dimensions
    )
    buffer = io.BytesIO()
    np.save(buffer, derived, allow_pickle=False)
    candidate = GemmaDimensionCandidate(
        slug=f"{slug}-derived-{dimensions}-{digest(base)[:12]}",
        source_sha256=base.source_sha256,
        base_vector_revision=digest(base),
        base_slug=slug,
        base_files_sha256=[c.file_sha256 for c in native_caches],
        base_settings_sha256=cache.settings_sha256,
        dimensions=dimensions,
        derived_file_sha256=hashlib.sha256(buffer.getvalue()).hexdigest(),
        ordered_ids_sha256=digest(ids),
    )
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / (digest(candidate) + ".npy")
    if path.exists():
        if file_hash(path) != candidate.derived_file_sha256:
            raise ValueError("immutable derived array differs")
    else:
        part = path.with_suffix(".part")
        with part.open("xb") as stream:
            np.save(stream, derived, allow_pickle=False)
        part.rename(path)
    text_hashes = dict(zip(base.article_ids, base.text_sha256, strict=True))
    for extension in base.extensions:
        if extension.slug == slug:
            text_hashes.update(zip(extension.article_ids, extension.summary_sha256, strict=True))
    result = DerivedVectorSnapshot(
        path_base="dataset-root",
        previous_revision=None,
        source_sha256=base.source_sha256,
        input_sha256=base.input_sha256,
        input_file=snapshot_file(
            output_root, vector_path(base, base.input_file, root), base.input_sha256, ".json"
        ),
        readings_file=snapshot_file(
            output_root, vector_path(base, base.readings_file, root), base.readings_sha256, ".json"
        ),
        readings_sha256=base.readings_sha256,
        encoder_config_file=snapshot_file(
            output_root,
            vector_path(base, base.encoder_config_file, root),
            base.encoder_config_sha256,
            ".json",
        ),
        encoder_config_sha256=base.encoder_config_sha256,
        max_sequence_length=base.max_sequence_length,
        article_ids=ids,
        text_sha256=[text_hashes[i] for i in ids],
        missing_article_ids=sorted(
            (set(base.missing_article_ids) | set(base.article_ids)) - set(ids)
        ),
        caches=[
            VectorCache(
                slug=candidate.slug,
                file=snapshot_file(output_root, path, file_hash(path), ".npy"),
                file_sha256=file_hash(path),
                rows=len(ids),
                dimensions=dimensions,
                reading_sha256=digest(candidate),
                input_sha256=digest([text_hashes[i] for i in ids]),
                model_id=cache.model_id,
                revision=cache.revision,
                settings_sha256=digest(candidate),
            )
        ],
        derivation=candidate,
        native_ordered_ids_sha256=digest(ids),
    )
    write_model(output_root / "derived-candidates" / (digest(candidate) + ".json"), candidate)
    write_model(output_root / "derived-vectors" / (digest(result) + ".json"), result)
    return result
