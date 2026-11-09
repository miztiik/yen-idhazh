"""Prove real tokenizer windows cover source ends without clipping native prompts."""

import pytest
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


@pytest.mark.parametrize("dimension", ["fluency", "coherence", "consistency", "relevance"])
def test_complete_input_token_boundary_preserves_dimension_index_and_worker_measurement(
    dimension: str,
) -> None:
    from summary_evaluator_cases.contract_examples import EXAMPLE_OPERATION, OPERATION_ID

    from summary_evaluator.shared.exchange_packets import encode_packet
    from summary_evaluator.unieval.contracts.unieval_worker_contract import UNIEVAL_WORKER_VERSION
    from summary_evaluator.unieval.contracts.unieval_worker_message import (
        RequestPacket,
        UnievalCommand,
        UnievalPrediction,
        UnievalReply,
        validate_request_reply,
    )
    from summary_evaluator.unieval.fail_unieval import UnievalFailure
    from summary_evaluator.unieval.load_unieval import CpuUnievalPredictor
    from summary_evaluator.unieval.unieval_worker import score_comparison

    _, settings = unieval_settings(consistency_source_mode="full_source_prompt")
    resources = load_unieval_resources(settings, REPOSITORY)
    request = UnievalRequest(
        source_text="The garden opened on Monday. Many visitors entered.",
        summary_text="It opened. Many visitors entered the garden on Monday.",
        reference_summary_text="The garden opened on Monday.",
        evaluate_relevance=True,
    )
    original = prepare_unieval(request, settings, resources)
    comparison = [item for item in original.comparisons if item.dimension == dimension][-1]
    measured = resources.token_count(comparison.prompt)
    at_limit = settings.model_copy(update={
        "scoring": settings.scoring.model_copy(update={"max_input_tokens": measured}),
    })
    accepted = prepare_unieval(request, at_limit, resources)
    assert comparison in accepted.comparisons
    assert not any(error.dimension == dimension for error in accepted.errors)

    over_limit = at_limit.model_copy(update={
        "scoring": at_limit.scoring.model_copy(update={"max_input_tokens": measured - 1}),
    })
    refused = prepare_unieval(request, over_limit, resources)
    error = next(error for error in refused.errors if error.dimension == dimension)
    assert getattr(error, "input_tokens", None) == measured, (
        "A refused comparison must retain the real complete-input token count."
    )
    assert getattr(error, "allowed_tokens", None) == measured - 1
    assert error.index == comparison.index
    assert getattr(refused.work, dimension).planned is None
    assert not any(item.dimension == dimension for item in refused.comparisons)

    from summary_evaluator.unieval.check_unieval_input_size import check_unieval_input_size

    assert check_unieval_input_size(measured, measured, comparison.dimension) is None
    assert check_unieval_input_size(
        measured, measured - 1, comparison.dimension, comparison.index
    ) == error
    _, _, model_identity = read_unieval_recordings()
    predictor = CpuUnievalPredictor(
        None,
        model_identity,
        resources,
        resources.tokenizer.encode(settings.prompts.positive_answer)[0],
        resources.tokenizer.encode(settings.prompts.negative_answer)[0],
        measured - 1,
    )
    with pytest.raises(UnievalFailure) as failure:
        predictor.score(comparison.prompt)
    assert failure.value.error.code == "MODEL_INPUT_TOO_LONG"
    assert failure.value.error.input_tokens == measured
    assert failure.value.error.allowed_tokens == measured - 1
    identity = RequestPacket(
        version=UNIEVAL_WORKER_VERSION,
        operation_metadata=EXAMPLE_OPERATION,
        execution_id=OPERATION_ID,
        generation=1,
    )
    command = UnievalCommand(**identity.model_dump(), request=request)
    prediction = score_comparison(predictor, comparison, identity)
    encoded = encode_packet(prediction, settings.worker.max_reply_bytes)
    decoded = UnievalReply.model_validate_json(encoded).root
    assert isinstance(decoded, UnievalPrediction)
    validate_request_reply(command, decoded)
    assert decoded == prediction and decoded.error == error and decoded.score is None
    assert decoded.dimension == comparison.dimension and decoded.index == comparison.index
    assert encode_packet(decoded, len(encoded)) == encoded
    with pytest.raises(ValueError, match="byte limit"):
        encode_packet(decoded, len(encoded) - 1)
    print(
        f"TOKEN_BOUNDARY dimension={dimension} index={comparison.index} "
        f"input_tokens={measured} accepted_allowance={measured} "
        f"refused_allowance={measured - 1} code={error.code} "
        f"packet_bytes={len(encoded)} configured_packet_allowance={settings.worker.max_reply_bytes}"
    )


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


@pytest.mark.parametrize("sentence_fits", [False, True])
def test_summary_question_overflow_is_distinct_from_reserved_window_geometry(
    sentence_fits: bool,
) -> None:
    _, settings = unieval_settings(source_window_tokens=24, source_overlap_tokens=4)
    resources = load_unieval_resources(settings, REPOSITORY)
    summary = "A short claim."
    measured = resources.token_count(
        settings.prompts.consistency.format(source="", summary=summary)
    )
    allowance = measured if sentence_fits else measured - 1
    settings = settings.model_copy(update={
        "scoring": settings.scoring.model_copy(update={"max_input_tokens": allowance}),
    })
    request = UnievalRequest(source_text="The source continues.", summary_text=summary)
    plan = prepare_unieval(request, settings, resources)
    failure = next(error for error in plan.errors if error.dimension == "consistency")
    assert plan.work.consistency.planned is None and not plan.work.source_spans
    if sentence_fits:
        assert failure.code == "WINDOW_BUDGET_INSUFFICIENT"
        assert failure.input_tokens is None and failure.allowed_tokens is None
        assert "forward progress" in failure.message and "overlap" in failure.message
    else:
        assert failure.code == "SUMMARY_SENTENCE_TOO_LONG" and failure.index == 0
        assert failure.input_tokens == measured and failure.allowed_tokens == allowance


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
        error.code == "WINDOW_BUDGET_INSUFFICIENT" and error.dimension == "consistency"
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
