"""Which native prompts and complete comparison plan produce each UniEval dimension?"""

from dataclasses import dataclass

from hhem_evaluator.contracts.unieval_contract import DIMENSIONS, Dimension
from hhem_evaluator.contracts.unieval_error import UnievalError, UnievalErrorCode
from hhem_evaluator.contracts.unieval_request import EffectiveUnievalControls, UnievalRequest
from hhem_evaluator.contracts.unieval_result import DimensionWork, SourceSpan, UnievalWork
from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.fail_unieval import UnievalFailure
from hhem_evaluator.load_unieval_resources import UnievalResources
from hhem_evaluator.plan_unieval_windows import plan_unieval_windows


@dataclass(frozen=True)
class UnievalComparison:
    dimension: Dimension
    index: int
    sentence_index: int | None
    source_index: int | None
    template: str
    summary: str
    source: str = ""
    reference: str = ""

    @property
    def prompt(self) -> str:
        return self.template.format(
            summary=self.summary, source=self.source, reference=self.reference
        )


@dataclass(frozen=True)
class UnievalPlan:
    controls: EffectiveUnievalControls
    work: UnievalWork
    comparisons: tuple[UnievalComparison, ...]
    errors: tuple[UnievalError, ...]


def prepare_unieval(
    request: UnievalRequest, settings: UnievalSettings, resources: UnievalResources
) -> UnievalPlan:
    sentences = tuple(resources.sentences.tokenize(request.summary_text))
    if not sentences:
        raise UnievalFailure(UnievalError.from_code("INVALID_REQUEST"))
    controls = settings.scoring.model_copy(
        update={
            "consistency_source_mode": (
                request.consistency_source_mode or settings.scoring.consistency_source_mode
            )
        }
    )
    errors: list[UnievalError] = []
    spans: tuple[SourceSpan, ...] = ()
    budget: int | None = None
    try:
        if controls.consistency_source_mode == "all_source_windows":
            spans, budget = plan_unieval_windows(
                request.source_text, sentences, settings, resources
            )
        else:
            spans = (SourceSpan(start=0, end=len(request.source_text)),)
    except UnievalFailure as failure:
        errors.append(failure.error)
    selected: list[UnievalComparison] = []
    counts: dict[str, DimensionWork] = {}
    source_windows = tuple(request.source_text[span.start : span.end] for span in spans)
    for dimension in DIMENSIONS:
        required_count = (
            len(sentences) * len(spans)
            if dimension == "consistency"
            else len(sentences)
            if dimension == "fluency"
            else 1
        )
        if len(selected) + required_count > controls.max_comparisons:
            errors.append(UnievalError.from_code("COMPARISON_LIMIT_EXCEEDED", dimension))
            counts[dimension] = DimensionWork()
            continue
        inputs: list[tuple[str, str, str, int | None, int | None]] = []
        template = getattr(settings.prompts, dimension)
        if dimension == "fluency":
            inputs = [(sentence, "", "", index, None) for index, sentence in enumerate(sentences)]
        elif dimension == "coherence":
            inputs = [(request.summary_text, request.source_text, "", None, None)]
        elif dimension == "relevance":
            inputs = [(request.summary_text, "", request.reference_summary_text, None, None)]
        elif spans:
            inputs = [
                (
                    sentence,
                    source,
                    "",
                    sentence_index,
                    source_index,
                )
                for sentence_index, sentence in enumerate(sentences)
                for source_index, source in enumerate(source_windows)
            ]
        if not inputs:
            counts[dimension] = DimensionWork()
            continue
        comparisons = [
            UnievalComparison(
                dimension, index, sentence_index, window_index, template, summary, source, reference
            )
            for index, (summary, source, reference, sentence_index, window_index) in enumerate(
                inputs
            )
        ]
        too_long = any(
            resources.token_count(comparison.prompt) > controls.max_input_tokens
            for comparison in comparisons
        )
        if too_long:
            codes: dict[Dimension, UnievalErrorCode] = {
                "fluency": "SUMMARY_SENTENCE_TOO_LONG",
                "coherence": "COHERENCE_INPUT_TOO_LONG",
                "relevance": "RELEVANCE_INPUT_TOO_LONG",
                "consistency": "CONSISTENCY_INPUT_TOO_LONG",
            }
            errors.append(UnievalError.from_code(codes[dimension], dimension))
            counts[dimension] = DimensionWork()
            continue
        counts[dimension] = DimensionWork(planned=len(comparisons))
        selected.extend(comparisons)
    return UnievalPlan(
        EffectiveUnievalControls(**controls.model_dump(), source_budget_tokens=budget),
        UnievalWork.model_validate(
            {
                **counts,
                "summary_sentences": len(sentences),
                "source_characters": len(request.source_text),
                "source_spans": spans,
            }
        ),
        tuple(selected),
        tuple(errors),
    )
