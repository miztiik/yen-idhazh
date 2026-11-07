"""Does the relocated real calculation exactly replay genuine calls, metrics and evidence?"""

import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_recordings import (
    RecordedCoverageBackend,
    coverage_settings,
    read_coverage_recordings,
)

from summary_evaluator.source_coverage.contracts.scoring_warning import CoverageWarningCode
from summary_evaluator.source_coverage.prepare_text import chunk_document, extract_macro_skeleton
from summary_evaluator.source_coverage.retrieve_evidence import EvidenceRetriever
from summary_evaluator.source_coverage.score_coverage import score_coverage


@pytest.mark.parametrize("index", [0, 1])
def test_genuine_calls_replay_to_exact_legacy_metrics_and_evidence(index: int) -> None:
    inputs, recording = read_coverage_recordings()
    settings = coverage_settings()
    selected, captured = inputs.cases[index], recording.cases[index]
    backend = RecordedCoverageBackend(captured, settings, REPOSITORY)
    warnings: list[CoverageWarningCode] = []
    result = score_coverage(
        selected.source_text, selected.summary_text, settings.preparation, backend, warnings.append
    )
    assert result == captured.expected_metrics
    assert backend.calls == len(captured.calls)
    assert not warnings


def test_preparation_knobs_change_real_boundaries_without_source_edits() -> None:
    settings = coverage_settings().preparation
    changed = settings.model_copy(update={"chunk_words": 5, "stride_words": 1})
    source = "one two three four five six seven eight nine ten eleven"
    assert chunk_document(source, changed) == [
        "one two three four five",
        "five six seven eight nine",
        "nine ten eleven",
    ]
    assert chunk_document(source, settings) == [source]
    assert extract_macro_skeleton("", settings) == settings.empty_macro


def test_actual_bm25_failure_uses_the_retained_fallback_and_safe_warning() -> None:
    warnings: list[CoverageWarningCode] = []
    retriever = EvidenceRetriever([], coverage_settings().preparation, warnings.append)
    assert retriever.retrieve_top_k("A sentence.") == []
    assert warnings == ["RETRIEVAL_FALLBACK"]
