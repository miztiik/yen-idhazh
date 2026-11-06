"""Does the named live input exercise complete long-source prompts with the actual tokenizer?"""

import pytest
from summary_eval_pipeline.contracts import text_sha256
from summary_eval_pipeline.evaluate_pair import require_unieval_work
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.inputs import ManualInputs
from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.contracts.unieval_request import UnievalRequest
from summary_evaluator.unieval.contracts.unieval_result import UnievalResult
from summary_evaluator.unieval.load_unieval_resources import load_unieval_resources
from summary_evaluator.unieval.plan_unieval_windows import plan_unieval_windows
from summary_evaluator_cases.contract_examples import REPOSITORY, example_unieval_result

# The pinned upstream implementation clipped complete prompts at this fixed token count.
UPSTREAM_PROMPT_CUTOFF = 1024


def test_named_source_alone_exceeds_the_original_coherence_cutoff_and_covers_its_tail() -> None:
    inputs = ManualInputs.model_validate_json(
        (
            REPOSITORY / "tests" / "fixtures" / "unieval-evaluator" / "workflow-inputs.json"
        ).read_bytes()
    )
    api = load_api_settings(REPOSITORY / "config" / "summary-evals" / "api.json")
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
        for previous, current in zip(spans[:-1], spans[1:], strict=True)
    )
    assert "Thursday" in inputs.source_text[spans[-1].start : spans[-1].end]
    assert "Thursday" in inputs.reference_summary_text


def test_native_zero_examples_still_require_the_exact_dimension_work_counts() -> None:
    request = UnievalRequest(
        source_text="S", summary_text="A claim.", reference_summary_text="Independent reference."
    )
    result = example_unieval_result(text_sha256(request.reference_summary_text))
    require_unieval_work(result, request, 200)
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
            require_unieval_work(invalid, request, 200)
