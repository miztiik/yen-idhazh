"""How are configured model assets prepared and loaded without runtime downloads?"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from gliner_api.configure_native_diagnostics import (
    configure_native_diagnostics,
    filter_encoder_deprecation,
    native_operation,
)

if TYPE_CHECKING:
    from gliner_api.load_settings import GlinerSettings

# Native checkpoint and tokenizer filenames are format identifiers, not model choices.
_REQUIRED_ASSETS: Final = (
    Path("config.json"),
    Path("encoder_config") / "config.json",
    Path("tokenizer_config.json"),
)
_TOKENIZER_LAYOUTS: Final = (
    (Path("tokenizer.json"),),
    (Path("vocab.txt"),),
    (Path("vocab.json"), Path("merges.txt")),
    (Path("spm.model"),),
    (Path("sentencepiece.bpe.model"),),
    (Path("tokenizer.model"),),
)
# CPU is this provider's execution target, not a caller-selected model setting.
CPU_DEVICE: Final = "cpu"


class ModelLoadError(RuntimeError):
    """Report unavailable assets or native capabilities without raw exceptions."""

    def __init__(self) -> None:
        super().__init__("The configured GLiNER model is not available.")


@runtime_checkable
class NativeModel(Protocol):
    """Expose the two real native long-text operations required by the API."""

    def extract_entities_long(
        self,
        text: str,
        entity_types: list[str],
        *,
        include_confidence: bool,
        include_spans: bool,
    ) -> object: ...

    def classify_text_long(
        self,
        text: str,
        tasks: dict[str, dict[str, object]],
        *,
        include_confidence: bool,
    ) -> object: ...


def _has_asset(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _require_local_assets(snapshot: Path) -> None:
    """Check one snapshot's named inputs without claiming inference readiness."""
    if not snapshot.is_dir() or not all(
        _has_asset(snapshot / asset) for asset in _REQUIRED_ASSETS
    ):
        raise ModelLoadError()
    safetensors = snapshot / "model.safetensors"
    weights = safetensors if safetensors.is_file() else snapshot / "pytorch_model.bin"
    if not _has_asset(weights) or not any(
        all(_has_asset(snapshot / asset) for asset in layout) for layout in _TOKENIZER_LAYOUTS
    ):
        raise ModelLoadError()


def _resolve_snapshot(
    settings: GlinerSettings, root: Path, *, local_files_only: bool
) -> Path:
    from huggingface_hub import snapshot_download

    from gliner_api.load_settings import MODEL_CACHE_PATH

    snapshot = Path(
        snapshot_download(
            repo_id=settings.model.repo,
            endpoint=settings.model.base_url,
            cache_dir=root / MODEL_CACHE_PATH,
            local_files_only=local_files_only,
        )
    )
    _require_local_assets(snapshot)
    return snapshot


def prepare_model(root: Path) -> Path:
    """Download one configured snapshot; native loading remains a separate check."""
    try:
        with native_operation():
            configure_native_diagnostics()
            from gliner_api.load_settings import load_settings

            settings = load_settings(root)
            if not settings.enabled:
                raise ModelLoadError()
            snapshot = _resolve_snapshot(settings, root, local_files_only=False)
        return snapshot
    except Exception:
        raise ModelLoadError() from None


def load_model(settings: GlinerSettings, root: Path) -> NativeModel:
    """Load the prepared local directory on CPU, with no inference-time Hub fetch."""
    try:
        if not settings.enabled:
            raise ModelLoadError()
        with native_operation():
            configure_native_diagnostics()
            snapshot = _resolve_snapshot(settings, root, local_files_only=True)
            with filter_encoder_deprecation():
                from gliner2 import AutoExtractor

                model: object = AutoExtractor.from_pretrained(
                    str(snapshot), map_location=CPU_DEVICE, local_files_only=True
                )
            if (
                not isinstance(model, NativeModel)
                or not callable(model.extract_entities_long)
                or not callable(model.classify_text_long)
            ):
                raise ModelLoadError()
        return model
    except Exception:
        raise ModelLoadError() from None
