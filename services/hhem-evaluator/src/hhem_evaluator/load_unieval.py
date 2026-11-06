"""How does the official CPU T5 model score an uncut native UniEval prompt?"""

import math
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from hhem_evaluator.contracts.unieval_error import UnievalError
from hhem_evaluator.contracts.unieval_result import UnievalModelIdentity, UnievalRuntimeVersions
from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.fail_unieval import UnievalFailure
from hhem_evaluator.load_model_assets import resolve_snapshot
from hhem_evaluator.load_unieval_resources import UnievalResources, load_unieval_resources
from hhem_evaluator.shared.quiet_model_output import quiet_model_output


class UnievalPredictor(Protocol):
    identity: UnievalModelIdentity
    resources: UnievalResources

    def score(self, prompt: str) -> float: ...


@dataclass
class CpuUnievalPredictor:
    model: object
    identity: UnievalModelIdentity
    resources: UnievalResources
    positive_id: int
    negative_id: int
    max_input_tokens: int

    def score(self, prompt: str) -> float:
        import torch
        from transformers import PreTrainedModel

        encoded = self.resources.tokenizer.encode(
            prompt, add_special_tokens=True, truncation=False, verbose=False
        )
        if len(encoded) > self.max_input_tokens:
            raise UnievalFailure(UnievalError.from_code("CONSISTENCY_INPUT_TOO_LONG"))
        inputs = torch.tensor([encoded], dtype=torch.long, device="cpu")
        target = torch.tensor([[self.negative_id]], dtype=torch.long, device="cpu")
        with torch.inference_mode():
            output = cast(PreTrainedModel, self.model)(
                input_ids=inputs, attention_mask=torch.ones_like(inputs), labels=target
            )
            probabilities = torch.softmax(output.logits[0, 0], dim=-1)
            positive = float(probabilities[self.positive_id].item())
            negative = float(probabilities[self.negative_id].item())
        denominator = positive + negative
        score = positive / denominator if denominator else float("nan")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise UnievalFailure(UnievalError.from_code("INVALID_MODEL_OUTPUT"))
        return score


def load_unieval(settings: UnievalSettings, root: Path) -> UnievalPredictor:
    try:
        with quiet_model_output():
            import nltk
            import tokenizers
            import torch
            import transformers
            from transformers import AutoModelForSeq2SeqLM

            resources = load_unieval_resources(settings, root)
            snapshot = resolve_snapshot(
                settings.assets.model,
                root / settings.assets.cache_directory,
                local_only=True,
            )
            model = AutoModelForSeq2SeqLM.from_pretrained(
                str(snapshot), local_files_only=True, torch_dtype="auto"
            )
            model.to("cpu")
            model.eval()
            identity = UnievalModelIdentity(
                reference=settings.assets.model.reference,
                configured_revision=settings.assets.model.revision,
                loaded_revision=snapshot.name,
                tokenizer_revision=resources.snapshot.name,
                reference_code_revision=settings.assets.reference_code_revision,
                runtime_versions=UnievalRuntimeVersions(
                    python=platform.python_version(),
                    pytorch=torch.__version__,
                    transformers=transformers.__version__,
                    tokenizers=tokenizers.__version__,
                    nltk=nltk.__version__,
                ),
            )
            positive = resources.tokenizer.encode(settings.prompts.positive_answer)[0]
            negative = resources.tokenizer.encode(settings.prompts.negative_answer)[0]
            if positive == negative:
                raise ValueError("The declared answers encode the same first token")
            return CpuUnievalPredictor(
                model, identity, resources, positive, negative, settings.scoring.max_input_tokens
            )
    except UnievalFailure:
        raise
    except Exception:
        raise UnievalFailure(UnievalError.from_code("MODEL_LOAD_FAILED")) from None
