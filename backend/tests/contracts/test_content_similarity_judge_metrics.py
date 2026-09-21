"""Does this judge's own reading survive a day file, and does its funnel close?

Three questions, and they are separate. The row has to make the trip to a CSV day
file and back with every cell intact; the four endings a pair can have must add
up to what the shard was dealt; and the day file has to sit where the
instrument's own reader looks - a store one directory too deep is invisible to
that reader and the miss is silent.

What none of this can settle is whether the figures are true. Nothing writes this
row yet; the step that fills it is what proves the numbers.

Nothing here reads a committed file. The day tree is built under `tmp_path`, so
what this costs does not move as the archive grows (CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import day_partition, ledger
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.judge_call import JudgeConfigStamp
from idhazh.telemetry import inventory

pytestmark = pytest.mark.contract

FIXTURES = CONTRACT_FIXTURES_DIR / "content-similarity-judge-metrics"

#: The night these tests are drawn on, and a date in another month so the
#: directory arithmetic has two answers to disagree about.
A_NIGHT = "2026-09-19"
ANOTHER_NIGHT = "2026-10-01"

#: The four endings a pair the shard was dealt can have. Named here because the
#: test below adds one to each in turn, which is what says every term is in the
#: identity rather than three of them and a spare column.
ENDINGS = ("pairs_read", "pairs_refused", "pairs_unreadable", "pairs_abandoned")


def a_shard(name: str) -> ContentSimilarityJudgeMetrics:
    """One recorded shard, read inside the test that asks for it."""
    return ContentSimilarityJudgeMetrics.from_json(read_text(FIXTURES / f"{name}.json"))


def test_a_shards_reading_round_trips_through_a_day_file() -> None:
    """Write it, read it back through the contract, get the same row."""
    row = a_shard("a-shard-that-read-its-pairs")

    document = ledger.render_file(ContentSimilarityJudgeMetrics.csv_columns(), [row.csv_row()])
    read_back = list(csv.DictReader(io.StringIO(document)))

    assert len(read_back) == 1
    assert ContentSimilarityJudgeMetrics.from_csv_row(read_back[0]) == row
    assert len(document.splitlines()) == 2, "a cell put a line break in the row"


@pytest.mark.parametrize("ending", ENDINGS)
def test_a_shard_cannot_file_a_funnel_that_does_not_close(ending: str) -> None:
    """The oracle: every pair dealt has exactly one of four endings.

    One more of any ending than the shard was dealt is a row whose rates would be
    shares of a denominator that means nothing, so the row is refused rather than
    filed. Driven once per ending, because a validator that checked three of them
    would pass a test that checked only the fourth.
    """
    payload: dict[str, Any] = a_shard("a-shard-that-read-its-pairs").model_dump(mode="json")

    assert payload["pairs_dealt"] == sum(payload[name] for name in ENDINGS)
    with pytest.raises(ValidationError, match="pairs_dealt"):
        ContentSimilarityJudgeMetrics.model_validate(payload | {ending: payload[ending] + 1})


def test_a_shard_cannot_agree_more_pairs_than_it_read() -> None:
    """A pair agrees only if both of its readings arrived."""
    payload: dict[str, Any] = a_shard("a-shard-that-read-its-pairs").model_dump(mode="json")

    with pytest.raises(ValidationError, match="pairs_agreed"):
        ContentSimilarityJudgeMetrics.model_validate(
            payload | {"pairs_agreed": payload["pairs_read"] + 1}
        )


def test_a_rate_over_no_pairs_is_empty_rather_than_zero() -> None:
    """Zero reads as a shard that measured everything and found nothing wrong."""
    row = a_shard("a-shard-that-was-dealt-nothing")

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
    assert ContentSimilarityJudgeMetrics.from_csv_row(cells) == row


def test_the_shared_stamp_is_carried_and_narrowed_to_this_judge() -> None:
    """The config stamp arrives whole, and both open columns close here.

    A closed set is honest on this row in the way it cannot be on the shared
    stamp: that stamp is inherited by judges nobody has written yet, and this
    store holds the readings of one judge and no other.
    """
    columns = ContentSimilarityJudgeMetrics.csv_columns()
    assert set(JudgeConfigStamp.model_fields) <= set(columns), (
        "the shard row stopped carrying the shared stamp, so two judges are free to "
        "spell the same reading two ways"
    )

    payload: dict[str, Any] = a_shard("a-shard-that-read-its-pairs").model_dump(mode="json")
    assert ContentSimilarityJudgeMetrics.model_validate(
        {name: value for name, value in payload.items() if name != "judge_id"}
    ).judge_id == "content-similarity-judge"
    with pytest.raises(ValidationError, match="judge_id"):
        ContentSimilarityJudgeMetrics.model_validate(payload | {"judge_id": "another-judge"})
    with pytest.raises(ValidationError, match="judge_model"):
        ContentSimilarityJudgeMetrics.model_validate(
            payload | {"judge_model": "a-model-this-repository-does-not-ship"}
        )


def test_the_day_file_a_date_resolves_to_is_two_levels_under_state() -> None:
    """A third level is invisible to the day inventory and the miss is silent."""
    relpath = ledger.content_similarity_judge_metrics_relpath(A_NIGHT)

    assert relpath == "state/content-similarity-judge/metrics/2026/09/19.csv"
    assert (
        ledger.content_similarity_judge_metrics_path(Path("state"), A_NIGHT).as_posix() == relpath
    )

    segments = relpath.removeprefix(f"{ledger.STATE_DIRNAME}/").split("/")
    assert segments[:2] == [
        ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME,
        ledger.JUDGE_METRICS_DIRNAME,
    ]
    assert segments[2:] == ["2026", "09", "19.csv"], "the day tree gained a directory level"


def test_the_instrument_reader_finds_the_day_this_store_wrote(tmp_path: Path) -> None:
    """A store this row creates is visible rather than silently absent.

    The inventory globs one directory level and two, so a nested store is found
    and a store nested deeper would not be. Asked through the public report,
    because that is what an operator reads.
    """
    state_root = tmp_path / ledger.STATE_DIRNAME
    for night in (A_NIGHT, ANOTHER_NIGHT):
        path = ledger.content_similarity_judge_metrics_path(state_root, night)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            ledger.render_file(
                ContentSimilarityJudgeMetrics.csv_columns(),
                [a_shard("a-shard-that-was-dealt-nothing").csv_row()],
            ),
            encoding="utf-8",
            newline="",
        )

    report = inventory.files(state_root, date=A_NIGHT)

    assert any(
        "content-similarity-judge/metrics/2026/09/19.csv" in line for line in report
    ), report
    assert not any(ANOTHER_NIGHT.replace("-", "/") in line for line in report), (
        "the inventory reported a day it was not asked about"
    )

    root = state_root / ledger.CONTENT_SIMILARITY_JUDGE_DIRNAME / ledger.JUDGE_METRICS_DIRNAME
    assert [day_partition.date_of(found) for found in day_partition.day_files(root)] == [
        A_NIGHT,
        ANOTHER_NIGHT,
    ]
