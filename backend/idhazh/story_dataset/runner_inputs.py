"""How is an exact missing-only input package prepared and checked without any outbound action?"""

import json
import subprocess
import zipfile
from pathlib import Path

from pydantic import TypeAdapter

from idhazh.contracts.encoder_reading import EncoderReading
from idhazh.contracts.story_encoder_candidate import CandidateVectorState, PinnedEncoderCandidate
from idhazh.contracts.story_evaluation import StoryPolicy
from idhazh.contracts.story_runner import RunnerFile, RunnerPackage, RunnerRuntimeLock, RunnerShard
from idhazh.contracts.story_source import ArticleEvidence, SourceFreeze
from idhazh.contracts.story_vectors import VectorSnapshot
from idhazh.story_dataset.encoder_candidates import validate_candidate_unit
from idhazh.story_dataset.source import article_id
from idhazh.story_dataset.storage import digest, file_hash, now, read_model, write_model
from idhazh.story_dataset.vector_files import relative_vector_path, vector_path
from idhazh.story_dataset.vectors import covered_ids, validate_vectors


def describe_file(path: Path, root: Path) -> RunnerFile:
    return RunnerFile(
        path=path.relative_to(root).as_posix(), sha256=file_hash(path), bytes=path.stat().st_size
    )


def describe_committed_code(repository: Path, commit: str, name: str) -> RunnerFile:
    raw = subprocess.check_output(["git", "-C", str(repository), "show", f"{commit}:{name}"])
    path = relative_vector_path(name, repository)
    if path.read_bytes() != raw:
        raise ValueError(f"runner code differs from the exact committed LF bytes: {name}")
    return describe_file(path, repository)


def validate_shard(shard: RunnerShard) -> None:
    encoder = shard.encoder
    revision = encoder.model_options.get("revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("runner cannot encode an unknown historical control revision")
    try:
        int(revision, 16)
    except ValueError:
        raise ValueError("runner requires a hexadecimal immutable model revision") from None
    if shard.policy.batch_size != shard.unit_rows or shard.policy.batch_size > 20:
        raise ValueError("runner units must preserve the bounded source policy")
    for evidence in shard.articles:
        if evidence.article_id != article_id(
            evidence.source.url
        ) or evidence.input_sha256 != digest(evidence.source):
            raise ValueError("article identity or full source evidence hash differs")
    if (
        digest([a.article_id for a in shard.articles]) != shard.ordered_ids_sha256
        or digest([encoder.prefix + a.source.summary for a in shard.articles])
        != shard.prefixed_texts_sha256
    ):
        raise ValueError("shard article order or exact prefixed summaries differ")


def prepare_shards(
    source: SourceFreeze,
    articles: dict[str, ArticleEvidence],
    policy: StoryPolicy,
    vectors: VectorSnapshot,
    vector_root: Path,
    candidate: PinnedEncoderCandidate,
    state: CandidateVectorState,
    candidate_root: Path,
    output: Path,
    shard_rows: int = 400,
    model_files: dict[str, list[RunnerFile]] | None = None,
) -> list[RunnerShard]:
    if output.exists() or not 20 <= shard_rows <= 400 or shard_rows % policy.batch_size:
        raise ValueError("use a new package directory and whole-unit shards up to400 rows")
    if (
        source.source_sha256 != vectors.source_sha256
        or candidate.source_sha256 != source.source_sha256
    ):
        raise ValueError("runner parents belong to another exact source")
    if state.candidate_revision != digest(candidate):
        raise ValueError("candidate state differs from its pinned registration")
    for unit in state.units:
        validate_candidate_unit(candidate_root, candidate, articles, unit)
    validate_vectors(vectors, vector_root)
    readings = TypeAdapter(list[EncoderReading]).validate_python(
        json.loads(vector_path(vectors, vectors.readings_file, vector_root).read_bytes())[
            "encoders"
        ]
    )
    selections: list[tuple[PinnedEncoderCandidate | EncoderReading, str, set[str], int]] = [
        (
            candidate,
            digest(state),
            {i for u in state.units for i in u.article_ids},
            candidate.dimensions,
        )
    ]
    for slug in ("jina-v5-nano", "embeddinggemma-two"):
        reading = next(r for r in readings if r.slug == slug)
        cache = next(c for c in vectors.caches if c.slug == slug)
        if (
            digest(reading) != cache.reading_sha256
            or cache.model_id != reading.model_id
            or cache.revision != reading.model_options.get("revision")
            or cache.settings_sha256
            != digest(
                {
                    "prefix": reading.prefix,
                    "model_options": reading.model_options,
                    "encode_options": reading.encode_options,
                }
            )
        ):
            raise ValueError("saved pinned reading differs from registered cache settings")
        selections.append((reading, digest(vectors), covered_ids(vectors, slug), cache.dimensions))
    result = []
    for encoder, parent, done, dimensions in selections:
        missing = sorted(set(articles) - done)
        for start in range(0, len(missing), shard_rows):
            ids = missing[start : start + shard_rows]
            shard = RunnerShard(
                shard=f"{encoder.slug}-{start // shard_rows:03d}",
                source=source,
                policy=policy,
                parent_revision=parent,
                candidate=encoder if isinstance(encoder, PinnedEncoderCandidate) else None,
                reading=encoder if isinstance(encoder, EncoderReading) else None,
                articles=[articles[i] for i in ids],
                ordered_ids_sha256=digest(ids),
                prefixed_texts_sha256=digest(
                    [encoder.prefix + articles[i].source.summary for i in ids]
                ),
                unit_rows=policy.batch_size,
                dimensions=dimensions,
                model_files=model_files[encoder.model_id] if model_files else [],
            )
            validate_shard(shard)
            write_model(output / "shards" / (shard.shard + ".json"), shard)
            result.append(shard)
    return result


def validate_package(package: RunnerPackage, root: Path, repository: Path) -> None:
    if len({f.path for f in package.files}) != len(package.files):
        raise ValueError("package has repeated file paths")
    for item in package.files:
        path = relative_vector_path(item.path, root)
        if path.stat().st_size != item.bytes or file_hash(path) != item.sha256:
            raise ValueError("package file bytes or hash differ")
    for item in package.code_files:
        path = relative_vector_path(item.path, repository)
        if path.stat().st_size != item.bytes or file_hash(path) != item.sha256:
            raise ValueError("runner code bytes differ from the approved preview")
    if package.runtime_lock not in package.files:
        raise ValueError("runtime lock is not part of the approved package")
    lock = read_model(root / "runtime-lock.json", RunnerRuntimeLock)
    if lock.versions != package.runtime_versions:
        raise ValueError("package runtime versions differ from its installer lock")
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    allowed = {f.path for f in package.files} | {"package.json"}
    if actual - allowed:
        raise ValueError("input package contains unexpected files")
    by_path = {item.path for item in package.files}
    for identity, name in package.shards.items():
        if name not in by_path:
            raise ValueError("shard is not a hashed input file")
        shard = read_model(root / name, RunnerShard)
        validate_shard(shard)
        if identity != shard.shard or shard.source.source_sha256 != package.source_sha256:
            raise ValueError("package names a different shard or source")


def finish_package(
    output: Path,
    shards: list[RunnerShard],
    repository: Path,
    code_commit: str,
    code_paths: list[str],
    requirements: Path,
) -> RunnerPackage:
    runtime_path = output / "runtime-requirements.txt"
    runtime_path.write_bytes(requirements.read_bytes())
    (output / "runtime-lock.json").write_bytes(requirements.with_suffix(".json").read_bytes())
    files = [describe_file(output / "shards" / (s.shard + ".json"), output) for s in shards]
    files.append(describe_file(runtime_path, output))
    files.append(describe_file(output / "runtime-lock.json", output))
    package = RunnerPackage(
        prepared_at=now(),
        source_sha256=shards[0].source.source_sha256,
        code_commit=code_commit,
        files=files,
        shards={s.shard: "shards/" + s.shard + ".json" for s in shards},
        code_files=[describe_committed_code(repository, code_commit, p) for p in code_paths],
        runtime_lock=files[-2],
        runtime_versions=read_model(output / "runtime-lock.json", RunnerRuntimeLock).versions,
    )
    validate_package(package, output, repository)
    write_model(output / "package.json", package)
    with zipfile.ZipFile(
        output.with_suffix(".zip"), "x", compression=zipfile.ZIP_DEFLATED
    ) as bundle:
        for name in ["package.json", *(f.path for f in files)]:
            bundle.writestr(name, (output / name).read_bytes())
    return package
