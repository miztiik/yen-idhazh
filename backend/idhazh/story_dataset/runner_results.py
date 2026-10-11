"""Validate downloaded runner units before continuing the current typed vector registrations."""

import hashlib
from pathlib import Path

import numpy as np

from idhazh.contracts.story_encoder_candidate import CandidateVectorState, CandidateVectorUnit
from idhazh.contracts.story_runner import RunnerPackage, RunnerResult, RunnerShard
from idhazh.contracts.story_source import ArticleEvidence
from idhazh.contracts.story_vectors import VectorExtensionSnapshot, VectorSnapshot
from idhazh.story_dataset.encoder_candidates import register_candidate_unit
from idhazh.story_dataset.runner_inputs import describe_file, validate_shard
from idhazh.story_dataset.storage import Store, canonical, digest, file_hash, read_model
from idhazh.story_dataset.vector_files import relative_vector_path, snapshot_file
from idhazh.story_dataset.vectors import register_extension


def validate_result(
    result: RunnerResult, shard: RunnerShard, package: RunnerPackage, root: Path
) -> None:
    validate_result_content(result, shard, package, root)
    expected = {"result.json", *(f.path for f in result.files)}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != expected:
        raise ValueError("result directory contains unexpected files")


def validate_result_content(
    result: RunnerResult, shard: RunnerShard, package: RunnerPackage, root: Path
) -> None:
    validate_shard(shard)
    if (
        result.shard_sha256 != digest(shard)
        or result.package_sha256 != digest(package)
        or result.code_commit != package.code_commit
        or result.shard != shard.shard
        or any(result.runtime_versions.get(k) != v for k, v in package.runtime_versions.items())
        or (result.units and result.model_files != shard.model_files)
    ):
        raise ValueError("returned package, source, code, runtime or pinned model lineage differs")
    encoder = shard.encoder
    articles = {a.article_id: a for a in shard.articles}
    expected_units = [
        list(articles)[n : n + shard.unit_rows] for n in range(0, len(articles), shard.unit_rows)
    ]
    done: set[str] = set()
    expected_paths = []
    for unit in result.units:
        if unit.article_ids not in expected_units or done & set(unit.article_ids):
            raise ValueError("result duplicates, splits or invents an ordered input unit")
        done.update(unit.article_ids)
        cache = unit.cache
        if (
            unit.source_sha256 != shard.source.source_sha256
            or unit.slug != encoder.slug
            or (
                shard.candidate is not None
                and (
                    not isinstance(unit, CandidateVectorUnit)
                    or unit.candidate_revision != digest(shard.candidate)
                )
            )
            or (shard.candidate is None and isinstance(unit, CandidateVectorUnit))
            or cache.slug != encoder.slug
            or cache.model_id != encoder.model_id
            or cache.revision != encoder.model_options["revision"]
            or cache.dimensions != shard.dimensions
            or cache.rows != len(unit.article_ids)
            or cache.reading_sha256 != digest(encoder)
            or cache.settings_sha256
            != digest(
                {
                    "prefix": encoder.prefix,
                    "model_options": encoder.model_options,
                    "encode_options": encoder.encode_options,
                }
            )
            or cache.input_sha256
            != digest([encoder.prefix + articles[i].source.summary for i in unit.article_ids])
            or unit.article_input_sha256 != [articles[i].input_sha256 for i in unit.article_ids]
            or unit.summary_sha256
            != [
                hashlib.sha256(articles[i].source.summary.encode()).hexdigest()
                for i in unit.article_ids
            ]
            or unit.runtime_versions != result.runtime_versions
        ):
            raise ValueError("unit source/order/prefix/role/native dimensions/settings differ")
        path = relative_vector_path(cache.file, root)
        matrix = np.load(path, mmap_mode="r", allow_pickle=False)
        if (
            file_hash(path) != cache.file_sha256
            or matrix.shape != (cache.rows, shard.dimensions)
            or matrix.dtype != np.dtype("float32")
            or not np.isfinite(matrix).all()
            or np.any(np.linalg.norm(matrix, axis=1) == 0)
        ):
            raise ValueError("returned vector hash, float32 shape or finite nonzero values differ")
        descriptor = "units/" + digest(unit.article_ids) + ".json"
        if (root / descriptor).read_bytes() != canonical(unit):
            raise ValueError("returned typed descriptor differs from its manifest")
        expected_paths.extend([cache.file, descriptor])
    if result.pending_article_ids != [i for i in articles if i not in done]:
        raise ValueError("pending inputs are not the exact unfinished input order")
    if (result.state == "complete") != (not result.pending_article_ids and result.error is None):
        raise ValueError("result completion state is dishonest")
    expected_files = [describe_file(root / name, root) for name in expected_paths]
    if result.files != expected_files:
        raise ValueError("returned per-file manifest differs")


def recover_result(
    shard: RunnerShard, package: RunnerPackage, root: Path
) -> RunnerResult:
    """Reconstruct only complete typed unit pairs after a manifest-write interruption."""
    prior = read_model(root / "result.json", RunnerResult)
    validate_result_content(prior, shard, package, root)
    units: list[CandidateVectorUnit | VectorExtensionSnapshot] = []
    ids = [a.article_id for a in shard.articles]
    model = CandidateVectorUnit if shard.candidate else VectorExtensionSnapshot
    incomplete = []
    for start in range(0, len(ids), shard.unit_rows):
        selected = ids[start : start + shard.unit_rows]
        name = digest(selected)
        descriptor = root / "units" / (name + ".json")
        array = root / "vectors" / (name + ".npy")
        if descriptor.exists():
            unit = read_model(descriptor, model)
            if unit.article_ids != selected or not array.exists():
                raise ValueError("recovery descriptor order or complete vector pair differs")
            units.append(unit)
        elif array.exists():
            incomplete.append(array)
    done = {i for unit in units for i in unit.article_ids}
    pending = [i for i in ids if i not in done]
    result = prior.model_copy(update={
        "units": units,
        "files": [
            describe_file(root / name, root)
            for unit in units
            for name in (unit.cache.file, "units/" + digest(unit.article_ids) + ".json")
        ],
        "pending_article_ids": pending,
        "state": "failed" if prior.error else ("partial" if pending else "complete"),
        "resumed_from": digest(prior),
    })
    validate_result_content(result, shard, package, root)
    if not {digest(u) for u in prior.units} <= {digest(u) for u in units}:
        raise ValueError("recovery changes a previously completed unit")
    expected = {"result.json", *(f.path for f in result.files)}
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    incomplete_names = {p.relative_to(root).as_posix() for p in incomplete}
    parts = {name for name in actual - expected - incomplete_names if name.endswith(".part")}
    if actual - expected - incomplete_names - parts:
        raise ValueError("recovery directory contains unexpected files")
    # Retain incomplete files outside the artifact root; they never establish completion.
    for name in sorted(incomplete_names | parts):
        source = root / name
        destination = root.with_name(root.name + "-incomplete") / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError("incomplete recovery destination already exists")
        source.rename(destination)
    validate_result(result, shard, package, root)
    part = root / "result.json.part"
    part.write_bytes(canonical(result))
    part.replace(root / "result.json")
    return result


def import_result(
    result: RunnerResult,
    shard: RunnerShard,
    package: RunnerPackage,
    downloaded: Path,
    root: Path,
    articles: dict[str, ArticleEvidence],
    state_pointer: Path | None = None,
) -> CandidateVectorState | VectorSnapshot:
    validate_result(result, shard, package, downloaded)
    for evidence in shard.articles:
        if articles.get(evidence.article_id) != evidence:
            raise ValueError("downloaded source evidence differs from current immutable freeze")
    if shard.candidate:
        if state_pointer is None:
            raise ValueError("candidate import requires the current live state pointer")
        state = read_model(state_pointer, CandidateVectorState)
        for unit in result.units:
            assert isinstance(unit, CandidateVectorUnit)
            cache = unit.cache.model_copy(
                update={
                    "file": snapshot_file(
                        root, downloaded / unit.cache.file, unit.cache.file_sha256, ".npy"
                    )
                }
            )
            portable = unit.model_copy(update={"cache": cache})
            state = register_candidate_unit(root, shard.candidate, articles, portable, state)
            part = state_pointer.with_suffix(".part")
            part.write_bytes(canonical(state))
            part.replace(state_pointer)
        return state
    store = Store(root)
    try:
        identity = store.setting("vectors")
        if identity is None:
            raise ValueError("import requires an existing vector registration, not an empty index")
        vectors = store.get("vectors", identity, VectorSnapshot)
        for unit in result.units:
            assert isinstance(unit, VectorExtensionSnapshot)
            cache = unit.cache.model_copy(
                update={
                    "file": snapshot_file(
                        root, downloaded / unit.cache.file, unit.cache.file_sha256, ".npy"
                    )
                }
            )
            vectors = register_extension(
                store, vectors, articles, unit.model_copy(update={"cache": cache})
            )
        return vectors
    finally:
        store.close()
