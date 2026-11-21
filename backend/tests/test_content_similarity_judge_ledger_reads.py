"""Do the judge's two new ledgers file through the door and come back through their loaders?

A row is filed under the day its `date` cell names, and a loader hands back the rows of
exactly the days its caller names: oldest day first, both runs of one night, nothing for a
night nobody filed. The rows are the committed fixtures with a date and a run changed, so the
trip is through the real door, the real parquet files and the real contracts.

The review and the collecting job's sparse declaration must agree on which dates to read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from support.ledger import seed_compact_index, seed_compact_period, writer_identity
from support.paths import CONTRACT_FIXTURES_DIR, read_text

from idhazh import config, ledger
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.ledger_reads import (
    load_pair_verdicts,
    load_threshold_history,
    review_days,
)
from idhazh.content_similarity_judge.tenant import TENANT
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_diagnostics import (
    ScoreDriftBaseline,
    ScoreDriftStatus,
    ScorePoolHistogram,
    diagnostic_text,
)
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


def a_night_with_pool(
    row: StorySimilarityThresholdHistoryRow, pool: ScorePoolHistogram
) -> StorySimilarityThresholdHistoryRow:
    cells = row.model_dump()
    cells["version"] = StorySimilarityThresholdHistoryRow.schema_version()
    cells["score_pool_histogram"] = diagnostic_text(pool)
    if any(pool.counts):
        cells.update(
            score_drift_status=ScoreDriftStatus.INSUFFICIENT_BASELINE,
            score_drift_baseline=diagnostic_text(
                ScoreDriftBaseline(sources=(), required_days=1, share_floor=1e-6)
            ),
        )
    else:
        cells["score_drift_status"] = ScoreDriftStatus.EMPTY_POOL
    return StorySimilarityThresholdHistoryRow.model_validate(cells)


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


def test_the_declared_drift_window_uses_the_packed_door_without_a_raw_repair_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    night, actual_day, too_old = "2026-11-30", "2026-11-01", "2026-10-31"
    narrow = review_days(night, config=judge_settings.load())
    # The real tenant config path, not a substitute for the declaration or ledger reader.
    settings_file = tmp_path / "config" / "judges" / "content-similarity-judge.json"
    settings_file.parent.mkdir(parents=True)
    settings = judge_settings.load()
    settings.diagnostics.score_baseline_lookback_days = 29
    settings_file.write_text(settings.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_DIR", tmp_path / "config")
    days = review_days(night, config=judge_settings.load())
    assert days.threshold_history == (actual_day, *narrow.threshold_history)
    assert days.fit_history == narrow.fit_history
    assert days.pair_verdicts == narrow.pair_verdicts

    declared = TENANT.publication_inputs(date=night)
    state = tmp_path / "state"
    packed = a_night(actual_day, "2026-11-02-2")
    old_path = seed_compact_period(
        state, THRESHOLD_HISTORY, StorySimilarityThresholdHistoryRow, Period.DAILY, actual_day,
        [(actual_day, packed.run_id, packed)], producer="stages.review_thresholds",
    )
    index_path = seed_compact_index(
        state, THRESHOLD_HISTORY, Period.DAILY,
        [CompactEntry(covers=actual_day, rows=1, bytes=1)],
    )
    repaired = a_night(actual_day, "2026-11-03-3")
    raw_path = file_through_the_door(state, THRESHOLD_HISTORY, repaired)
    older = file_through_the_door(state, THRESHOLD_HISTORY, a_night(too_old, "2026-11-01-1"))
    assert {old_path, index_path, raw_path.parent} <= {
        tmp_path / path for path in declared
    }
    assert older.parent.relative_to(tmp_path).as_posix() not in declared
    assert load_threshold_history(state, days.fit_history) == []
    assert load_threshold_history(state, days.threshold_history) == [packed]
