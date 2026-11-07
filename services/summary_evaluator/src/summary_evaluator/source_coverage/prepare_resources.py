"""How are the exact legacy code, tokenizer, sentence rules and optional weights prepared?"""

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

import httpx

from summary_evaluator.shared.load_model_assets import resolve_snapshot
from summary_evaluator.source_coverage.contracts.service_settings import (
    CoverageSentenceResources,
    CoverageSettings,
)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_bounded_url(url: str, maximum: int, timeout_ms: int) -> bytes:
    data = bytearray()
    with httpx.stream(
        "GET", url, timeout=timeout_ms / 1000, follow_redirects=False, trust_env=False
    ) as response:
        response.raise_for_status()
        for block in response.iter_bytes():
            if len(data) + len(block) > maximum:
                raise ValueError("A named coverage resource exceeds its declared allowance")
            data.extend(block)
    return bytes(data)


def extract_sentences(
    archive: Path, destination: Path, selected: CoverageSentenceResources
) -> None:
    with zipfile.ZipFile(archive) as source:
        for name in selected.files:
            if source.getinfo(name).file_size > selected.max_archive_bytes:
                raise ValueError("A named sentence resource exceeds its declared allowance")
            # NLTK's public sentence API resolves these archive entries below tokenizers/.
            atomic_write(destination / "tokenizers" / name, source.read(name))


def prepare_resources(root: Path, settings: CoverageSettings, *, include_weights: bool) -> None:
    cache = root / settings.assets.cache_directory
    code = settings.assets.code
    for name, digest in code.files.items():
        path = cache / "code" / code.revision / name
        if not path.is_file():
            data = read_bounded_url(
                f"https://raw.githubusercontent.com/{code.repository}/{code.revision}/{name}",
                code.max_file_bytes,
                code.download_timeout_ms,
            )
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Downloaded legacy code does not match its immutable digest")
            atomic_write(path, data)
        if path.stat().st_size > code.max_file_bytes or hashlib.sha256(
            path.read_bytes()
        ).hexdigest() != digest:
            raise ValueError("Prepared legacy code does not match its immutable digest")

    model = settings.assets.model
    files = model.files if include_weights else tuple(
        name for name in model.files if name != "pytorch_model.bin"
    )
    resolve_snapshot(model.model_copy(update={"files": files}), cache / "model", local_only=False)
    # The upstream loader names its repository but has no revision argument. Its private
    # offline cache resolves that one name to the verified immutable snapshot, not live main.
    repository_cache = cache / "model" / f"models--{model.reference.replace('/', '--')}"
    atomic_write(repository_cache / "refs" / "main", model.revision.encode("ascii"))

    sentences = settings.assets.sentences
    archive = cache / "sentences" / "punkt_tab.zip"
    if not archive.is_file():
        data = read_bounded_url(
            sentences.archive_url, sentences.max_archive_bytes, sentences.download_timeout_ms
        )
        if hashlib.sha256(data).hexdigest() != sentences.archive_sha256:
            raise ValueError("Downloaded sentence rules do not match the pinned digest")
        atomic_write(archive, data)
    if archive.stat().st_size > sentences.max_archive_bytes or hashlib.sha256(
        archive.read_bytes()
    ).hexdigest() != sentences.archive_sha256:
        raise ValueError("Prepared sentence rules do not match the pinned digest")
    extract_sentences(archive, cache / "sentences", sentences)
