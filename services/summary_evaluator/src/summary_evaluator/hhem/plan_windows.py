"""Which exact full-size word ranges cover one source with an anchored final window?"""

from dataclasses import dataclass

from summary_evaluator.hhem.contracts.error_detail import ErrorDetail
from summary_evaluator.hhem.fail_evaluation import EvaluationFailure


@dataclass(frozen=True)
class WordWindow:
    index: int
    start_word: int
    end_word: int
    text: str


def plan_windows(text: str, size: int, overlap: int, max_windows: int) -> tuple[WordWindow, ...]:
    """Refuse an excessive plan before constructing any window strings."""
    if type(size) is not int or type(overlap) is not int or not 0 <= overlap < size:
        raise EvaluationFailure(
            ErrorDetail.from_code("INVALID_REQUEST", "request", field="chunk_overlap_words")
        )
    words = text.split()
    count = len(words)
    if not count:
        raise EvaluationFailure(
            ErrorDetail.from_code("INVALID_REQUEST", "request", field="source_text")
        )
    if count <= size:
        return (WordWindow(0, 0, count, text),)
    step = size - overlap
    last_start = count - size
    regular_count = last_start // step + 1
    planned_count = regular_count + int(last_start % step != 0)
    if planned_count > max_windows:
        raise EvaluationFailure(ErrorDetail.from_code("WINDOW_LIMIT_EXCEEDED", "request"))
    starts = list(range(0, last_start + 1, step))
    if starts[-1] != last_start:
        starts.append(last_start)
    return tuple(
        WordWindow(index, start, start + size, " ".join(words[start : start + size]))
        for index, start in enumerate(starts)
    )
