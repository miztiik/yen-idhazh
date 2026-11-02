"""Which actual loaded tensors, configuration and named assets identify a model?"""

import hashlib
import json
import platform
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from .contracts.model_identity import ModelIdentity, RuntimeVersions
from .contracts.service_settings import ServiceSettings


class TensorArray(Protocol):
    def tobytes(self) -> bytes: ...


class LoadedTensor(Protocol):
    dtype: object
    shape: tuple[int, ...]

    def detach(self) -> "LoadedTensor": ...
    def cpu(self) -> "LoadedTensor": ...
    def contiguous(self) -> "LoadedTensor": ...
    def numpy(self) -> TensorArray: ...


class LoadedConfiguration(Protocol):
    foundation: str

    def to_dict(self) -> dict[str, object]: ...


class FingerprintableModel(Protocol):
    config: LoadedConfiguration
    prompt: str

    def state_dict(self) -> Mapping[str, LoadedTensor]: ...


def canonical_bytes(value: object) -> bytes:
    """Make configuration hashing independent of mapping insertion order."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def settings_digest(settings: ServiceSettings) -> str:
    return hashlib.sha256(canonical_bytes(settings.model_dump(mode="json"))).hexdigest()


def _logical_config(value: object, paths: Mapping[str, str]) -> object:
    if isinstance(value, str):
        return paths.get(value, value)
    if isinstance(value, dict):
        return {key: _logical_config(child, paths) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_logical_config(child, paths) for child in value]
    return value


def fingerprint_model(
    model: FingerprintableModel,
    settings: ServiceSettings,
    model_directory: Path,
    foundation_directory: Path,
    *,
    pytorch_version: str,
    transformers_version: str,
) -> ModelIdentity:
    """Hash observed values, normalizing only the two local snapshot locations."""
    weights = hashlib.sha256()
    tensors = model.state_dict()
    if not tensors:
        raise ValueError("The loaded model has no tensors.")
    for name in sorted(tensors):
        tensor = tensors[name]
        metadata = canonical_bytes(
            {"name": name, "dtype": str(tensor.dtype), "shape": list(tensor.shape)}
        )
        weights.update(len(metadata).to_bytes(8, "big"))
        weights.update(metadata)
        data = tensor.detach().cpu().contiguous().numpy().tobytes()
        weights.update(len(data).to_bytes(8, "big"))
        weights.update(data)
    paths = {
        str(model_directory): (f"{settings.hhem.model.reference}@{settings.hhem.model.revision}"),
        str(foundation_directory): (
            f"{settings.hhem.foundation.reference}@{settings.hhem.foundation.revision}"
        ),
    }
    assets: dict[str, dict[str, str]] = {}
    for label, selection, directory in (
        ("model", settings.hhem.model, model_directory),
        ("foundation", settings.hhem.foundation, foundation_directory),
    ):
        assets[label] = {}
        for filename in selection.files:
            if filename.endswith(".safetensors"):
                continue
            with (directory / filename).open("rb") as stream:
                assets[label][filename] = hashlib.file_digest(stream, "sha256").hexdigest()
    configuration = {
        "config": _logical_config(model.config.to_dict(), paths),
        "prompt": model.prompt,
        "assets": assets,
    }
    return ModelIdentity(
        reference=settings.hhem.model.reference,
        configured_revision=settings.hhem.model.revision,
        loaded_revision=model_directory.name,
        foundation_reference=settings.hhem.foundation.reference,
        foundation_revision=foundation_directory.name,
        loaded_weights_sha256=weights.hexdigest(),
        loaded_config_sha256=hashlib.sha256(canonical_bytes(configuration)).hexdigest(),
        service_config_sha256=settings_digest(settings),
        runtime_versions=RuntimeVersions(
            python=platform.python_version(),
            pytorch=pytorch_version,
            transformers=transformers_version,
        ),
    )
