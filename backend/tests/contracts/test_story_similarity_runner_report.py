"""Does a runner's reading survive the trip to the collecting job, and does its funnel close?

Two questions, and they are separate. The reading has to make the trip through the CSV file a
runner ships and back with every cell intact, and the four endings a pair can have must add up
to what the runner was dealt.

What none of this can settle is whether the figures are true. The stage that fills the reading,
`stages.judge_item_pairs`, and the one that sums it, `stages.review_thresholds`, are what prove
the numbers.

Nothing here reads a committed file but the named fixtures, so what this costs does not move as
the archive grows (CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from pydantic import ValidationError
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.contracts.story_similarity_pair_verdict import JUDGE_POLICY_VERSION
from idhazh.contracts.story_similarity_runner_report import StorySimilarityRunnerReport
from idhazh.contracts.story_similarity_threshold_history_row import canary_answers_text

pytestmark = pytest.mark.contract

FIXTURES = CONTRACT_FIXTURES_DIR / "story-similarity-runner-report"

A_NIGHT = "2026-09-19"

#: The four endings a pair the runner was dealt can have. Named here because the
#: test below adds one to each in turn, which is what says every term is in the
#: identity rather than three of them and a spare column.
ENDINGS = ("pairs_valid", "pairs_refused", "pairs_unreadable", "pairs_abandoned")


def a_runner(name: str) -> StorySimilarityRunnerReport:
    """One recorded runner, read inside the test that asks for it."""
    return StorySimilarityRunnerReport.from_json(read_text(FIXTURES / f"{name}.json"))


def test_a_runners_reading_round_trips_through_the_file_it_ships() -> None:
    """Write it, read it back through the contract, get the same reading."""
    row = a_runner("a-runner-that-read-its-pairs")

    document = ledger.render_file(StorySimilarityRunnerReport.csv_columns(), [row.csv_row()])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert len(read_back) == 1
    assert StorySimilarityRunnerReport.from_csv_row(read_back[0]) == row
    assert len(document.splitlines()) == 2, "a cell put a line break in the row"


@pytest.mark.parametrize("ending", ENDINGS)
def test_a_runner_cannot_report_a_funnel_that_does_not_close(ending: str) -> None:
    """The oracle: every pair dealt has exactly one of four endings.

    One more of any ending than the runner was dealt is a reading whose rates would
    be shares of a denominator that means nothing, so the reading is refused rather
    than shipped. Driven once per ending, because a validator that checked three of
    them would pass a test that checked only the fourth.
    """
    payload: dict[str, Any] = a_runner("a-runner-that-read-its-pairs").model_dump(mode="json")

    assert payload["pairs_dealt"] == sum(payload[name] for name in ENDINGS)
    with pytest.raises(ValidationError, match="pairs_dealt"):
        StorySimilarityRunnerReport.model_validate(payload | {ending: payload[ending] + 1})


def test_a_runner_cannot_agree_more_pairs_than_it_found_valid() -> None:
    """A pair agrees only if both of its readings arrived."""
    payload: dict[str, Any] = a_runner("a-runner-that-read-its-pairs").model_dump(mode="json")

    with pytest.raises(ValidationError, match="pairs_agreed"):
        StorySimilarityRunnerReport.model_validate(
            payload | {"pairs_agreed": payload["pairs_valid"] + 1}
        )


def test_a_rate_over_no_pairs_is_empty_rather_than_zero() -> None:
    """Zero reads as a runner that measured everything and found nothing wrong."""
    row = a_runner("a-runner-that-was-dealt-nothing")

    assert row.pairs_dealt == 0
    assert (row.disagreement_rate, row.unclear_rate, row.first_token_margin_median) == (
        None,
        None,
        None,
    )
    assert (row.decode_seconds_total, row.decode_seconds_max, row.judge_model) == (
        None,
        None,
        None,
    )

    cells = row.csv_row()
    assert [cells[name] for name in ("disagreement_rate", "unclear_rate")] == ["", ""]
    assert StorySimilarityRunnerReport.from_csv_row(cells) == row


def test_current_measurements_validate_the_valid_pair_denominator() -> None:
    payload = {
        "date": A_NIGHT, "run_id": f"{A_NIGHT}-1", "work_part_index": 0,
        "pairs_dealt": 4, "pairs_valid": 2, "pairs_agreed": 1,
        "pairs_unreadable": 0, "pairs_refused": 2, "pairs_abandoned": 0,
        "disagreement_rate": 0.5, "unclear_rate": 1.0,
        "judge_policy_version": JUDGE_POLICY_VERSION,
    }
    row = StorySimilarityRunnerReport.model_validate(payload)
    assert StorySimilarityRunnerReport.from_csv_row(row.csv_row()) == row
    for rate in (None, 0.0, 0.25):
        with pytest.raises(ValidationError, match="disagreement_rate"):
            StorySimilarityRunnerReport.model_validate(payload | {"disagreement_rate": rate})
    with pytest.raises(ValidationError, match="unclear_rate"):
        StorySimilarityRunnerReport.model_validate(payload | {"unclear_rate": None})


def test_the_model_column_records_weights_that_are_no_longer_configured_and_refuses_a_path() -> None:
    """Its recorded weights need not still be configured, and the cell stays one slug."""
    payload: dict[str, Any] = a_runner("a-runner-that-read-its-pairs").model_dump(mode="json")
    row = StorySimilarityRunnerReport.model_validate(
        payload | {"judge_model": "a-model-this-repository-does-not-ship"}
    )
    assert row.judge_model == "a-model-this-repository-does-not-ship"
    assert StorySimilarityRunnerReport.from_csv_row(row.csv_row()) == row
    with pytest.raises(ValidationError, match="judge_model"):
        StorySimilarityRunnerReport.model_validate(payload | {"judge_model": "../weights"})


def a_runner_with_known_answers(runner: int = 2) -> StorySimilarityRunnerReport:
    """The recorded runner, having also judged one known-answer pair on `runner`."""
    payload: dict[str, Any] = a_runner("a-runner-that-read-its-pairs").model_dump(mode="json")
    answers = canary_answers_text({"same-1": ["YES", "YES", 0.9810234, 0.993, 812, runner]})
    return StorySimilarityRunnerReport.model_validate(payload | {"canary_answers": answers})


def test_a_runners_known_answers_round_trip_through_the_file_it_ships() -> None:
    """The cell is JSON in a CSV file, so quotes and commas have to survive the trip."""
    row = a_runner_with_known_answers()

    document = ledger.render_file(StorySimilarityRunnerReport.csv_columns(), [row.csv_row()])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert StorySimilarityRunnerReport.from_csv_row(read_back[0]) == row
    assert read_back[0]["canary_answers"] == '{"same-1":["YES","YES",0.9810234,0.993,812,2]}'
    assert len(document.splitlines()) == 2, "a cell put a line break in the row"


def test_a_runner_cannot_claim_a_known_answer_another_runner_gave() -> None:
    """The reading is the only place the answer and the runner that gave it sit together."""
    with pytest.raises(ValidationError, match="same-1 on runner 3, and this reading is runner 2"):
        a_runner_with_known_answers(runner=3)


def test_a_file_without_the_known_answer_column_reads_no_answers() -> None:
    """An optional column the file does not carry is an absent cell, never an answer."""
    row = a_runner("a-runner-that-read-its-pairs")
    cells = {name: cell for name, cell in row.csv_row().items() if name != "canary_answers"}

    assert row.canary_answers is None
    assert StorySimilarityRunnerReport.from_csv_row(cells) == row
