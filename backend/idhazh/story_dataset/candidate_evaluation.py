"""How can saved pinned units be evaluated without inference or historical vector mixing?"""

import io
import os
from pathlib import Path
from uuid import uuid4

import numpy as np

from idhazh.contracts.story_candidate_evaluation import CandidateEvaluationSnapshot
from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_encoder_candidate import CandidateVectorState, PinnedEncoderCandidate
from idhazh.contracts.story_source import ArticleEvidence
from idhazh.story_dataset.encoder_candidates import validate_candidate_unit
from idhazh.story_dataset.storage import canonical, digest, file_hash
from idhazh.story_dataset.vector_files import relative_vector_path, snapshot_file


def publish_object(root: Path, raw: bytes, suffix: str) -> str:
    import hashlib

    identity = hashlib.sha256(raw).hexdigest()
    name = f"vector-evidence/{identity}{suffix}"
    target = relative_vector_path(name, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + "." + uuid4().hex + ".part")
    try:
        with part.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(part, target)
        except FileExistsError:
            if target.read_bytes() != raw:
                raise ValueError("immutable candidate evaluation evidence changed") from None
    finally:
        part.unlink(missing_ok=True)
    return name


def materialize_candidate(
    candidate: PinnedEncoderCandidate,
    state: CandidateVectorState,
    articles: dict[str, ArticleEvidence],
    root: Path,
    output_root: Path,
) -> CandidateEvaluationSnapshot:
    if root.resolve() == output_root.resolve():
        raise ValueError("materialize into a separate integration-owned evaluation root")
    if (
        state.candidate_revision != digest(candidate)
        or not state.units
        or (root / "candidate-vector-states" / (digest(state) + ".json")).read_bytes()
        != canonical(state)
    ):
        raise ValueError("candidate state lacks its immutable registered lineage")
    identities: list[str] = []
    summaries: list[str] = []
    matrices = []
    for unit in state.units:
        validate_candidate_unit(root, candidate, articles, unit)
        if set(identities) & set(unit.article_ids):
            raise ValueError("candidate state duplicates an article across units")
        identities.extend(unit.article_ids)
        summaries.extend(unit.summary_sha256)
        matrices.append(
            np.load(relative_vector_path(unit.cache.file, root), allow_pickle=False)
        )
    for unit in state.units:
        name = snapshot_file(
            output_root, relative_vector_path(unit.cache.file, root),
            unit.cache.file_sha256, ".npy",
        )
        if name != unit.cache.file:
            raise ValueError("candidate state must use content-addressed native evidence")
    buffer = io.BytesIO()
    np.save(buffer, np.concatenate(matrices), allow_pickle=False)
    array_file = publish_object(output_root, buffer.getvalue(), ".npy")
    state_file = publish_object(output_root, canonical(state), ".json")
    candidate_file = publish_object(output_root, canonical(candidate), ".json")
    snapshot_file(
        output_root, relative_vector_path(candidate.official_metadata_file, root),
        str(candidate.official_metadata.evidence_sha256), ".json",
    )
    settings = digest(
        {
            "prefix": candidate.prefix,
            "model_options": candidate.model_options,
            "encode_options": candidate.encode_options,
        }
    )
    return CandidateEvaluationSnapshot(
        path_base="dataset-root",
        source_sha256=candidate.source_sha256,
        input_sha256=digest(state),
        input_file=state_file,
        readings_file=candidate_file,
        readings_sha256=digest(candidate),
        encoder_config_file=candidate_file,
        encoder_config_sha256=digest(candidate),
        max_sequence_length=candidate.max_sequence_length,
        article_ids=identities,
        text_sha256=summaries,
        missing_article_ids=sorted(articles.keys() - set(identities)),
        caches=[
            VectorCache(
                slug=candidate.slug,
                file=array_file,
                file_sha256=file_hash(output_root / array_file),
                rows=len(identities),
                dimensions=candidate.dimensions,
                reading_sha256=digest(candidate),
                input_sha256=digest(state),
                model_id=candidate.model_id,
                revision=candidate.revision,
                settings_sha256=settings,
            )
        ],
        candidate=candidate,
        candidate_state_sha256=digest(state),
        unit_sha256=[digest(unit) for unit in state.units],
        native_files_sha256=[unit.cache.file_sha256 for unit in state.units],
        ordered_ids_sha256=digest(identities),
    )
