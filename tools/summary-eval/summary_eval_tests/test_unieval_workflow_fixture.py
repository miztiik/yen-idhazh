"""Does the named live input exercise complete long-source prompts with the actual tokenizer?"""

import json
from itertools import pairwise

import pytest
from summary_eval_pipeline.contracts import text_sha256
from summary_eval_pipeline.evaluate_pair import require_unieval_work
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import ManualInputs
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.load_unieval_resources import load_unieval_resources
from summary_evaluator.unieval.plan_unieval_windows import plan_unieval_windows
from summary_evaluator_cases.contract_examples import REPOSITORY, example_unieval_result

# The pinned scorer's configurable constructor default, not a model context maximum.
UPSTREAM_PROMPT_CUTOFF = 1024


def test_named_source_alone_exceeds_the_original_coherence_cutoff_and_covers_its_tail() -> None:
    inputs = ManualInputs.model_validate({
        **json.loads((
            REPOSITORY / "tests" / "fixtures" / "unieval-evaluator" / "workflow-inputs.json"
        ).read_bytes()),
        "consistency_source_mode": "all_source_windows",
    })
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    resources = load_unieval_resources(settings, REPOSITORY)
    source_only = resources.token_count(
        settings.prompts.coherence.format(summary="", source=inputs.source_text)
    )
    assert UPSTREAM_PROMPT_CUTOFF < source_only < settings.scoring.max_input_tokens
    spans, budget = plan_unieval_windows(
        inputs.source_text, ("The library opens on 18 March.",), settings, resources
    )
    assert len(spans) > 1 and budget <= settings.scoring.source_window_tokens
    assert spans[0].start == 0 and spans[-1].end == len(inputs.source_text)
    assert all(
        current.start < previous.end
        for previous, current in pairwise(spans)
    )
    assert "Thursday" in inputs.source_text[spans[-1].start : spans[-1].end]
    assert inputs.reference_summary_text is not None and inputs.evaluate_relevance is True
    assert inputs.consistency_source_mode == "all_source_windows"
    assert "Thursday" in inputs.reference_summary_text


def test_native_zero_examples_still_require_the_exact_dimension_work_counts() -> None:
    request = UnievalRequest(
        source_text="S", summary_text="A claim.", reference_summary_text="Independent reference.",
        evaluate_relevance=True,
        consistency_source_mode="all_source_windows",
    )
    api = load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    settings = load_unieval_settings(REPOSITORY, api)
    assert request.reference_summary_text is not None
    result = example_unieval_result(text_sha256(request.reference_summary_text))
    settings = settings.model_copy(update={
        "scoring": settings.scoring.model_copy(
            update={"consistency_source_mode": "all_source_windows"}
        ),
    })
    assert result.effective_settings is not None
    result = UnievalResult.model_validate_json(result.model_copy(update={
        "effective_settings": result.effective_settings.model_copy(
            update={"consistency_source_mode": "all_source_windows"}
        ),
    }).model_dump_json())
    require_unieval_work(result, request, settings, 200)
    for dimension, count in (
        ("fluency", 2),
        ("coherence", 2),
        ("consistency", 2),
        ("relevance", 2),
    ):
        work = getattr(result.work, dimension).model_copy(
            update={"planned": count, "completed": count}
        )
        invalid = UnievalResult.model_validate_json(
            result.model_copy(
                update={"work": result.work.model_copy(update={dimension: work})}
            ).model_dump_json()
        )
        with pytest.raises(WorkflowError):
            require_unieval_work(invalid, request, settings, 200)
