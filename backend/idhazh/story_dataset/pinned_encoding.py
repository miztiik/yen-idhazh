"""Can one bounded unit be encoded for a new immutable candidate without borrowing old rows?"""

from __future__ import annotations

import hashlib
import os
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from packaging.version import Version

from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_encoder_candidate import CandidateVectorUnit, PinnedEncoderCandidate
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_source import ArticleEvidence
from idhazh.story_dataset.encoder_candidates import (
    validate_candidate,
    validate_candidate_unit,
)
from idhazh.story_dataset.storage import digest, file_hash, now, read_model, write_model
from idhazh.story_dataset.vector_files import snapshot_file


def encode_pinned_selected(
    candidate: PinnedEncoderCandidate,
    articles: dict[str, ArticleEvidence],
    ids: list[str],
    policy: StoryPolicy,
    root: Path,
    output: Path,
) -> CandidateVectorUnit:
    validate_candidate(root, candidate)
    if (
        not ids
        or len(ids) > policy.batch_size
        or len(set(ids)) != len(ids)
        or not set(ids) <= articles.keys()
    ):
        raise ValueError("encoding requires one bounded unit of distinct frozen article IDs")
    descriptor = output.with_suffix(".json")
    if descriptor.exists():
        prior = read_model(descriptor, CandidateVectorUnit)
        if prior.article_ids != ids:
            raise ValueError("resumed candidate unit differs from the requested article order")
        validate_candidate_unit(root, candidate, articles, prior)
        return prior
    if output.exists():
        raise ValueError("output exists without its immutable candidate descriptor")
    runtime = {
        name: version(name)
        for name in ("sentence-transformers", "transformers", "torch", "torchvision", "Pillow")
    }
    if Version(runtime["sentence-transformers"]) < Version("6.1") or Version(
        runtime["transformers"]
    ) < Version("5.19"):
        raise ValueError(
            "new candidate encoding requires ST>=6.1 and Transformers>=5.19; no substitution"
        )
    import torch
    import torchvision  # type: ignore[import-not-found]
    from sentence_transformers import SentenceTransformer
    from transformers import AutoImageProcessor

    if (
        torch.version.cuda is not None
        or not runtime["torch"].endswith("+cpu")
        or not runtime["torchvision"].endswith("+cpu")
    ):
        raise ValueError(
            "new candidates require the isolated matching CPU torch/torchvision runtime"
        )
    # Import the processor and the actual torchvision operators before loading weights.
    runtime["image_processor"] = AutoImageProcessor.__name__
    torchvision.ops.nms(torch.tensor([[0.0, 0.0, 1.0, 1.0]]), torch.tensor([1.0]), 0.5)
    torch.set_num_threads(policy.encoding_threads)
    options: dict[str, Any] = {**candidate.model_options, "local_files_only": True}
    texts = [candidate.prefix + articles[i].source.summary for i in ids]
    encoder = SentenceTransformer(candidate.model_id, device="cpu", **options)
    encoder.max_seq_length = candidate.max_sequence_length
    encode_options: dict[str, Any] = dict(candidate.encode_options)
    matrix = np.asarray(
        encoder.encode(
            texts,
            batch_size=policy.encoding_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
            **encode_options,
        ),
        dtype=np.float32,
    )
    if (
        matrix.shape != (len(ids), candidate.dimensions)
        or not np.isfinite(matrix).all()
        or np.any(np.linalg.norm(matrix, axis=1) == 0)
    ):
        raise ValueError("candidate encoder returned invalid vector dimensions or values")
    output.parent.mkdir(parents=True, exist_ok=True)
    part = output.with_name(output.name + "." + uuid4().hex + ".part")
    try:
        with part.open("xb") as stream:
            np.save(stream, matrix, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(part, output)
    finally:
        part.unlink(missing_ok=True)
    unit = CandidateVectorUnit(
        path_base="dataset-root",
        candidate_revision=digest(candidate),
        encoded_at=now(),
        source_sha256=candidate.source_sha256,
        slug=candidate.slug,
        article_ids=ids,
        article_input_sha256=[articles[i].input_sha256 for i in ids],
        summary_sha256=[
            hashlib.sha256(articles[i].source.summary.encode()).hexdigest() for i in ids
        ],
        runtime_versions=runtime,
        cache=VectorCache(
            slug=candidate.slug,
            file=snapshot_file(root, output, file_hash(output), ".npy"),
            file_sha256=file_hash(output),
            rows=len(ids),
            dimensions=candidate.dimensions,
            reading_sha256=digest(candidate),
            input_sha256=digest(texts),
            model_id=candidate.model_id,
            revision=candidate.revision,
            settings_sha256=digest(
                {
                    "prefix": candidate.prefix,
                    "model_options": candidate.model_options,
                    "encode_options": candidate.encode_options,
                }
            ),
        ),
    )
    write_model(descriptor, unit)
    return unit
