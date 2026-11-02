"""How is the official CPU predictor loaded from named immutable local assets?"""

import contextlib
import math
import os
import platform
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from .contracts.error_detail import ErrorDetail
from .contracts.model_identity import ModelIdentity, RuntimeVersions
from .contracts.service_settings import ModelAssetSettings, ServiceSettings
from .fail_evaluation import EvaluationFailure


class Prediction(Protocol):
    def numel(self) -> int: ...
    def item(self) -> float: ...


class OfficialModel(Protocol):
    def to(self, device: str) -> "OfficialModel": ...
    def eval(self) -> "OfficialModel": ...
    def predict(self, pairs: list[tuple[str, str]]) -> Prediction: ...


class Predictor(Protocol):
    identity: ModelIdentity

    def score(self, source: str, summary: str) -> float: ...


@contextlib.contextmanager
def quiet_model_output() -> Iterator[None]:
    """Discard untrusted native and Python diagnostics rather than forwarding them."""
    with open(os.devnull, "w", encoding="utf-8") as sink:
        saved = [(descriptor, os.dup(descriptor)) for descriptor in (1, 2)]
        try:
            for descriptor, _ in saved:
                os.dup2(sink.fileno(), descriptor)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
        finally:
            for descriptor, original in saved:
                os.dup2(original, descriptor)
                os.close(original)


def _snapshot(selection: ModelAssetSettings, cache: Path, local_only: bool) -> Path:
    from huggingface_hub import hf_hub_download

    directory: Path | None = None
    for filename in selection.files:
        asset = Path(
            hf_hub_download(
                repo_id=selection.reference,
                revision=selection.revision,
                filename=filename,
                cache_dir=str(cache),
                local_files_only=local_only,
            )
        )
        if asset.name != filename or asset.parent.name != selection.revision:
            raise ValueError("The downloaded asset does not identify the selected revision.")
        if directory is not None and asset.parent != directory:
            raise ValueError("The selected assets do not share an immutable snapshot.")
        directory = asset.parent
    if directory is None:
        raise ValueError("The selected asset inventory is empty.")
    return directory


@dataclass
class CpuPredictor:
    """Keep the official model call and finite scalar validation at one boundary."""

    model: OfficialModel
    identity: ModelIdentity

    def score(self, source: str, summary: str) -> float:
        import torch

        with torch.inference_mode():
            predicted = self.model.predict([(source, summary)])
        if predicted.numel() != 1:
            raise EvaluationFailure(ErrorDetail.from_code("INVALID_MODEL_OUTPUT", "worker"))
        score = float(predicted.item())
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise EvaluationFailure(ErrorDetail.from_code("INVALID_MODEL_OUTPUT", "worker"))
        return score


def load_model(settings: ServiceSettings, root: Path, *, local_only: bool) -> Predictor:
    """Use public loader/configuration interfaces without modifying model internals."""
    try:
        with quiet_model_output():
            cache = (root / settings.hhem.cache_directory).resolve()
            os.environ["HF_MODULES_CACHE"] = str(cache / "modules")
            import torch
            import transformers
            from huggingface_hub.utils import disable_progress_bars
            from transformers import AutoConfig, AutoModelForSequenceClassification

            disable_progress_bars()
            model_directory = _snapshot(settings.hhem.model, cache, local_only)
            foundation_directory = _snapshot(settings.hhem.foundation, cache, local_only)
            config = AutoConfig.from_pretrained(
                str(model_directory), trust_remote_code=True, local_files_only=True
            )
            config.foundation = str(foundation_directory)
            model = cast(
                OfficialModel,
                AutoModelForSequenceClassification.from_pretrained(
                    str(model_directory),
                    config=config,
                    trust_remote_code=True,
                    local_files_only=True,
                    torch_dtype="auto",
                ),
            )
            model.to("cpu")
            model.eval()
            identity = ModelIdentity(
                reference=settings.hhem.model.reference,
                configured_revision=settings.hhem.model.revision,
                loaded_revision=model_directory.name,
                foundation_reference=settings.hhem.foundation.reference,
                foundation_revision=foundation_directory.name,
                runtime_versions=RuntimeVersions(
                    python=platform.python_version(),
                    pytorch=torch.__version__,
                    transformers=transformers.__version__,
                ),
            )
            return CpuPredictor(model, identity)
    except Exception:
        raise EvaluationFailure(ErrorDetail.from_code("MODEL_LOAD_FAILED", "worker")) from None
