"""Capture genuine legacy dimension calls before relocating the coverage calculation."""

import argparse
import copy
import hashlib
import importlib.util
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from idhazh.contracts.base import canonical_json
from idhazh.contracts.coverage_model_recording import (
    CoverageCaptureProvenance,
    CoverageDimensionCall,
    CoverageModelRecording,
    CoverageRecordedCase,
    CoverageRecordingInputs,
)

from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.source_coverage.contracts.evaluation_result import CoverageMetrics
from summary_evaluator.source_coverage.load_model import CoverageModel, load_model
from summary_evaluator.source_coverage.load_settings import load_settings
from summary_evaluator.source_coverage.prepare_resources import atomic_write


@dataclass
class RecordDimensionCalls:
    model: CoverageModel
    calls: list[CoverageDimensionCall]

    def __call__(self, data: list[dict[str, str]], dimension: str) -> list[dict[str, float]]:
        actual_inputs = copy.deepcopy(data)
        results = self.model.evaluate_dimension(data, dimension)
        self.calls.append(
            CoverageDimensionCall(
                index=len(self.calls),
                dimension=cast(Literal["fluency", "coherence", "consistency"], dimension),
                overall=False,
                inputs=tuple(actual_inputs),
                results=tuple(copy.deepcopy(results)),
            )
        )
        return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / "tests" / "fixtures" / "summary-evaluation"
    inputs = CoverageRecordingInputs.model_validate_json(
        (directory / "coverage-recording-inputs.json").read_bytes()
    )
    producer = ".github/scripts/serve-evaluator.py"
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", producer], cwd=root, check=False
    ).returncode:
        raise ValueError("Commit the concrete legacy call boundary before capturing its revision")
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    spec = importlib.util.spec_from_file_location("legacy_coverage_capture", root / producer)
    if spec is None or spec.loader is None:
        raise ValueError("The named legacy producer could not be loaded")
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    api = load_api_settings(root / "config" / "summary-evals" / "api.json")
    settings = load_settings(root, api.listener, api.logging)
    model = load_model(settings, root)
    effective = settings.model_dump(mode="json")
    effective["model"]["threads"] = model.threads
    cases: list[CoverageRecordedCase] = []
    for case in inputs.cases:
        recorder = RecordDimensionCalls(model, [])
        metrics = legacy.compute_unieval_sync(
            case.source_text,
            case.summary_text,
            convert_input=model.convert_input,
            dimension_call=recorder,
        )
        CoverageMetrics.model_validate_json(canonical_json(metrics))
        cases.append(
            CoverageRecordedCase(
                id=case.id,
                input_sha256=hashlib.sha256(case.model_dump_json().encode("utf-8")).hexdigest(),
                calls=tuple(recorder.calls),
                expected_metrics=metrics,
            )
        )
    code = settings.assets.code
    code_directory = root / settings.assets.cache_directory / "code" / code.revision
    recording = CoverageModelRecording(
        captured_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        inputs_sha256=hashlib.sha256(inputs.to_json().encode("utf-8")).hexdigest(),
        settings_sha256=hashlib.sha256(canonical_json(effective).encode("utf-8")).hexdigest(),
        effective_settings=effective,
        provenance=CoverageCaptureProvenance(
            producer=producer,
            source_revision=revision,
            producer_sha256=hashlib.sha256((root / producer).read_bytes()).hexdigest(),
            code_repository=code.repository,
            code_revision=code.revision,
            code_files={
                name: hashlib.sha256((code_directory / name).read_bytes()).hexdigest()
                for name in code.files
            },
            model_reference=settings.assets.model.reference,
            configured_model_revision=settings.assets.model.revision,
            loaded_model_revision=model.loaded_model_revision,
            tokenizer_revision=model.tokenizer_revision,
            tokenizer_files=model.tokenizer_files,
            runtime_versions=model.runtime_versions,
            platform={
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "logical_processors": os.cpu_count(),
                "model_threads": model.threads,
            },
        ),
        cases=tuple(cases),
    )
    recording.require_inputs(inputs)
    atomic_write(
        directory / "coverage-model-recording.json", recording.to_json().encode("utf-8")
    )
    print(
        "Captured genuine legacy dimension inputs, results and final metrics; "
        "no Linux gate claimed."
    )


if __name__ == "__main__":
    main()
