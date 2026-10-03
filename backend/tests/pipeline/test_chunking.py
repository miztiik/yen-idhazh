"""How is a premise too long for the scorer cut into windows, and which window wins?"""

from __future__ import annotations

import pytest

from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.evals.hhem import chunks, dual_score, score_over_chunks


def test_a_short_premise_is_one_chunk() -> None:
    assert chunks("a b c", size=10, overlap=2) == ["a b c"]


def test_a_long_premise_is_windowed_with_overlap() -> None:
    size, overlap = 300, 50
    text = " ".join(str(n) for n in range(2 * size - overlap))
    windows = chunks(text, size=size, overlap=overlap)
    assert len(windows) > 1
    assert windows[0].split()[-1] in windows[1].split()[:60], "windows overlap"


def test_a_premise_just_over_one_window_keeps_the_last_window_full() -> None:
    """The first length that needs a second window exposes a partial-tail defect."""
    geometry = EvaluationConfig()
    size, overlap = geometry.chunk_words, geometry.chunk_overlap_words

    words = [str(n) for n in range(size + 1)]
    windows = [window.split() for window in chunks(" ".join(words), size, overlap)]

    assert [len(window) for window in windows] == [size, size]
    assert windows[-1][-1] == words[-1]


def test_anchoring_the_last_window_drops_a_window_on_a_long_article() -> None:
    """Five words are enough for the old walk to add a partial third window."""
    words = " ".join(str(n) for n in range(5))
    windows = chunks(words, size=3, overlap=1)

    assert len(windows) == 2
    assert all(len(window.split()) == 3 for window in windows)


def test_the_best_chunk_wins_not_the_average() -> None:
    """A mean would drive the score down as the article lengthens and invert the flag."""
    scores = iter([0.1, 0.95])

    class Recorded:
        def score(self, premise: str, hypothesis: str) -> float:
            del premise, hypothesis
            return next(scores)

    text = " ".join(str(n) for n in range(EvaluationConfig().chunk_words + 1))
    assert score_over_chunks(
        Recorded(), text, "claim", evaluation=EvaluationConfig()
    ) == pytest.approx(0.95)


def test_an_empty_premise_scores_zero_rather_than_raising() -> None:
    class Never:
        def score(self, premise: str, hypothesis: str) -> float:  # pragma: no cover
            raise AssertionError("must not be called")

    assert score_over_chunks(Never(), "", "claim", evaluation=EvaluationConfig()) == 0.0


class _Counting:
    """A scorer that answers deterministically and says how often it was asked."""

    def __init__(self) -> None:
        self.premises: list[str] = []

    def score(self, premise: str, hypothesis: str) -> float:
        del hypothesis
        self.premises.append(premise)
        return 0.5 + 0.1 * len(self.premises)


def test_an_untruncated_article_is_scored_once_and_not_twice() -> None:
    """The scorer is deterministic, so a second pass over one string cannot differ.

    About 97 percent of items are never cut, and one pass over a 900-word chunk
    measured 2.88 to 3.08 s on `ubuntu-latest` (2026-08-26, run `2026-08-26-5`,
    n=5). The pass this skips was roughly 2 s an item, or 21 to 24 minutes of
    runner wall-clock a day at the observed 621 to 731 items.
    """
    scorer = _Counting()
    whole = "The plant will close in March, the ministry said on Tuesday."

    seen, full = dual_score(
        scorer,
        seen_text=whole,
        full_text=whole,
        summary="claim",
        evaluation=EvaluationConfig(),
    )

    assert scorer.premises == [whole], "one identical string, one pass"
    assert seen == full


def test_a_truncated_article_is_scored_against_both_texts() -> None:
    """The short-circuit must not swallow the case the column exists for."""
    scorer = _Counting()
    seen_text = "The plant will close in March."
    whole = f"{seen_text} The ministry named June as the original date."

    seen, full = dual_score(
        scorer,
        seen_text=seen_text,
        full_text=whole,
        summary="claim",
        evaluation=EvaluationConfig(),
    )

    assert scorer.premises == [seen_text, whole], "two different strings, two passes"
    assert seen != full
