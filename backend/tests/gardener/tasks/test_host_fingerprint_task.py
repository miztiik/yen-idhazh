"""Which months of the machines each job ran on does the host-fingerprint task take?

The same shape as the feed-health task: a row is one job's silicon on one run,
the window counts months over a tree filed by day, and a month past the window
goes whole. What is kept is asserted against the window the declaration ships.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from retention._trees import (
    HISTORY_MONTHS,
    TODAY,
    host_fingerprint_history,
    host_fingerprint_months,
    months_back,
)

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.knobs.gardener import MonthsWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.retention import oldest_month_kept

from ._task import declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "host-fingerprint"


def window_months() -> int:
    window = declared()[NAME].window
    assert isinstance(window, MonthsWindow), "host-fingerprint keeps a window of months"
    return window.value


def host_fingerprint_days(state: Path) -> list[Path]:
    """Every host-fingerprint file, oldest first, through the pipeline's own walk."""
    tree = ledger.tree_root(state, LedgerName.HOST_FINGERPRINT)
    return list(day_shards.shard_files(tree, days=UNBOUNDED_WINDOW))


def the_file_the_fixture_wrote(day: str) -> str:
    name = ledger.segment_name(run_id=f"{day}-1", attempt=1, job=ServerJob.PLAN, shard=0)
    return f"{ledger.relpath(LedgerName.HOST_FINGERPRINT, day)}/{name}"


def test_the_task_takes_the_expired_day_and_keeps_the_day_beside_it(tmp_path: Path) -> None:
    """One day inside the window and one outside it - exactly one goes, and it weighed something."""
    state = tmp_path / ledger.STATE_DIRNAME
    boundary = oldest_month_kept(TODAY, window_months())
    expired_day = f"{months_back(TODAY, window_months() + 1)[0]}-09"
    kept_day = f"{boundary}-09"
    assert expired_day[:7] < boundary <= kept_day[:7], "the fixture must straddle the boundary"
    host_fingerprint_history(state, [expired_day[:7], kept_day[:7]], day_of_month=9)
    expired_path = ledger.path(state, LedgerName.HOST_FINGERPRINT, expired_day)
    kept_path = ledger.path(state, LedgerName.HOST_FINGERPRINT, kept_day)

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert not expired_path.exists(), "the expired day is still there, so nothing was taken"
    assert kept_path.exists(), "the day inside the window was taken"
    assert list(outcome.taken) == [the_file_the_fixture_wrote(expired_day)]
    assert host_fingerprint_months(state) == [kept_day[:7]]
    assert outcome.bytes_freed > 0, "a taken day file weighed nothing, so nothing was measured"
    assert not expired_path.parent.exists()


def test_a_dry_run_names_the_same_files_a_live_run_takes(tmp_path: Path) -> None:
    state = tmp_path / ledger.STATE_DIRNAME
    host_fingerprint_history(state, months_back(TODAY, HISTORY_MONTHS))
    before = host_fingerprint_days(state)

    dry = run_task(NAME, tmp_path, today=TODAY)

    assert dry.dry_run, "host-fingerprint ships in dry run"
    assert dry.taken, "the dry run named nothing, so the window never fired"
    assert host_fingerprint_days(state) == before, "a dry run deleted a file"

    live = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert live.taken == dry.taken


def test_a_window_that_keeps_for_ever_takes_nothing(tmp_path: Path) -> None:
    """Never is a window a person chose, and it deletes no month the ledger has written."""
    state = tmp_path / ledger.STATE_DIRNAME
    months = months_back(TODAY, HISTORY_MONTHS)
    host_fingerprint_history(state, months)

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False, window={"unit": "forever"})

    assert not outcome.changed
    assert host_fingerprint_months(state) == months
