"""How are new pinned control candidates and their own vectors registered without legacy mixing?"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import numpy as np
from pydantic import TypeAdapter

from idhazh.contracts.encoder_reading import EncoderReading
from idhazh.contracts.story_encoder_candidate import (
    CandidateVectorState,
    CandidateVectorUnit,
    PinnedEncoderCandidate,
    Revision,
)
from idhazh.contracts.story_source import ArticleEvidence, SourceCheck
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.storage import canonical, digest, file_hash, now
from idhazh.story_dataset.vector_files import relative_vector_path, snapshot_file, vector_path


def save_immutable(
    root: Path, directory: str, value: PinnedEncoderCandidate | CandidateVectorState
) -> Path:
    path = root / directory / (digest(value) + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value)
    part = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with part.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(part, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("immutable candidate artifact changed") from None
    finally:
        part.unlink(missing_ok=True)
    return path


def register_pinned_candidate(
    vectors: VectorSnapshot,
    legacy_root: Path,
    slug: str,
    revision: str,
    metadata_file: Path,
    source_check: SourceCheck,
    output_root: Path,
) -> PinnedEncoderCandidate:
    TypeAdapter(Revision).validate_python(revision)
    if vectors.max_sequence_length != 256:
        raise ValueError("new candidate must preserve the saved 256-token input contract")
    if (
        source_check.state != "read"
        or source_check.checked_at is None
        or source_check.evidence_sha256 != file_hash(metadata_file)
    ):
        raise ValueError("new pin requires a byte-checked dated official metadata capture")
    if (
        file_hash(vector_path(vectors, vectors.readings_file, legacy_root))
        != vectors.readings_sha256
    ):
        raise ValueError("legacy encoder reading bytes changed")
    readings = TypeAdapter(list[EncoderReading]).validate_python(
        json.loads(vector_path(vectors, vectors.readings_file, legacy_root).read_bytes())[
            "encoders"
        ]
    )
    reading = next((r for r in readings if r.slug == slug), None)
    cache = next((c for c in vectors.caches if c.slug == slug), None)
    if (
        reading is None
        or cache is None
        or (
            cache.reading_sha256 != digest(reading)
            or cache.model_id != reading.model_id
            or cache.revision != reading.model_options.get("revision")
            or cache.dimensions != reading.numbers_an_article
            or cache.settings_sha256
            != digest(
                {
                    "prefix": reading.prefix,
                    "model_options": reading.model_options,
                    "encode_options": reading.encode_options,
                }
            )
        )
    ):
        raise ValueError("legacy reading does not match the registered control")
    metadata = json.loads(metadata_file.read_bytes())
    official_url = f"https://huggingface.co/api/models/{reading.model_id}/revision/{revision}"
    expected_url = urlsplit(official_url)
    actual_url = urlsplit(str(source_check.url))
    final_url = urlsplit(str(source_check.final_url or source_check.url))
    if (
        (actual_url.scheme, actual_url.netloc, actual_url.path)
        != (expected_url.scheme, expected_url.netloc, expected_url.path)
        or (final_url.scheme, final_url.netloc, final_url.path)
        != (expected_url.scheme, expected_url.netloc, expected_url.path)
        or metadata.get("sha") != revision
        or metadata.get("id", metadata.get("modelId")) != reading.model_id
    ):
        raise ValueError("metadata does not prove the named official model revision")
    candidate = PinnedEncoderCandidate(
        registered_at=now(),
        source_sha256=vectors.source_sha256,
        legacy_vector_revision=digest(vectors),
        legacy_slug=slug,
        legacy_reading_sha256=digest(reading),
        legacy_model_revision=cache.revision,
        slug=f"{slug}-pinned-{revision[:12]}",
        model_id=reading.model_id,
        revision=revision,
        prefix=reading.prefix,
        model_options={**reading.model_options, "revision": revision},
        encode_options=reading.encode_options,
        dimensions=cache.dimensions,
        max_sequence_length=256,
        official_metadata_file=snapshot_file(
            output_root, metadata_file, file_hash(metadata_file), ".json"
        ),
        official_metadata=source_check,
    )
    save_immutable(output_root, "encoder-candidates", candidate)
    return candidate


def validate_candidate(root: Path, candidate: PinnedEncoderCandidate) -> None:
    candidate_path = root / "encoder-candidates" / (digest(candidate) + ".json")
    if not candidate_path.is_file() or candidate_path.read_bytes() != canonical(candidate):
        raise ValueError("candidate is not registered as its immutable artifact")
    if (
        file_hash(relative_vector_path(candidate.official_metadata_file, root))
        != candidate.official_metadata.evidence_sha256
    ):
        raise ValueError("official candidate metadata bytes changed")


def validate_candidate_unit(
    root: Path,
    candidate: PinnedEncoderCandidate,
    articles: dict[str, ArticleEvidence],
    unit: CandidateVectorUnit,
) -> None:
    validate_candidate(root, candidate)
    cache = unit.cache
    if (
        unit.candidate_revision != digest(candidate)
        or unit.source_sha256 != candidate.source_sha256
        or unit.slug != candidate.slug
        or cache.slug != candidate.slug
        or cache.model_id != candidate.model_id
        or cache.revision != candidate.revision
        or cache.dimensions != candidate.dimensions
        or cache.reading_sha256 != digest(candidate)
        or cache.settings_sha256
        != digest(
            {
                "prefix": candidate.prefix,
                "model_options": candidate.model_options,
                "encode_options": candidate.encode_options,
            }
        )
    ):
        raise ValueError("unit does not belong to this immutable pinned candidate")
    ids = unit.article_ids
    if (
        not ids
        or len(set(ids)) != len(ids)
        or not set(ids) <= articles.keys()
        or len(ids) != cache.rows
        or unit.article_input_sha256 != [articles[i].input_sha256 for i in ids]
        or unit.summary_sha256
        != [hashlib.sha256(articles[i].source.summary.encode()).hexdigest() for i in ids]
        or cache.input_sha256
        != digest([candidate.prefix + articles[i].source.summary for i in ids])
    ):
        raise ValueError("unit input/order differs from the frozen article evidence")
    path = relative_vector_path(cache.file, root)
    matrix = np.load(path, mmap_mode="r", allow_pickle=False)
    if (
        file_hash(path) != cache.file_sha256
        or matrix.shape != (len(ids), candidate.dimensions)
        or matrix.dtype != np.dtype("float32")
        or not np.isfinite(matrix).all()
        or np.any(np.linalg.norm(matrix, axis=1) == 0)
    ):
        raise ValueError("unit bytes, float32 shape or numeric values differ")


def register_candidate_unit(
    root: Path,
    candidate: PinnedEncoderCandidate,
    articles: dict[str, ArticleEvidence],
    unit: CandidateVectorUnit,
    previous: CandidateVectorState | None = None,
) -> CandidateVectorState:
    validate_candidate_unit(root, candidate, articles, unit)
    unit = unit.model_copy(
        update={
            "cache": unit.cache.model_copy(
                update={
                    "file": snapshot_file(
                        root,
                        relative_vector_path(unit.cache.file, root),
                        unit.cache.file_sha256,
                        ".npy",
                    ),
                }
            )
        }
    )
    units = list(previous.units) if previous else []
    if previous and previous.candidate_revision != digest(candidate):
        raise ValueError("previous state belongs to another candidate")
    if previous:
        previous_path = root / "candidate-vector-states" / (digest(previous) + ".json")
        if not previous_path.is_file() or previous_path.read_bytes() != canonical(previous):
            raise ValueError("previous candidate state is not its immutable registration")
        for retained in previous.units:
            validate_candidate_unit(root, candidate, articles, retained)
    if any(digest(existing) == digest(unit) for existing in units):
        return (
            previous
            if previous is not None
            else CandidateVectorState(
                candidate_revision=digest(candidate), previous_revision=None, units=units
            )
        )
    if set(unit.article_ids) & {i for existing in units for i in existing.article_ids}:
        raise ValueError("candidate unit duplicates already registered candidate rows")
    state = CandidateVectorState(
        candidate_revision=digest(candidate),
        previous_revision=digest(previous) if previous else None,
        units=[*units, unit],
    )
    save_immutable(root, "candidate-vector-states", state)
    return state
