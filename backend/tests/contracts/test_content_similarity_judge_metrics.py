"""Does this judge's own reading survive the trip to its ledger, and does its funnel close?

Three questions, and they are separate. The row has to make the trip through
the CSV file a unit ships and back with every cell intact; the four endings a
pair can have must add up to what the shard was dealt; and the ledger door has
to file the row under the judge's own folder, where its reader looks.

What none of this can settle is whether the figures are true. The step that
fills the row, `stages.count_verdicts`, is what proves the numbers.

Nothing here reads a committed file. The ledger is built under `tmp_path`, so
what this costs does not move as the archive grows (CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, SEED_COMMIT, read_text
from pydantic import ValidationError

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.judge_call import JudgeConfigStamp
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain

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
    ledger holds the readings of one judge and no other.
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


def test_a_row_written_before_the_part_was_renamed_reads_its_part_under_the_new_name() -> None:
    """`shard` became `work_part_index`, and a row an earlier run wrote still reads.

    Both sides: a CSV row under the old heading, and a JSON payload carrying the
    old key. The part number moves across unchanged.
    """
    row = a_shard("a-shard-that-read-its-pairs")
    cells = row.csv_row()
    old_cells = {name: cell for name, cell in cells.items() if name != "work_part_index"}
    old_cells["shard"] = cells["work_part_index"]
    payload = row.model_dump(mode="json")
    old_payload = {name: value for name, value in payload.items() if name != "work_part_index"}
    old_payload["shard"] = row.work_part_index

    assert ContentSimilarityJudgeMetrics.from_csv_row(old_cells) == row
    assert ContentSimilarityJudgeMetrics.model_validate(old_payload) == row
    assert "shard" not in ContentSimilarityJudgeMetrics.model_fields


def test_the_door_files_the_ledger_under_the_judges_own_folder() -> None:
    """The ledger keeps its family nest, and moves only under raw and compact."""
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    entry = ledger.entry(which)

    assert entry.grain is Grain.RAW_AND_COMPACT
    assert entry.prefix == ("content-similarity-judge", "metrics")
    assert ledger.raw_root(Path(ledger.STATE_DIRNAME), which).as_posix() == (
        "state/raw/content-similarity-judge/metrics"
    )


def test_the_door_reader_finds_the_day_the_door_filed(tmp_path: Path) -> None:
    """A row filed through the door is read back for its own night and no other."""
    state_root = tmp_path / ledger.STATE_DIRNAME
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    rows = [
        a_shard("a-shard-that-was-dealt-nothing").model_copy(update={"date": night})
        for night in (A_NIGHT, ANOTHER_NIGHT)
    ]
    written = ledger.persist(
        state_root,
        rows,
        ledger=which,
        covers=A_NIGHT,
        identity=WriterIdentity(
            run_id=rows[0].run_id,
            attempt=1,
            job=ServerJob.SAVE_COUNCIL_RESULTS,
            shard=0,
            producer="tests.contracts.test_content_similarity_judge_metrics",
            git_sha=SEED_COMMIT,
        ),
    )

    assert len(written) == 2, "one raw file for each night the rows name"
    assert ledger.load_days(state_root, which, [A_NIGHT], model=ContentSimilarityJudgeMetrics) == [
        rows[0]
    ]
    assert list(ledger.raw_days(state_root, which)) == [A_NIGHT, ANOTHER_NIGHT]
