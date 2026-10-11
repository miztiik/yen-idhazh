"""Can selected missing summaries be encoded locally with the exact pinned candidate settings?"""

from __future__ import annotations

import hashlib
import json
import os
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from packaging.version import Version
from pydantic import TypeAdapter

from idhazh.contracts.encoder_reading import EncoderReading
from idhazh.contracts.story_candidates import VectorCache, VectorExtension, VectorManifest
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_source import ArticleEvidence
from idhazh.contracts.story_vectors import VectorExtensionSnapshot, VectorSnapshot
from idhazh.story_dataset.storage import digest, file_hash, write_model
from idhazh.story_dataset.vector_files import snapshot_file, vector_path
from idhazh.story_dataset.vectors import validate_vectors


def encode_selected(
    articles: dict[str, ArticleEvidence],
    vectors: VectorManifest,
    ids: list[str],
    slug: str,
    policy: StoryPolicy,
    output: Path,
    root: Path | None = None,
) -> VectorExtension:
    """Load one CPU encoder, offline only; refuse substitutions and unpinned controls."""
    if not isinstance(vectors, VectorSnapshot):
        raise ValueError("use relocate-vectors before encoding selected extensions")
    validate_vectors(vectors, root)
    if root is None:
        raise ValueError("dataset root is required to save a vector extension snapshot")
    if not ids or len(set(ids)) != len(ids) or not set(ids) <= articles.keys():
        raise ValueError("extension must select known distinct archive IDs")
    if len(ids) > policy.batch_size:
        raise ValueError("extension is a bounded resumable unit, not a whole-archive re-encode")
    reading_raw = next(
        (
            r
            for r in json.loads(vector_path(vectors, vectors.readings_file, root).read_bytes())[
                "encoders"
            ]
            if r["slug"] == slug
        ),
        None,
    )
    if reading_raw is None:
        raise ValueError("unknown saved encoder reading")
    reading = EncoderReading.model_validate(reading_raw)
    revision = reading.model_options.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError(
            "saved control has no immutable revision; pin and approve it before encoding"
        )
    cache = next((cache for cache in vectors.caches if cache.slug == slug), None)
    settings_hash = digest(
        {
            "prefix": reading.prefix,
            "model_options": reading.model_options,
            "encode_options": reading.encode_options,
        }
    )
    if cache is None or (
        cache.reading_sha256 != digest(reading)
        or cache.settings_sha256 != settings_hash
        or cache.model_id != reading.model_id
        or cache.revision != revision
        or cache.dimensions != reading.numbers_an_article
    ):
        raise ValueError("selected encoder reading differs from the registered candidate")
    summaries = [articles[identity].source.summary for identity in ids]
    texts = [reading.prefix + text for text in summaries]
    article_hashes = [articles[i].input_sha256 for i in ids]
    summary_hashes = [hashlib.sha256(text.encode()).hexdigest() for text in summaries]
    descriptor = output.with_suffix(".json")
    if descriptor.exists():
        adapter: TypeAdapter[VectorExtensionSnapshot | VectorExtension] = TypeAdapter(
            VectorExtensionSnapshot | VectorExtension
        )
        prior = adapter.validate_json(descriptor.read_bytes())
        if (
            prior.article_ids != ids
            or prior.slug != slug
            or prior.source_sha256 != vectors.source_sha256
            or prior.article_input_sha256 != article_hashes
            or prior.summary_sha256 != summary_hashes
            or prior.cache.rows != len(ids)
            or prior.cache.slug != slug
            or prior.cache.model_id != cache.model_id
            or prior.cache.revision != revision
            or prior.cache.dimensions != cache.dimensions
            or prior.cache.reading_sha256 != cache.reading_sha256
            or prior.cache.settings_sha256 != settings_hash
            or prior.cache.input_sha256 != digest(texts)
            or file_hash(vector_path(prior, prior.cache.file, root)) != prior.cache.file_sha256
        ):
            raise ValueError("resumed vector extension differs from the requested unit")
        return prior
    if output.exists():
        raise ValueError("encoding output already exists without a descriptor; choose a fresh path")
    runtime = {name: version(name) for name in ("torch", "sentence-transformers", "transformers")}
    if slug == "embeddinggemma-two" and (
        Version(runtime["sentence-transformers"]) < Version("6.1")
        or Version(runtime["transformers"]) < Version("5.19")
    ):
        raise ValueError(
            "EmbeddingGemma-2 requires ST>=6.1, Transformers>=5.19 and compatible "
            "CPU Pillow/Torchvision; current runtime cannot load it. No replacement permitted."
        )
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(policy.encoding_threads)
    options: dict[str, Any] = dict(reading.model_options)
    encode_options: dict[str, Any] = dict(reading.encode_options)
    options["local_files_only"] = True
    encoder = SentenceTransformer(reading.model_id, device="cpu", **options)
    # The saved comparison truncates at 256 tokens; do not silently change its input contract.
    encoder.max_seq_length = vectors.max_sequence_length
    result = encoder.encode(
        texts,
        batch_size=policy.encoding_batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
        **encode_options,
    )
    if (
        result.shape != (len(ids), reading.numbers_an_article)
        or not np.isfinite(result).all()
        or np.any(np.linalg.norm(result, axis=1) == 0)
    ):
        raise ValueError("encoder returned the wrong shape, nonfinite values or zero rows")
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_name(output.name + "." + uuid4().hex + ".part")
    try:
        with part.open("xb") as stream:
            np.save(stream, result, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(part, output)
    finally:
        part.unlink(missing_ok=True)
    output_hash = file_hash(output)
    extension = VectorExtensionSnapshot(
        path_base="dataset-root",
        source_sha256=vectors.source_sha256,
        slug=slug,
        article_ids=ids,
        article_input_sha256=article_hashes,
        summary_sha256=summary_hashes,
        runtime_versions=runtime,
        cache=VectorCache(
            slug=slug,
            file=snapshot_file(root, output, output_hash, ".npy"),
            file_sha256=output_hash,
            rows=len(ids),
            dimensions=int(result.shape[1]),
            reading_sha256=digest(reading),
            input_sha256=digest(texts),
            model_id=reading.model_id,
            revision=revision,
            settings_sha256=settings_hash,
        ),
    )
    write_model(descriptor, extension)
    return extension
