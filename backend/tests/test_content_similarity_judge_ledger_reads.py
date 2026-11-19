"""Do the judge's two new ledgers file through the door and come back through their loaders?

A row is filed under the day its `date` cell names, and a loader hands back the rows of
exactly the days its caller names: oldest day first, both runs of one night, nothing for a
night nobody filed. The rows are the committed fixtures with a date and a run changed, so the
trip is through the real door, the real parquet files and the real contracts.

What this cannot settle is whether the council's collecting job will name the right days;
that job does not exist yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from support.ledger import writer_identity
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh import ledger
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_threshold_history,
)
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)

pytestmark = pytest.mark.contract

PAIR_VERDICTS = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
THRESHOLD_HISTORY = LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY

PAIR_FIXTURE = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-pair-verdict"
    / "a-judged-pair-with-its-slice-and-chance.json"
)
NIGHT_FIXTURE = (
    CONTRACT_FIXTURES_DIR
    / "story-similarity-threshold-history-row"
    / "a-night-that-held-both-thresholds.json"
)


def a_verdict(date: str, run_id: str) -> StorySimilarityPairVerdict:
    payload: dict[str, Any] = json.loads(read_text(PAIR_FIXTURE))
    return StorySimilarityPairVerdict.model_validate(payload | {"date": date, "run_id": run_id})


def a_night(date: str, run_id: str) -> StorySimilarityThresholdHistoryRow:
    payload: dict[str, Any] = json.loads(read_text(NIGHT_FIXTURE))
    return StorySimilarityThresholdHistoryRow.model_validate(
        payload | {"date": date, "run_id": run_id}
    )


def file_through_the_door(
    state: Path, which: LedgerName, row: StorySimilarityPairVerdict | StorySimilarityThresholdHistoryRow
) -> Path:
    """File one row the way the council's collecting job does, and say which file it landed in."""
    rows: list[Contract] = [row]
    identity = writer_identity(
        row.run_id,
        job=ServerJob.SAVE_COUNCIL_RESULTS,
        producer="tests.test_content_similarity_judge_ledger_reads",
    )
    written = ledger.persist(state, rows, ledger=which, covers=row.date, identity=identity)
    assert len(written) == 1 and written[0].is_file()
    return written[0]


def test_pair_verdicts_come_back_for_exactly_the_days_named(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    first = a_verdict("2026-11-16", "2026-11-17-100")
    second = a_verdict("2026-11-17", "2026-11-18-200")
    rerun = a_verdict("2026-11-17", "2026-11-18-300")
    for row in (first, second, rerun):
        landed = file_through_the_door(state, PAIR_VERDICTS, row)
        assert landed.parent == ledger.raw_root(state, PAIR_VERDICTS).joinpath(
            *row.date.split("-")
        )

    both_days = load_pair_verdicts(state, ["2026-11-17", "2026-11-16"])

    assert [row.date for row in both_days] == ["2026-11-16", "2026-11-17", "2026-11-17"]
    assert both_days[0] == first
    assert {row.run_id for row in both_days[1:]} == {second.run_id, rerun.run_id}
    assert load_pair_verdicts(state, ["2026-11-16"]) == [first]
    assert load_pair_verdicts(state, ["2026-11-15"]) == []


def test_threshold_rows_come_back_for_exactly_the_days_named(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    night = a_night("2026-11-17", "2026-11-18-200")
    landed = file_through_the_door(state, THRESHOLD_HISTORY, night)
    assert landed.parent == ledger.raw_root(state, THRESHOLD_HISTORY).joinpath(
        *night.date.split("-")
    )

    assert load_threshold_history(state, ["2026-11-17"]) == [night]
    assert load_threshold_history(state, ["2026-11-16", "2026-11-18"]) == []
