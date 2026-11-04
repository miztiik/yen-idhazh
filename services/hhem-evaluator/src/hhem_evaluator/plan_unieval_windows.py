"""How do tokenizer-sized original source spans cover the entire supplied article?"""

from .contracts.unieval_error import UnievalError
from .contracts.unieval_result import SourceSpan
from .contracts.unieval_settings import UnievalSettings
from .fail_unieval import UnievalFailure
from .load_unieval_resources import UnievalResources


def plan_unieval_windows(
    source: str,
    sentences: tuple[str, ...],
    settings: UnievalSettings,
    resources: UnievalResources,
) -> tuple[tuple[SourceSpan, ...], int]:
    controls = settings.scoring
    template = settings.prompts.consistency
    prefix_size = max(
        resources.token_count(template.format(source="", summary=sentence))
        for sentence in sentences
    )
    budget = min(controls.source_window_tokens, controls.max_input_tokens - prefix_size)
    if budget <= controls.source_overlap_tokens:
        raise UnievalFailure(UnievalError.from_code("SUMMARY_SENTENCE_TOO_LONG", "consistency"))
    offsets = resources.source_offsets(source)
    spans: list[SourceSpan] = []
    start = 0
    while start < len(offsets):
        end = min(start + budget, len(offsets))
        left = 0 if start == 0 else offsets[start][0]
        while end > start:
            right = len(source) if end == len(offsets) else offsets[end][0]
            prompts = (
                template.format(source=source[left:right], summary=sentence)
                for sentence in sentences
            )
            if all(
                resources.token_count(prompt) <= controls.max_input_tokens for prompt in prompts
            ):
                break
            end -= 1
        if end <= start or (end != len(offsets) and end - start <= controls.source_overlap_tokens):
            raise UnievalFailure(
                UnievalError.from_code("CONSISTENCY_INPUT_TOO_LONG", "consistency")
            )
        spans.append(SourceSpan(start=left, end=right))
        if len(spans) > controls.max_source_windows:
            raise UnievalFailure(UnievalError.from_code("WINDOW_LIMIT_EXCEEDED", "consistency"))
        if end == len(offsets):
            break
        start = end - controls.source_overlap_tokens
    return tuple(spans), budget
