"""Which seen day files does the task take, and does the planner still read every day it wants?

The seen task deletes by the window in `config/gardener/seen.json`, and the
planner reads by `collect.seen_window_days`. These tests hold the two together
on trees built by the ledger's own appender: whatever the task takes, the
planner could no longer see.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import day_partition, ledger
from idhazh.contracts.knobs.gardener import DaysWindow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.seen import SeenRow

from ._task import declared, run_task

pytestmark = pytest.mark.contract

TODAY: Final = date(2026, 8, 30)


def window_days() -> int:
    window = declared()["seen"].window
    assert isinstance(window, DaysWindow), "seen keeps a window of days"
    return window.value


def a_seen_day(root: Path, day: str, rows: int = 1) -> Path:
    """One day of the seen ledger under the checkout `root`, written by the real appender."""
    state = root / ledger.STATE_DIRNAME
    ledger.append_seen(
        state,
        day,
        [
            SeenRow(
                version=SeenRow.schema_version(),
                url_key=hashlib.sha256(f"{day}-{n}".encode()).hexdigest(),
                first_seen_at=f"{day}T06:00:00Z",
                first_seen_run=f"{day}-1",
            )
            for n in range(rows)
        ],
    )
    return ledger.path(state, LedgerName.SEEN, day)


def test_a_seen_day_the_planner_still_reads_is_never_taken(tmp_path: Path) -> None:
    """Every date `load_seen` would open survives, for the window the task ships with."""
    inside = day_partition.days_in_window(TODAY.isoformat(), window_days())
    for day in inside:
        a_seen_day(tmp_path, day)

    outcome = run_task("seen", tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ()
    state = tmp_path / ledger.STATE_DIRNAME
    assert all(ledger.path(state, LedgerName.SEEN, day).exists() for day in inside)


def test_what_the_task_keeps_covers_what_the_reader_opens_at_a_past_anchor(
    tmp_path: Path,
) -> None:
    """The whole safety claim, at the date that would break it.

    A 140-day tree read at an anchor 40 days before its newest file, so every day
    the reader names has a file. Two-sided: every file the reader opens at that
    anchor survives, and every file below the window goes. A task that took
    everything OUTSIDE the window rather than everything BELOW it would eat the
    forty days of live files the next run appends to.
    """
    state = tmp_path / ledger.STATE_DIRNAME
    window = window_days()
    newest = date(2026, 8, 30)
    built = sorted((newest - timedelta(days=offset)).isoformat() for offset in range(140))
    for day in built:
        a_seen_day(tmp_path, day)
    anchor = newest - timedelta(days=40)

    read_at_anchor = day_partition.days_in_window(anchor.isoformat(), window)
    floor = min(read_at_anchor)
    assert built[0] < floor, "the tree has to reach below the window or nothing is taken"
    before = ledger.load_seen(state, today=anchor.isoformat(), within_days=window)
    outcome = run_task("seen", tmp_path, today=anchor, dry_run=False)
    after = ledger.load_seen(state, today=anchor.isoformat(), within_days=window)

    assert all(ledger.path(state, LedgerName.SEEN, day).exists() for day in read_at_anchor)
    newer = [day for day in built if day > anchor.isoformat()]
    assert all(ledger.path(state, LedgerName.SEEN, day).exists() for day in newer)
    below = [day for day in built if day < floor]
    assert sorted(outcome.taken) == [ledger.relpath(LedgerName.SEEN, day) for day in below]
    assert not any(ledger.path(state, LedgerName.SEEN, day).exists() for day in below)
    assert after == before
    assert before, "an empty answer would pass the line above on any tree"


def test_a_seen_day_outside_the_window_goes_and_says_what_it_weighed(tmp_path: Path) -> None:
    """A day no read can reach goes, with the year and month folders it leaves empty."""
    state = tmp_path / ledger.STATE_DIRNAME
    stale = a_seen_day(tmp_path, "2024-01-15", rows=3)
    weight = stale.stat().st_size
    kept = a_seen_day(tmp_path, TODAY.isoformat())
    before = ledger.load_seen(state, today=TODAY.isoformat(), within_days=window_days())

    outcome = run_task("seen", tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ("state/seen/2024/01/15.csv",)
    assert outcome.bytes_freed == weight
    assert not stale.exists()
    assert kept.exists()
    assert not (ledger.tree_root(state, LedgerName.SEEN) / "2024").exists()
    assert ledger.load_seen(state, today=TODAY.isoformat(), within_days=window_days()) == before


def test_a_dry_run_names_the_day_file_and_leaves_it(tmp_path: Path) -> None:
    stale = a_seen_day(tmp_path, "2024-01-15")

    outcome = run_task("seen", tmp_path, today=TODAY)

    assert outcome.dry_run, "seen ships in dry run"
    assert outcome.taken == ("state/seen/2024/01/15.csv",)
    assert stale.exists()


def test_a_day_newer_than_the_date_it_was_handed_is_never_taken(tmp_path: Path) -> None:
    """A wake handed an older day must not delete the file every later plan opens."""
    live = a_seen_day(tmp_path, "2026-08-15")
    stale = a_seen_day(tmp_path, "2024-01-15")

    outcome = run_task("seen", tmp_path, today=date(2026, 1, 5), dry_run=False)

    assert outcome.taken == ("state/seen/2024/01/15.csv",)
    assert live.exists(), "the live day file was taken by a wake given an older date"
    assert not stale.exists()


def test_a_window_that_keeps_for_ever_takes_nothing_and_reads_nothing(tmp_path: Path) -> None:
    a_seen_day(tmp_path, "2024-01-15")

    outcome = run_task("seen", tmp_path, today=TODAY, dry_run=False, window={"unit": "forever"})

    assert (outcome.taken, outcome.seen, outcome.until) == ((), 0, None)
