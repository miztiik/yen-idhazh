"""How is a premise too long for the scorer cut into windows, and which window wins?"""

from __future__ import annotations

import pytest

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.evals.hhem import chunks, dual_score, score_over_chunks

pytestmark = pytest.mark.slow


def test_a_short_premise_is_one_chunk() -> None:
    assert chunks("a b c", size=10, overlap=2) == ["a b c"]


def test_a_long_premise_is_windowed_with_overlap() -> None:
    text = " ".join(str(n) for n in range(1000))
    windows = chunks(text, size=300, overlap=50)
    assert len(windows) > 1
    assert windows[0].split()[-1] in windows[1].split()[:60], "windows overlap"


def test_every_window_is_the_full_window_and_the_last_one_ends_on_the_last_word() -> None:
    """The aggregation is a max, so a short window is a rival with less to work with.

    Until 2026-08-28 the walk stepped past the end and the leftover became the
    final window. That window was short on every premise longer than one window
    - as little as one word, and 370 words on average against 900-word rivals -
    so every long article was graded with at least one draw from a partial
    premise. Counting the windows cannot see this: the count is the same either
    way on most lengths. The window LENGTHS are what say it.
    """
    geometry = EvaluationConfig()
    size, overlap = geometry.chunk_words, geometry.chunk_overlap_words

    for length in range(size + 1, 4001):
        words = [str(n) for n in range(length)]
        windows = [window.split() for window in chunks(" ".join(words), size, overlap)]
        short = [len(window) for window in windows if len(window) != size]
        assert not short, f"premise of {length} words produced windows of {short} words"
        assert windows[-1][-1] == words[-1], (
            f"premise of {length} words: the last window stops at "
            f"{windows[-1][-1]} rather than {words[-1]}"
        )


def test_anchoring_the_last_window_drops_a_window_on_a_long_article() -> None:
    """Correctness is the reason; the saved scorer pass arrived with the bigger cap.

    At the cap of 2500 committed until 2026-08-29, an article stopped at 1,923
    words. There anchoring fixes the runt and changes no count - 3 windows
    before, 3 after - so it bought correctness and no time. At 3,846 words, which
    is what the cap of 5000 now allows, the unanchored walk needed 6 windows with
    the last of them 96 words long, and anchoring covers the same text in 5. That
    is 16.7 percent less scorer work, and the cap move is what turned it from a
    number to quote later into a live saving.
    """
    geometry = EvaluationConfig()
    size, overlap = geometry.chunk_words, geometry.chunk_overlap_words

    at_cap = chunks(" ".join(str(n) for n in range(1923)), size, overlap)
    doubled = chunks(" ".join(str(n) for n in range(3846)), size, overlap)

    assert len(at_cap) == 3, "the old cap cost the same three passes it always did"
    assert len(doubled) == 5, "six before anchoring, five after"


def test_the_best_chunk_wins_not_the_average() -> None:
    """A mean would drive the score down as the article lengthens and invert the flag."""
    scores = iter([0.1, 0.95, 0.2, 0.15])

    class Recorded:
        def score(self, premise: str, hypothesis: str) -> float:
            del premise, hypothesis
            return next(scores)

    text = " ".join(str(n) for n in range(3000))
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
