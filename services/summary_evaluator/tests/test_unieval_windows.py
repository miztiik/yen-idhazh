"""Prove real tokenizer windows cover source ends without clipping native prompts."""

from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.unieval_cases import (
    read_unieval_inputs,
    read_unieval_recordings,
    recorded_unieval_request,
    unieval_settings,
)

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import SourceSpan
from summary_evaluator.unieval.load_unieval_resources import load_unieval_resources
from summary_evaluator.unieval.score_unieval import prepare_unieval


def test_default_full_source_has_one_consistency_comparison_per_summary_sentence() -> None:
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    resources = load_unieval_resources(settings, REPOSITORY)
    source = "  The garden opened on Monday.\n" * 100
    summary = "The garden opened on Monday. Visitors entered the garden."
    request = UnievalRequest(source_text=source, summary_text=summary)
    sentences = tuple(resources.sentences.tokenize(summary))
    offsets = resources.source_offsets(source)
    assert len(offsets) > settings.scoring.source_window_tokens
    assert len(sentences) == 2

    plan = prepare_unieval(request, settings, resources)
    assert not plan.errors
    assert plan.controls.consistency_source_mode == "full_source_prompt"
    assert plan.work.source_spans == (SourceSpan(start=0, end=len(source)),)
    assert plan.work.summary_sentences == len(sentences)
    assert plan.work.consistency.planned == len(sentences)
    assert [
        (item.sentence_index, item.source_index, item.summary, item.source)
        for item in plan.comparisons if item.dimension == "consistency"
    ] == [(index, 0, sentence, source) for index, sentence in enumerate(sentences)]
    coherence = next(item for item in plan.comparisons if item.dimension == "coherence")
    assert coherence.summary == summary and coherence.source == source
    assert all(
        resources.token_count(item.prompt) <= settings.scoring.max_input_tokens
        for item in plan.comparisons
    )
    assert request.source_text == source and request.summary_text == summary
    assert request.consistency_source_mode is None

    explicit = UnievalRequest(
        source_text=source, summary_text=summary, consistency_source_mode="all_source_windows"
    )
    windows = prepare_unieval(explicit, settings, resources)
    spans = windows.work.source_spans
    assert not windows.errors and windows.controls.consistency_source_mode == "all_source_windows"
    assert len(spans) > 1
    assert spans[0].start == 0 and spans[-1].end == len(source)
    for previous, current in zip(spans, spans[1:], strict=False):
        assert previous.start < current.start < previous.end < current.end
        assert sum(
            current.start <= start < previous.end for start, _ in offsets
        ) >= settings.scoring.source_overlap_tokens
    assert windows.work.consistency.planned == len(sentences) * len(spans)
    assert [
        (item.sentence_index, item.source_index, item.summary, item.source)
        for item in windows.comparisons if item.dimension == "consistency"
    ] == [
        (sentence_index, source_index, sentence, source[span.start:span.end])
        for sentence_index, sentence in enumerate(sentences)
        for source_index, span in enumerate(spans)
    ]
    assert all(
        resources.token_count(item.prompt) <= settings.scoring.max_input_tokens
        for item in windows.comparisons
    )
    assert explicit.source_text == source and explicit.summary_text == summary


def test_actual_tokenizer_plan_covers_all_source_spans_and_recorded_prompts() -> None:
    _, settings = unieval_settings()
    resources = load_unieval_resources(settings, REPOSITORY)
    inputs, predictions, _ = read_unieval_recordings()
    case = inputs.cases[0]
    plan = prepare_unieval(recorded_unieval_request(case.request), settings, resources)
    assert len(plan.work.source_spans) > 1
    assert plan.work.source_spans[0].start == 0
    assert plan.work.source_spans[-1].end == len(case.request.source_text)
    for left, right in zip(plan.work.source_spans, plan.work.source_spans[1:], strict=False):
        assert right.start < left.end
    assert plan.work == predictions.cases[0].work
    assert len(plan.comparisons) == len(predictions.cases[0].comparisons)
    for comparison in plan.comparisons:
        assert resources.token_count(comparison.prompt) <= settings.scoring.max_input_tokens
    count = plan.work.summary_sentences
    assert count is not None
    assert plan.work.consistency.planned == count * len(plan.work.source_spans)


def test_full_source_overflow_never_retries_windows_or_shortens_the_inputs() -> None:
    _, settings = unieval_settings(
        consistency_source_mode="full_source_prompt", evaluate_relevance=False,
        max_input_tokens=80, source_window_tokens=24, source_overlap_tokens=4,
    )
    resources = load_unieval_resources(settings, REPOSITORY)
    source = "The garden opened on Monday. " * 25
    summary = "The garden opened."
    request = UnievalRequest(source_text=source, summary_text=summary)
    plan = prepare_unieval(request, settings, resources)
    assert {error.code for error in plan.errors} == {
        "COHERENCE_INPUT_TOO_LONG", "CONSISTENCY_INPUT_TOO_LONG",
    }
    assert plan.controls.consistency_source_mode == "full_source_prompt"
    assert plan.controls.source_budget_tokens is None
    assert plan.work.source_spans == (SourceSpan(start=0, end=len(source)),)
    assert plan.work.coherence.planned is None and plan.work.consistency.planned is None
    assert plan.work.fluency.planned == 1 and plan.relevance_skip_reason == "disabled"
    assert [item.dimension for item in plan.comparisons] == ["fluency"]
    assert request.source_text == source and request.summary_text == summary

    windows = prepare_unieval(
        UnievalRequest(
            source_text=source, summary_text=summary, consistency_source_mode="all_source_windows"
        ),
        settings,
        resources,
    )
    assert {error.code for error in windows.errors} == {"COHERENCE_INPUT_TOO_LONG"}
    assert windows.work.coherence.planned is None and windows.work.consistency.planned is not None
    assert len(windows.work.source_spans) > 1
    assert windows.work.source_spans[0].start == 0
    assert windows.work.source_spans[-1].end == len(source)
    assert windows.work.fluency == plan.work.fluency


def test_short_and_unicode_sources_keep_every_original_character() -> None:
    _, settings = unieval_settings(source_window_tokens=24, source_overlap_tokens=4)
    resources = load_unieval_resources(settings, REPOSITORY)
    for source in ("  One fact. \n", " The price is EUR 20. " * 15, "A \U0001f331 grew. " * 20):
        request = UnievalRequest(
            source_text=source,
            summary_text="A plant grew.",
            reference_summary_text="A plant grew.",
            evaluate_relevance=True,
        )
        plan = prepare_unieval(request, settings, resources)
        assert not plan.errors
        assert plan.work.source_spans[0].start == 0
        assert plan.work.source_spans[-1].end == len(source)


def test_oversized_coherence_and_reference_do_not_change_source_or_summary() -> None:
    _, settings = unieval_settings(
        max_input_tokens=80, source_window_tokens=24, source_overlap_tokens=4
    )
    resources = load_unieval_resources(settings, REPOSITORY)
    source = "The garden opened on Monday. " * 25
    reference = "The garden opened. " * 25
    request = UnievalRequest(
        source_text=source, summary_text="The garden opened.", reference_summary_text=reference,
        evaluate_relevance=True,
    )
    plan = prepare_unieval(request, settings, resources)
    assert {error.code for error in plan.errors} == {
        "COHERENCE_INPUT_TOO_LONG",
        "RELEVANCE_INPUT_TOO_LONG",
    }
    assert plan.work.coherence.planned is None and plan.work.relevance.planned is None
    assert plan.work.consistency.planned is not None
    assert all(resources.token_count(item.prompt) <= 80 for item in plan.comparisons)
    assert request.source_text == source and request.reference_summary_text == reference


def test_comparison_limit_refuses_matrix_before_materializing_it() -> None:
    _, settings = unieval_settings(max_comparisons=4)
    resources = load_unieval_resources(settings, REPOSITORY)
    inputs = read_unieval_inputs()
    plan = prepare_unieval(recorded_unieval_request(inputs.cases[0].request), settings, resources)
    assert any(error.code == "COMPARISON_LIMIT_EXCEEDED" for error in plan.errors)
    assert plan.work.consistency.planned is None
    assert len(plan.comparisons) <= settings.scoring.max_comparisons


def test_normalized_character_offsets_refuse_impossible_overlap_only_for_consistency() -> None:
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    resources = load_unieval_resources(settings, REPOSITORY)
    request = UnievalRequest(
        source_text="\ufdfa" * 50,
        summary_text="word " * 4003 + ".",
        reference_summary_text="Words.",
        evaluate_relevance=True,
        consistency_source_mode="all_source_windows",
    )
    plan = prepare_unieval(request, settings, resources)
    assert any(
        error.code == "CONSISTENCY_INPUT_TOO_LONG" and error.dimension == "consistency"
        for error in plan.errors
    )
    assert plan.work.consistency.planned is None
    assert plan.work.fluency.planned == plan.work.relevance.planned == 1
    assert not plan.work.source_spans


def test_normalized_character_boundaries_advance_and_cover_a_viable_source_plan() -> None:
    _, settings = unieval_settings(source_window_tokens=70, source_overlap_tokens=8)
    resources = load_unieval_resources(settings, REPOSITORY)
    request = UnievalRequest(
        source_text="\ufdfa" * 50,
        summary_text="A short claim.",
        reference_summary_text="A short reference.",
        evaluate_relevance=True,
    )
    plan = prepare_unieval(request, settings, resources)
    spans = plan.work.source_spans
    assert len(spans) > 1 and not any(error.dimension == "consistency" for error in plan.errors)
    assert spans[0].start == 0 and spans[-1].end == len(request.source_text)
    for previous, current in zip(spans, spans[1:], strict=False):
        assert previous.start < current.start <= previous.end < current.end
    assert all(
        resources.token_count(comparison.prompt) <= settings.scoring.max_input_tokens
        for comparison in plan.comparisons
    )
