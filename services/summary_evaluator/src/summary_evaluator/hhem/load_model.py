"""How is the official CPU predictor loaded from named immutable local assets?"""

import math
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.contracts.model_identity import ModelIdentity, RuntimeVersions
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure
from summary_evaluator.shared.load_model_assets import resolve_snapshot
from summary_evaluator.shared.quiet_model_output import quiet_model_output


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
            from huggingface_hub.utils.tqdm import disable_progress_bars
            from transformers import AutoConfig, AutoModelForSequenceClassification

            disable_progress_bars()
            model_directory = resolve_snapshot(settings.hhem.model, cache, local_only=local_only)
            foundation_directory = resolve_snapshot(
                settings.hhem.foundation, cache, local_only=local_only
            )
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
