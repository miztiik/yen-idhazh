"""Replay only genuine ordered legacy calls through the real converter and preparation code."""

import copy
from pathlib import Path

from idhazh.contracts.coverage_model_recording import (
    CoverageModelRecording,
    CoverageRecordedCase,
    CoverageRecordingInputs,
)
from summary_evaluator_cases.contract_examples import REPOSITORY

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.source_coverage.contracts.service_settings import CoverageSettings
from summary_evaluator.source_coverage.load_converter import load_converter
from summary_evaluator.source_coverage.load_settings import load_settings


def read_coverage_recordings() -> tuple[CoverageRecordingInputs, CoverageModelRecording]:
    directory = REPOSITORY / "tests" / "fixtures" / "summary-evaluation"
    inputs = CoverageRecordingInputs.model_validate_json(
        (directory / "coverage-recording-inputs.json").read_bytes()
    )
    recording = CoverageModelRecording.model_validate_json(
        (directory / "coverage-model-recording.json").read_bytes()
    )
    recording.require_inputs(inputs)
    return inputs, recording


def coverage_settings(*, api: ApiSettings | None = None) -> CoverageSettings:
    api = api or load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "coverage"
    )
    return load_settings(REPOSITORY, api.listener, api.logging)


class RecordedCoverageBackend:
    def __init__(
        self, case: CoverageRecordedCase, settings: CoverageSettings, root: Path
    ) -> None:
        import nltk

        nltk.data.path = [str(root / settings.assets.cache_directory / "sentences")]
        self.convert_input = load_converter(settings, root)
        self.recorded, self.calls = case, 0

    def evaluate_dimension(
        self, data: list[dict[str, str]], dimension: str
    ) -> list[dict[str, float]]:
        if self.calls >= len(self.recorded.calls):
            raise AssertionError("There is no genuine recorded call at this position")
        selected = self.recorded.calls[self.calls]
        assert dimension == selected.dimension, "The actual dimension-call order changed"
        assert tuple(data) == selected.inputs, "The actual dimension-call inputs changed"
        self.calls += 1
        return [copy.deepcopy(result) for result in selected.results]
