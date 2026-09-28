"""When does the feed-health task take a month, and what is never a candidate?"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest
from retention._trees import (
    HISTORY_MONTHS,
    TODAY,
    feed_health_history,
    feed_health_months,
    months_back,
)

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.feed_retirement import FeedRetirementRow, RetirementCause
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.gardener import MonthsWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.retention import oldest_month_kept

from ._task import declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "feed-health"


def window_months() -> int:
    window = declared()[NAME].window
    assert isinstance(window, MonthsWindow), "feed-health keeps a window of months"
    return window.value


def the_file_the_fixture_wrote(day: str) -> str:
    """Where the fixture's one plan job filed its verdicts for `day`, spelled by the grammar."""
    name = ledger.segment_name(run_id=f"{day}-1", attempt=1, job=ServerJob.PLAN, shard=0)
    return f"{ledger.relpath(LedgerName.FEED_HEALTH, day)}/{name}"


def test_the_task_takes_the_expired_day_and_keeps_the_day_beside_it(tmp_path: Path) -> None:
    """Two-sided on purpose: an empty result passes "nothing failed" and prunes nothing."""
    state = tmp_path / ledger.STATE_DIRNAME
    boundary = oldest_month_kept(TODAY, window_months())
    expired_day = f"{months_back(TODAY, window_months() + 1)[0]}-09"
    kept_day = f"{boundary}-09"
    assert expired_day[:7] < boundary <= kept_day[:7], "the fixture must straddle the boundary"
    feed_health_history(state, [expired_day[:7], kept_day[:7]], day_of_month=9)
    expired_path = ledger.path(state, LedgerName.FEED_HEALTH, expired_day)
    kept_path = ledger.path(state, LedgerName.FEED_HEALTH, kept_day)

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert not expired_path.exists(), "the expired day is still there, so nothing was taken"
    assert kept_path.exists(), "the day inside the window was taken"
    assert list(outcome.taken) == [the_file_the_fixture_wrote(expired_day)]
    assert feed_health_months(state) == [kept_day[:7]]
    assert not expired_path.parent.exists()


def test_a_month_past_the_window_is_deleted_rather_than_folded(tmp_path: Path) -> None:
    """Nothing reads a feed's result from past the window, so no summary is written."""
    state = tmp_path / ledger.STATE_DIRNAME
    months = months_back(TODAY, HISTORY_MONTHS)
    feed_health_history(state, months)
    boundary = oldest_month_kept(TODAY, window_months())

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert sorted({path.split("/")[2] + "-" + path.split("/")[3] for path in outcome.taken}) == [
        stem for stem in months if stem < boundary
    ]
    assert outcome.bytes_freed > 0
    assert outcome.written == ()
    assert feed_health_months(state) == [stem for stem in months if stem >= boundary]
    assert not ledger.tree_root(state, LedgerName.ITEM_HEALTH_SUMMARY).exists()


def test_the_retirement_ledger_is_never_a_candidate(tmp_path: Path) -> None:
    """A retirement has no age, and it is filed on the oldest day the history reaches."""
    state = tmp_path / ledger.STATE_DIRNAME
    months = months_back(TODAY, HISTORY_MONTHS)
    feed_health_history(state, months)
    oldest_day = f"{months[0]}-01"
    retired = FeedRetirementRow(
        version=FeedRetirementRow.schema_version(),
        feed_id="trade-press",
        endpoint_key="a" * 64,
        retired_on=oldest_day,
        decided_by_run=f"{oldest_day}-1",
        cause=RetirementCause.HTTP_410,
        evidence_run_ids=(f"{oldest_day}-1",),
    )
    identity = WriterIdentity(
        run_id=f"{oldest_day}-1",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="stages.plan",
        git_sha="a" * 40,
    )
    (written,) = ledger.persist(
        state, [retired], ledger=LedgerName.FEED_RETIREMENTS, covers=oldest_day, identity=identity
    )
    before = written.read_bytes()

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken, "the fixture has to reach past the window or this proves nothing"
    assert written.read_bytes() == before
    assert ledger.load_retirements(state) == [retired]


def test_a_name_the_walk_cannot_place_stops_the_task(tmp_path: Path) -> None:
    """Below a year folder every name is the writer's, so a stray means something else writes."""
    state = tmp_path / ledger.STATE_DIRNAME
    feed_health_history(state, ["2024-01"])
    stray = ledger.tree_root(state, LedgerName.FEED_HEALTH) / "2024-01.csv"
    stray.write_text("header\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not a file inside a YYYY/MM/DD day directory"):
        run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert ledger.path(state, LedgerName.FEED_HEALTH, "2024-01-11").exists()


def test_a_dry_run_names_the_writers_own_file_and_leaves_it(tmp_path: Path) -> None:
    """Never a `<month>-01` the ledger may not hold: the dry list is the live list."""
    state = tmp_path / ledger.STATE_DIRNAME
    feed_health_history(state, ["2024-01", TODAY.strftime("%Y-%m")])

    outcome = run_task(NAME, tmp_path, today=TODAY)

    assert outcome.dry_run, "feed-health ships in dry run"
    assert outcome.taken == (the_file_the_fixture_wrote("2024-01-11"),)
    assert ledger.path(state, LedgerName.FEED_HEALTH, "2024-01-11").exists()


def test_a_wake_handed_an_older_date_keeps_the_live_month(tmp_path: Path) -> None:
    """The boundary is a floor: older than the oldest month kept, never outside the window."""
    state = tmp_path / ledger.STATE_DIRNAME
    feed_health_history(state, ["2024-01", "2026-08"])

    outcome = run_task(NAME, tmp_path, today=date(2026, 1, 5), dry_run=False)

    assert outcome.taken == (the_file_the_fixture_wrote("2024-01-11"),)
    assert ledger.path(state, LedgerName.FEED_HEALTH, "2026-08-11").exists()
    assert not ledger.path(state, LedgerName.FEED_HEALTH, "2024-01-11").exists()


def test_an_empty_state_tree_takes_nothing(tmp_path: Path) -> None:
    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert (outcome.taken, outcome.bytes_freed, outcome.changed) == ((), 0, False)
