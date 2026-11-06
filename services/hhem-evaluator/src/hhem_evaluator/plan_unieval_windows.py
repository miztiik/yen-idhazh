"""How do tokenizer-sized original source spans cover the entire supplied article?"""

from bisect import bisect_right

from hhem_evaluator.contracts.unieval_error import UnievalError
from hhem_evaluator.contracts.unieval_result import SourceSpan
from hhem_evaluator.contracts.unieval_settings import UnievalSettings
from hhem_evaluator.fail_unieval import UnievalFailure
from hhem_evaluator.load_unieval_resources import UnievalResources


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
    boundaries = [
        0,
        *(index for index in range(1, len(offsets)) if offsets[index - 1][0] < offsets[index][0]),
        len(offsets),
    ]
    spans: list[SourceSpan] = []
    start = 0
    while start < len(offsets):
        boundary = bisect_right(boundaries, min(start + budget, len(offsets))) - 1
        end = boundaries[boundary]
        left = 0 if start == 0 else offsets[start][0]
        right = left
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
            boundary -= 1
            end = boundaries[boundary]
        if (
            end <= start
            or right <= left
            or (
                spans
                and (left <= spans[-1].start or left > spans[-1].end or right <= spans[-1].end)
            )
        ):
            raise UnievalFailure(
                UnievalError.from_code("CONSISTENCY_INPUT_TOO_LONG", "consistency")
            )
        spans.append(SourceSpan(start=left, end=right))
        if len(spans) > controls.max_source_windows:
            raise UnievalFailure(UnievalError.from_code("WINDOW_LIMIT_EXCEEDED", "consistency"))
        if right == len(source):
            break
        if end - start <= controls.source_overlap_tokens:
            raise UnievalFailure(
                UnievalError.from_code("CONSISTENCY_INPUT_TOO_LONG", "consistency")
            )
        next_start = boundaries[bisect_right(boundaries, end - controls.source_overlap_tokens) - 1]
        if next_start <= start or next_start > end:
            raise UnievalFailure(
                UnievalError.from_code("CONSISTENCY_INPUT_TOO_LONG", "consistency")
            )
        start = next_start
    return tuple(spans), budget
