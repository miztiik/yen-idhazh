"""Are the two roots claimed, built one way, and the only roots the ledger door can write under?

The gardener's `trials` task empties every child of `state/` that no other task
owns and the registry does not claim, so an unclaimed `raw/` or `compact/` would
be read as a trial run's tree and the gardener would delete its own records. And
the four root builders refuse any path whose first folder under the state root
is neither, so a third root is a `ValueError` rather than a convention.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from gardener.tasks._task import committed_folders, declared

from idhazh import ledger
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import runner
from idhazh.ledger import paths

pytestmark = pytest.mark.contract

A_DAY: Final = "2026-09-24"
A_MONTH: Final = "2026-08"
A_FILE: Final = uuid.UUID("01a0d03c-2e00-8461-98e0-a67898e9a802")
WHICH: Final = LedgerName.VISUAL_PRUNES


def test_a_state_tree_holding_only_the_two_roots_leaves_the_trial_task_nothing(
    tmp_path: Path,
) -> None:
    """The oracle: the door's own trees are never strays."""
    state = tmp_path / "state"
    (state / "raw" / WHICH.value / "2026" / "09" / "24").mkdir(parents=True)
    (state / "compact" / WHICH.value / "daily").mkdir(parents=True)
    tasks = declared()

    folders = runner.folders_of("trials", tasks, tmp_path, committed_folders(tmp_path, tasks))

    assert folders.walk == ()


def test_the_two_roots_are_claimed_beside_every_family() -> None:
    claimed = ledger.claimed_roots()

    assert {"raw", "compact"} <= claimed
    assert "trial-runs" not in claimed


def test_each_builder_answers_its_one_shape(tmp_path: Path) -> None:
    state = tmp_path / "state"
    below = {
        "raw": ledger.raw_path(state, WHICH, A_DAY, A_FILE),
        "raw json": ledger.raw_path(state, WHICH, A_DAY, A_FILE, fmt=Format.JSON),
        "daily": ledger.compact_path(state, WHICH, Period.DAILY, A_DAY),
        "monthly": ledger.compact_path(state, WHICH, Period.MONTHLY, A_MONTH),
        "yearly": ledger.compact_path(state, WHICH, Period.YEARLY, A_DAY[:4]),
        "daily index": ledger.compact_index_path(state, WHICH, Period.DAILY),
        "monthly watermark": ledger.watermark_path(state, WHICH, Period.MONTHLY),
    }

    assert {what: built.relative_to(state).as_posix() for what, built in below.items()} == {
        "raw": f"raw/visual-prunes/2026/09/24/{A_FILE}.parquet",
        "raw json": f"raw/visual-prunes/2026/09/24/{A_FILE}.json",
        "daily": "compact/visual-prunes/daily/2026/09/24.parquet",
        "monthly": "compact/visual-prunes/monthly/2026/08.parquet",
        "yearly": "compact/visual-prunes/yearly/2026/2026.parquet",
        "daily index": "compact/visual-prunes/index/daily.json",
        "monthly watermark": "compact/visual-prunes/monthly/watermark.json",
    }


@pytest.mark.parametrize(
    ("period", "covers"),
    [(Period.DAILY, A_DAY), (Period.MONTHLY, A_MONTH), (Period.YEARLY, A_DAY[:4])],
)
def test_no_compact_file_sits_beside_its_periods_watermark(
    period: Period, covers: str, tmp_path: Path
) -> None:
    """The upkeep checkout fetches a watermark with every file beside it, so one there
    would be downloaded on every wake."""
    state = tmp_path / "state"

    assert (
        ledger.compact_path(state, WHICH, period, covers).parent
        != ledger.watermark_path(state, WHICH, period).parent
    )


@pytest.mark.parametrize(
    ("root", "build"),
    [
        ("RAW_DIRNAME", lambda state: ledger.raw_path(state, WHICH, A_DAY, A_FILE)),
        ("COMPACT_DIRNAME", lambda state: ledger.compact_path(state, WHICH, Period.DAILY, A_DAY)),
        ("COMPACT_DIRNAME", lambda state: ledger.compact_index_path(state, WHICH, Period.DAILY)),
        ("COMPACT_DIRNAME", lambda state: ledger.watermark_path(state, WHICH, Period.DAILY)),
    ],
    ids=["raw_path", "compact_path", "compact_index_path", "watermark_path"],
)
def test_a_builder_whose_root_is_neither_raw_nor_compact_is_refused_by_name(
    root: str, build: Callable[[Path], Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The oracle: a builder spelled onto a third root raises, naming the path and the rule."""
    monkeypatch.setattr(paths, root, "segments")

    with pytest.raises(ValueError, match=r"state/segments/.* is outside the two roots"):
        build(tmp_path / "state")


def test_a_path_that_walks_back_out_of_a_root_is_refused(tmp_path: Path) -> None:
    """Checked on the resolved path, so a root's name at the front is not enough."""
    state = tmp_path / "state"

    with pytest.raises(ValueError, match="outside the two roots"):
        paths._under_the_two_roots(state, state / "raw" / ".." / "scores" / "a.parquet")
    with pytest.raises(ValueError, match="outside the two roots"):
        paths._under_the_two_roots(state, tmp_path / "elsewhere" / "raw" / "a.parquet")


def test_a_root_is_resolved_once_but_each_candidate_is_still_checked(tmp_path: Path) -> None:
    state = tmp_path / "state"
    before = paths._resolved_root.cache_info()
    ledger.raw_path(state, WHICH, A_DAY, A_FILE)
    ledger.compact_index_path(state, WHICH, Period.DAILY)
    after = paths._resolved_root.cache_info()
    assert after.misses - before.misses == 1
    assert after.hits - before.hits == 2
    with pytest.raises(ValueError, match="outside the two roots"):
        paths._under_the_two_roots(state, state / "raw" / ".." / "scores" / "a.parquet")


@pytest.mark.parametrize(
    ("period", "covers"),
    [
        (Period.DAILY, A_MONTH),
        (Period.MONTHLY, A_DAY),
        (Period.DAILY, "../../x"),
        (Period.YEARLY, A_MONTH),
        (Period.YEARLY, "../x"),
    ],
)
def test_a_compact_period_handed_the_wrong_shape_is_refused(
    period: Period, covers: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match=f"is not a {period.value} period"):
        ledger.compact_path(tmp_path / "state", WHICH, period, covers)


@pytest.mark.parametrize("date", [A_MONTH, "2026-9-24", "../2026-09-24"])
def test_a_raw_day_that_is_not_a_day_is_refused(date: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="is not a YYYY-MM-DD UTC day"):
        ledger.raw_path(tmp_path / "state", WHICH, date, A_FILE)
