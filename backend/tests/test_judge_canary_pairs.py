"""Do the known-answer pairs reach the night's row as the runners answered them, and nowhere else?

The collecting job's half, built from the rows a night has already read: each runner ships its
answers in its own reading, and the night's row carries them gathered into one text. Every case
goes through the real contracts and the real merge, with the readings built in memory.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from pydantic import TypeAdapter
from support.judged_pairs import CONFIG_VERSIONS, DATE, a_night_of_pairs, a_reading
from support.threshold_nights import LOOKBACK, RULES

from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.story_similarity_threshold_history_row import (
    CanaryAnswersText,
    StorySimilarityThresholdHistoryRow,
    canary_answers_text,
)
from idhazh.similarity.night_totals import merged_canary_answers, runner_columns
from idhazh.stages.review_thresholds import build_threshold_row


def an_answer(runner: int, word: str = "YES") -> list[Any]:
    """One pair's six cells: both orders' answer, both margins, the prompt tokens, the runner."""
    return [word, word, 0.9810234, 0.993, 812, runner]


def a_runner(shard: int, answers: dict[str, list[Any]]) -> ContentSimilarityJudgeMetrics:
    """One runner's reading of its own instrument, having judged the pairs named in `answers`."""
    reading = a_reading(shard=shard, dealt=2, date=DATE, run_id=f"{DATE}-9")
    return ContentSimilarityJudgeMetrics.model_validate(
        reading.model_dump(mode="json") | {"canary_answers": canary_answers_text(answers)}
    )


def test_the_runners_answers_are_gathered_into_the_nights_one_text() -> None:
    """Each pair went to one runner, so the night's text is the union, sorted by pair id."""
    readings = [
        a_runner(2, {"different-1": an_answer(2, "NO")}),
        a_runner(0, {"same-1": an_answer(0), "unclear-1": an_answer(0, "UNCLEAR")}),
        a_runner(1, {}),
    ]

    text = merged_canary_answers(readings)

    assert text is not None
    assert list(json.loads(text)) == ["different-1", "same-1", "unclear-1"]
    assert json.loads(text)["different-1"] == an_answer(2, "NO")
    assert TypeAdapter(CanaryAnswersText).validate_python(text) == text
    assert runner_columns(readings, expected_shards=4)["canary_answers"] == text


def test_no_runner_having_judged_a_pair_leaves_the_text_empty_and_never_an_empty_object() -> None:
    """An empty object would read as pairs that ran and had nothing to say."""
    assert merged_canary_answers([]) is None
    assert merged_canary_answers([a_runner(0, {}), a_runner(1, {})]) is None
    assert canary_answers_text({}) is None


def test_a_pair_two_runners_both_answered_keeps_the_lower_runners_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """It is a fault of the artifacts and not a wrong answer, so the night is not held for it."""
    lower, higher = an_answer(0, "YES"), an_answer(1, "NO")
    readings = [a_runner(1, {"same-1": higher}), a_runner(0, {"same-1": lower})]

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        text = merged_canary_answers(readings)

    assert text is not None
    assert json.loads(text) == {"same-1": lower}
    assert "same-1 was answered by runner 0 and by runner 1" in caplog.text


def test_the_nights_row_carries_the_answers_as_the_runners_gave_them_and_no_count_moves() -> None:
    """The row the night files holds the text, and a pair that is not the night's own adds to no count."""
    rows = a_night_of_pairs([(0.80, "YES"), (0.60, "NO")])
    readings = [
        a_runner(0, {"same-1": an_answer(0)}),
        a_runner(1, {"unclear-1": an_answer(1, "NO")}),
    ]

    row = build_threshold_row(
        DATE,
        run_id=f"{DATE}-9",
        window=rows,
        history=[],
        draw_rows=[],
        readings=readings,
        expected_shards=4,
        rules=RULES,
        lookback_days_of_the_draw=LOOKBACK,
        versions=CONFIG_VERSIONS,
    )

    assert row is not None
    assert row.canary_answers == '{"same-1":["YES","YES",0.9810234,0.993,812,0],' \
        '"unclear-1":["NO","NO",0.9810234,0.993,812,1]}'
    assert (row.runners_reported, row.pairs_dealt) == (2, 4), "only the night's own pairs are counted"
    assert StorySimilarityThresholdHistoryRow.model_validate_json(row.to_json()) == row
