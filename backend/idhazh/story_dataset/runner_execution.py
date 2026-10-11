"""Run one approved missing-only shard on GitHub, keeping every complete twenty-row unit."""

import hashlib
import os
import platform
import time
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from packaging.version import Version

from idhazh.contracts.story_candidates import VectorCache
from idhazh.contracts.story_encoder_candidate import CandidateVectorUnit
from idhazh.contracts.story_runner import (
    RunnerPackage,
    RunnerResult,
    RunnerRuntimeLock,
    RunnerShard,
)
from idhazh.contracts.story_vectors import VectorExtensionSnapshot
from idhazh.story_dataset.runner_inputs import describe_file, validate_package, validate_shard
from idhazh.story_dataset.storage import canonical, digest, file_hash, now, read_model, write_model


def save_unit(
    shard: RunnerShard,
    ids: list[str],
    matrix: np.ndarray[Any, Any],
    output: Path,
    runtime: dict[str, str],
) -> CandidateVectorUnit | VectorExtensionSnapshot:
    validate_shard(shard)
    articles = {a.article_id: a for a in shard.articles}
    if (
        not ids
        or len(ids) > shard.unit_rows
        or len(set(ids)) != len(ids)
        or not set(ids) <= articles.keys()
        or matrix.shape != (len(ids), shard.dimensions)
        or matrix.dtype != np.dtype("float32")
        or not np.isfinite(matrix).all()
        or np.any(np.linalg.norm(matrix, axis=1) == 0)
    ):
        raise ValueError("runner unit IDs, native float32 shape or numeric values differ")
    encoder = shard.encoder
    path = output / "vectors" / (digest(ids) + ".npy")
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with part.open("xb") as stream:
            np.save(stream, matrix, allow_pickle=False)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            if path.read_bytes() != part.read_bytes():
                raise ValueError("immutable returned vector bytes differ")
        else:
            os.link(part, path)
    finally:
        part.unlink(missing_ok=True)
    fields: dict[str, Any] = {
        "path_base": "dataset-root",
        "source_sha256": shard.source.source_sha256,
        "slug": encoder.slug,
        "article_ids": ids,
        "article_input_sha256": [articles[i].input_sha256 for i in ids],
        "summary_sha256": [
            hashlib.sha256(articles[i].source.summary.encode()).hexdigest() for i in ids
        ],
        "runtime_versions": runtime,
        "cache": VectorCache(
            slug=encoder.slug,
            file=path.relative_to(output).as_posix(),
            file_sha256=file_hash(path),
            rows=len(ids),
            dimensions=shard.dimensions,
            reading_sha256=digest(encoder),
            input_sha256=digest([encoder.prefix + articles[i].source.summary for i in ids]),
            model_id=encoder.model_id,
            revision=str(encoder.model_options["revision"]),
            settings_sha256=digest(
                {
                    "prefix": encoder.prefix,
                    "model_options": encoder.model_options,
                    "encode_options": encoder.encode_options,
                }
            ),
        ),
    }
    unit: CandidateVectorUnit | VectorExtensionSnapshot
    if shard.candidate:
        unit = CandidateVectorUnit(
            **fields, candidate_revision=digest(shard.candidate), encoded_at=now()
        )
    else:
        unit = VectorExtensionSnapshot(**fields)
    write_model(output / "units" / (digest(ids) + ".json"), unit)
    return unit


def run_shard(
    package: RunnerPackage,
    package_root: Path,
    repository: Path,
    shard: RunnerShard,
    output: Path,
    soft_stop_minutes: int,
) -> RunnerResult:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or platform.system() != "Linux"
        or os.environ.get("GITHUB_SHA") != package.code_commit
        or not 1 <= soft_stop_minutes <= 300
    ):
        raise ValueError("inference is GitHub-runner-only at the approved code commit")
    memory_bytes = int(
        next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
             if line.startswith("MemTotal:"))
    ) * 1024
    if os.cpu_count() != package.runner_cpus or memory_bytes < package.runner_min_memory_bytes:
        raise ValueError("approved encoding requires a four-CPU, sixteen-GB GitHub runner")
    validate_package(package, package_root, repository)
    if (
        package.shards.get(shard.shard) is None
        or read_model(package_root / package.shards[shard.shard], RunnerShard) != shard
    ):
        raise ValueError("shard is not the approved package input")
    lock = read_model(package_root / "runtime-lock.json", RunnerRuntimeLock)
    runtime = {name: version(name) for name in lock.versions}
    if runtime != lock.versions or ".".join(platform.python_version_tuple()[:2]) != lock.python:
        raise ValueError("installed runtime differs from the exact Linux dependency lock")
    if (
        Version(runtime["sentence-transformers"]) < Version("6.1")
        or Version(runtime["transformers"]) < Version("5.19")
        or not runtime["torch"].endswith("+cpu")
        or not runtime["torchvision"].endswith("+cpu")
    ):
        raise ValueError("unsupported processor or mismatched CPU tensor/vision runtime")
    started = now()
    deadline = time.monotonic() + soft_stop_minutes * 60
    ids = [a.article_id for a in shard.articles]
    units: list[CandidateVectorUnit | VectorExtensionSnapshot] = []
    model_files = []
    resumed_from = None
    if (output / "result.json").exists():
        from idhazh.story_dataset.runner_results import recover_result

        prior = recover_result(shard, package, output)
        units = prior.units
        model_files = prior.model_files
        runtime = dict(prior.runtime_versions)
        resumed_from = digest(prior)
    done = {i for u in units for i in u.article_ids}
    error = None
    save_progress(package, shard, output, units, runtime, model_files, started, None,
                  resumed_from)
    try:
        import torch
        import torchvision  # type: ignore[import-not-found]
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer
        processor = import_module("transformers").EmbeddingGemma2Processor

        if torch.version.cuda is not None:
            raise ValueError("CPU-only tensor runtime required")
        torchvision.ops.nms(torch.tensor([[0.0, 0.0, 1.0, 1.0]]), torch.tensor([1.0]), 0.5)
        runtime["processor"] = processor.__name__
        torch.set_num_threads(shard.policy.encoding_threads)
        encoder_input = shard.encoder
        if not shard.model_files:
            raise ValueError("expected pinned model/tokenizer/custom-code file hashes are required")
        snapshot = Path(
            snapshot_download(
                encoder_input.model_id,
                revision=str(encoder_input.model_options["revision"]),
                allow_patterns=[f.path for f in shard.model_files],
            )
        )
        acquired_files = [describe_file(snapshot / f.path, snapshot) for f in shard.model_files]
        if acquired_files != shard.model_files:
            raise ValueError("downloaded pinned model/tokenizer/custom-code bytes differ")
        model_files = acquired_files
        save_progress(package, shard, output, units, runtime, model_files, started, None,
                      resumed_from)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        options: dict[str, Any] = dict(encoder_input.model_options)
        encode_options: dict[str, Any] = dict(encoder_input.encode_options)
        options["local_files_only"] = True
        encoder = SentenceTransformer(
            encoder_input.model_id,
            device="cpu",
            **options,
        )
        encoder.max_seq_length = 256
        for start in range(0, len(ids), shard.unit_rows):
            selected = ids[start : start + shard.unit_rows]
            if set(selected) <= done:
                continue
            if set(selected) & done:
                raise ValueError("resumed result splits an immutable encoding unit")
            if time.monotonic() >= deadline:
                break
            articles = {a.article_id: a for a in shard.articles}
            matrix = np.asarray(
                encoder.encode(
                    [encoder_input.prefix + articles[i].source.summary for i in selected],
                    batch_size=shard.policy.encoding_batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    **encode_options,
                ),
                dtype=np.float32,
            )
            unit = save_unit(shard, selected, matrix, output, runtime)
            units.append(unit)
            done.update(selected)
            save_progress(package, shard, output, units, runtime, model_files, started, None,
                          resumed_from)
    except Exception as failure:
        error = f"{type(failure).__name__}: {failure}"
    return save_progress(package, shard, output, units, runtime, model_files, started, error,
                         resumed_from)


def save_progress(
    package: RunnerPackage,
    shard: RunnerShard,
    output: Path,
    units: list[CandidateVectorUnit | VectorExtensionSnapshot],
    runtime: dict[str, str],
    model_files: list[Any],
    started: str,
    error: str | None,
    resumed_from: str | None = None,
) -> RunnerResult:
    resource = import_module("resource")

    done = {i for u in units for i in u.article_ids}
    pending = [a.article_id for a in shard.articles if a.article_id not in done]
    result = RunnerResult(
        shard_sha256=digest(shard),
        package_sha256=digest(package),
        shard=shard.shard,
        code_commit=package.code_commit,
        run_id=os.environ["GITHUB_RUN_ID"],
        run_attempt=os.environ["GITHUB_RUN_ATTEMPT"],
        repository=os.environ["GITHUB_REPOSITORY"],
        started_at=started,
        finished_at=now(),
        runtime_versions=runtime,
        model_files=model_files,
        host={
            "platform": platform.platform(),
            "cpu": platform.processor(),
            "cpu_count": str(os.cpu_count()),
            "peak_rss_kib": str(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            "threads": str(shard.policy.encoding_threads),
            "encoding_batch_size": str(shard.policy.encoding_batch_size),
        },
        files=[
            describe_file(output / path, output)
            for u in units
            for path in (u.cache.file, "units/" + digest(u.article_ids) + ".json")
        ],
        units=units,
        pending_article_ids=pending,
        state="failed" if error else ("partial" if pending else "complete"),
        error=error,
        resumed_from=resumed_from,
    )
    output.mkdir(parents=True, exist_ok=True)
    part = output / "result.json.part"
    part.write_bytes(canonical(result))
    part.replace(output / "result.json")
    return result
