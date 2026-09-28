"""Which counterfactual score files does the task take, and which does the tuning still read?"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.ledger_name import LedgerName

from ._task import run_task

pytestmark = pytest.mark.contract

TODAY: Final = date(2026, 8, 30)


def a_counterfactual_day(root: Path, day: str, rows: int = 1) -> Path:
    """One day of the ledger under the checkout `root`, written by the real producer."""
    state = root / ledger.STATE_DIRNAME
    ledger.write_segment(
        state,
        LedgerName.COUNTERFACTUAL_SCORES,
        [
            CounterfactualScoreRow(
                version=CounterfactualScoreRow.schema_version(),
                date=day,
                run_id=f"{day}-1",
                vertical="ai",
                url_key=hashlib.sha256(f"{day}-{n}".encode()).hexdigest(),
                taken=n == 0,
                lens_id="chips",
                lens_bonus=0.3,
                lens_multiplier=1.25,
                score_committed=1.2,
                score_counterfactual=1.275,
            )
            for n in range(rows)
        ],
        run_id=f"{day}-1",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
    )
    return ledger.path(state, LedgerName.COUNTERFACTUAL_SCORES, day)


def the_file(day: str) -> str:
    """What the writer above named its file, spelled by the producer's own helper."""
    return ledger.day_shard_relpath(
        LedgerName.COUNTERFACTUAL_SCORES,
        date=day,
        run_id=f"{day}-1",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
    )


def test_a_day_outside_the_window_goes_and_says_what_it_weighed(tmp_path: Path) -> None:
    """The ledger grows every run, so without this it has no ceiling at all."""
    stale = a_counterfactual_day(tmp_path, "2024-01-15", rows=3)
    weight = sum(path.stat().st_size for path in stale.iterdir())
    kept = a_counterfactual_day(tmp_path, TODAY.isoformat())

    outcome = run_task("counterfactual-scores", tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == (the_file("2024-01-15"),)
    assert outcome.bytes_freed == weight
    assert not stale.exists()
    assert kept.exists()
    state = tmp_path / ledger.STATE_DIRNAME
    assert not (ledger.tree_root(state, LedgerName.COUNTERFACTUAL_SCORES) / "2024").exists()


def test_a_dry_run_names_the_file_and_leaves_it(tmp_path: Path) -> None:
    stale = a_counterfactual_day(tmp_path, "2024-01-15")

    outcome = run_task("counterfactual-scores", tmp_path, today=TODAY)

    assert outcome.dry_run, "counterfactual-scores ships in dry run"
    assert outcome.taken == (the_file("2024-01-15"),)
    assert stale.exists()


def test_a_day_newer_than_the_date_it_was_handed_is_never_taken(tmp_path: Path) -> None:
    """The boundary is the window's OLDEST day, never its edges.

    A wake handed a date a month back computes a window around that date, and
    the day on disk is newer than every day it names. It still stays.
    """
    day = a_counterfactual_day(tmp_path, TODAY.isoformat())

    outcome = run_task(
        "counterfactual-scores",
        tmp_path,
        today=TODAY - timedelta(days=30),
        dry_run=False,
        window={"unit": "days", "value": 7},
    )

    assert outcome.taken == ()
    assert day.exists()
