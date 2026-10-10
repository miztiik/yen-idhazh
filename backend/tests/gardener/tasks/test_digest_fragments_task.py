"""Which run blocks does the digest-fragments task take, and what does it never touch?"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Final

import pytest

from idhazh import ledger
from idhazh.contracts.gardener_events import TaskOutcome
from idhazh.contracts.knobs.gardener import DaysWindow
from idhazh.contracts.ledger_name import LedgerName

from ._task import declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "digest-fragments"
TODAY: Final = date(2027, 11, 15)


def a_block(root: Path, day: date, run: str = "1") -> Path:
    tree = ledger.tree_root(root / ledger.STATE_DIRNAME, LedgerName.DIGEST_FRAGMENTS)
    path = tree / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}" / f"{day.isoformat()}-{run}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8", newline="\n")
    return path


def first_kept() -> date:
    window = declared()[NAME].window
    assert isinstance(window, DaysWindow), "the blocks keep a window of whole days"
    return TODAY - timedelta(days=window.value)


def test_every_block_of_a_day_past_the_window_goes_and_the_first_kept_day_stays(
    tmp_path: Path,
) -> None:
    gone = [a_block(tmp_path, first_kept() - timedelta(days=1), run) for run in ("1", "2")]
    kept = a_block(tmp_path, first_kept())
    published = tmp_path / "frontend" / "public" / "digest" / "2020" / "01" / "01" / "digest.json"
    published.parent.mkdir(parents=True)
    published.write_text("{}\n", encoding="utf-8")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert len(outcome.taken) == 2
    assert not any(path.exists() for path in gone)
    assert not gone[0].parent.exists(), "an emptied day folder was left behind"
    assert kept.exists()
    assert published.exists(), "a published day was touched"


def test_a_dry_run_names_every_block_and_leaves_it(tmp_path: Path) -> None:
    old = a_block(tmp_path, first_kept() - timedelta(days=400))

    old_day = old.parent.name
    old_month = old.parent.parent.name
    old_year = old.parent.parent.parent.name
    stamp = f"{old_year}-{old_month}-{old_day}"
    outcome = run_task(
        NAME, tmp_path, today=TODAY, period_range=(stamp, stamp)
    )

    assert outcome.dry_run, "digest-fragments ships in dry run"
    assert outcome.taken == (old.relative_to(tmp_path).as_posix(),)
    assert old.exists()


def test_empty_named_range_and_empty_scheduled_window_have_distinct_outcomes(
    tmp_path: Path,
) -> None:
    named = run_task(
        NAME,
        tmp_path,
        today=TODAY,
        period_range=("2024-08-01", "2024-08-02"),
    )
    scheduled = run_task(NAME, tmp_path, today=TODAY, wake=True)

    assert named.idle_outcome is TaskOutcome.OUTSIDE_RANGE
    assert scheduled.idle_outcome is TaskOutcome.NOT_DUE
