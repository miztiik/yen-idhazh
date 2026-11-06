"""How are only the declared UniEval assets prepared before offline execution?"""

import hashlib
import os
import tempfile
import zipfile
from pathlib import Path

import httpx

from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.load_model_assets import resolve_snapshot


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


def prepare_unieval_resources(
    root: Path, settings: UnievalSettings, *, include_weights: bool
) -> None:
    files = settings.assets.model.files
    if not include_weights:
        files = tuple(name for name in files if name != "pytorch_model.bin")
    resolve_snapshot(
        settings.assets.model.model_copy(update={"files": files}),
        root / settings.assets.cache_directory,
        local_only=False,
    )
    selected = settings.assets.sentences
    cache = root / settings.assets.cache_directory / "sentences"
    archive = cache / "punkt_tab.zip"
    if not archive.is_file():
        encoded = bytearray()
        with httpx.stream(
            "GET",
            selected.archive_url,
            timeout=selected.download_timeout_ms / 1000,
            follow_redirects=False,
            trust_env=False,
        ) as response:
            response.raise_for_status()
            for block in response.iter_bytes():
                if len(encoded) + len(block) > selected.max_archive_bytes:
                    raise ValueError("The pinned sentence archive exceeds its allowance")
                encoded.extend(block)
        if hashlib.sha256(encoded).hexdigest() != selected.archive_sha256:
            raise ValueError("The downloaded sentence archive digest does not match")
        atomic_write(archive, bytes(encoded))
    if archive.stat().st_size > selected.max_archive_bytes:
        raise ValueError("The prepared sentence archive exceeds its allowance")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != selected.archive_sha256:
        raise ValueError("The prepared sentence archive digest does not match")
    with zipfile.ZipFile(archive) as source:
        for name in selected.files:
            info = source.getinfo(name)
            if info.file_size > selected.max_archive_bytes:
                raise ValueError("A declared sentence resource exceeds its allowance")
            atomic_write(cache / name, source.read(info))
