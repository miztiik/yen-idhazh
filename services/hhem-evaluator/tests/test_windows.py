"""Prove exact anchored geometry and refusal instead of silent window loss."""

import pytest

from hhem_evaluator.fail_evaluation import EvaluationFailure
from hhem_evaluator.plan_windows import plan_windows


@pytest.mark.parametrize(
    ("count", "size", "overlap", "ranges"),
    [
        (3, 5, 1, [(0, 3)]),
        (5, 5, 1, [(0, 5)]),
        (9, 5, 1, [(0, 5), (4, 9)]),
        (10, 5, 1, [(0, 5), (4, 9), (5, 10)]),
        (13, 5, 1, [(0, 5), (4, 9), (8, 13)]),
        (2000, 1500, 900, [(0, 1500), (500, 2000)]),
        (2100, 1500, 900, [(0, 1500), (600, 2100)]),
    ],
)
def test_full_windows_match_regular_steps_and_one_anchored_tail(
    count: int, size: int, overlap: int, ranges: list[tuple[int, int]]
) -> None:
    words = [f"word{index}" for index in range(count)]
    source = " \t".join(words)
    windows = plan_windows(source, size, overlap, 256)
    assert [(window.start_word, window.end_word) for window in windows] == ranges
    assert [window.index for window in windows] == list(range(len(ranges)))
    assert [window.text.split() for window in windows] == [
        words[start:end] for start, end in ranges
    ]
    if count <= size:
        assert windows[0].text == source
    else:
        assert all(len(window.text.split()) == size for window in windows)


@pytest.mark.parametrize("source", ["", " \t\n"])
def test_empty_source_is_refused_not_scored_as_zero(source: str) -> None:
    with pytest.raises(EvaluationFailure) as failure:
        plan_windows(source, 900, 100, 256)
    assert failure.value.error.code == "INVALID_REQUEST"


def test_excessive_plan_is_refused_and_the_exact_boundary_is_scored_in_full() -> None:
    source = " ".join(f"word{index}" for index in range(10))
    with pytest.raises(EvaluationFailure) as failure:
        plan_windows(source, 5, 4, 5)
    assert failure.value.error.code == "WINDOW_LIMIT_EXCEEDED"
    assert len(plan_windows(source, 5, 4, 6)) == 6


@pytest.mark.parametrize(("size", "overlap"), [(0, 0), (5, -1), (5, 5), (5, 6)])
def test_invalid_resolved_pairs_do_not_clamp_the_step(size: int, overlap: int) -> None:
    with pytest.raises(EvaluationFailure):
        plan_windows("one two three", size, overlap, 256)
