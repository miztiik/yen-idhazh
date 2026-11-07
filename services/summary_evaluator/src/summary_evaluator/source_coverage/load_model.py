"""How does the real pinned upstream summarization evaluator load in an offline owned process?"""

import hashlib
import importlib
import importlib.metadata
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from summary_evaluator.shared.load_model_assets import resolve_snapshot
from summary_evaluator.shared.quiet_model_output import quiet_model_output
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings


class LegacyEvaluator(Protocol):
    def evaluate(
        self, data: list[dict[str, str]], *, dims: list[str], overall: bool
    ) -> list[dict[str, float]]: ...


class ConvertInput(Protocol):
    def __call__(
        self, *, output_list: list[str], src_list: list[str] | None = None
    ) -> list[dict[str, str]]: ...


@dataclass(frozen=True)
class CoverageModel:
    evaluator: LegacyEvaluator
    convert_input: ConvertInput
    loaded_model_revision: str
    tokenizer_revision: str
    tokenizer_files: dict[str, str]
    runtime_versions: dict[str, str]
    threads: int

    def evaluate_dimension(
        self, data: list[dict[str, str]], dimension: str
    ) -> list[dict[str, float]]:
        with quiet_model_output():
            return self.evaluator.evaluate(data, dims=[dimension], overall=False)


def load_model(settings: CoverageSettings, root: Path) -> CoverageModel:
    from huggingface_hub.constants import HF_HUB_OFFLINE

    if not HF_HUB_OFFLINE:
        raise ValueError("Legacy model loading requires offline resource resolution")
    cache = root / settings.assets.cache_directory
    code = settings.assets.code
    code_directory = cache / "code" / code.revision
    for name, digest in code.files.items():
        path = code_directory / name
        if path.stat().st_size > code.max_file_bytes or hashlib.sha256(
            path.read_bytes()
        ).hexdigest() != digest:
            raise ValueError("The prepared legacy code identity differs")
    selected = settings.assets.model
    snapshot = resolve_snapshot(selected, cache / "model", local_only=True)
    repository_cache = cache / "model" / f"models--{selected.reference.replace('/', '--')}"
    if (repository_cache / "refs" / "main").read_text(encoding="ascii") != selected.revision:
        raise ValueError("The upstream repository name does not resolve to the selected revision")
    with quiet_model_output():
        import nltk
        import torch

        nltk.data.path = [str(cache / "sentences")]
        nltk.tokenize.PunktTokenizer(settings.assets.sentences.language)
        threads = (
            os.cpu_count() or 2
            if settings.model.threads == "logical_processors"
            else settings.model.threads
        )
        torch.set_num_threads(threads)
        sys.path.insert(0, str(code_directory))
        evaluator_module = importlib.import_module("metric.evaluator")
        converter_module = importlib.import_module("utils")
        evaluator_path = evaluator_module.__file__
        converter_path = converter_module.__file__
        if (
            evaluator_path is None
            or converter_path is None
            or Path(evaluator_path).resolve()
            != (code_directory / "metric" / "evaluator.py").resolve()
            or Path(converter_path).resolve() != (code_directory / "utils.py").resolve()
        ):
            raise ValueError("Legacy modules were loaded outside the declared code snapshot")
        evaluator = evaluator_module.get_evaluator(
            "summarization",
            max_length=settings.model.max_length,
            device=settings.model.device,
            cache_dir=str(cache / "model"),
        )
        loaded_revision = evaluator.scorer.config._commit_hash
        if loaded_revision != selected.revision:
            raise ValueError("The loaded legacy model differs from the selected revision")
        if evaluator.scorer.tokenizer.name_or_path != selected.reference:
            raise ValueError("The legacy tokenizer belongs to another model")
        tokenizer_files = {
            name: hashlib.sha256((snapshot / name).read_bytes()).hexdigest()
            for name in selected.files
            if name != "pytorch_model.bin"
        }
        versions = {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "tokenizers", "nltk", "rank-bm25", "prettytable")
        }
    return CoverageModel(
        evaluator=cast(LegacyEvaluator, evaluator),
        convert_input=cast(ConvertInput, converter_module.convert_to_json),
        loaded_model_revision=loaded_revision,
        tokenizer_revision=snapshot.name,
        tokenizer_files=tokenizer_files,
        runtime_versions={"python": platform.python_version(), **versions},
        threads=threads,
    )
