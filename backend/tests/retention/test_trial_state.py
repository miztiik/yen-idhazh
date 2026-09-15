"""Does a trial run keep its ledgers out of the published series, and get cleaned up?"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from idhazh import retention
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.contracts.knobs.run import RunConfig
from idhazh.stages.prune_state import _prune_trial_shards

pytestmark = pytest.mark.contract

TRIAL = "trial-runs"


def a_tree(root: Path, *, days: dict[str, list[str]]) -> Path:
    """`state/<trial>/<ledger>/<yyyy>/<mm>/<dd>.csv`, the shape every ledger writes."""
    for ledger_name, dates in days.items():
        for written in dates:
            day = root / TRIAL / ledger_name / written[:4] / written[5:7] / f"{written[8:10]}.csv"
            day.parent.mkdir(parents=True, exist_ok=True)
            day.write_text("version,date\n2026-09-15," + written + "\n", encoding="utf-8")
    return root


def test_a_trial_day_past_the_window_goes_and_a_recent_one_stays(tmp_path: Path) -> None:
    """The window is what the knob says, counted from the day it is handed.

    Ninety days is the artifact retention this project already uses, so a
    trial's rows outlive the run's own artifacts by nothing.
    """
    state = a_tree(
        tmp_path / "state",
        days={"seen": ["2026-01-01", "2026-09-10"], "item-health": ["2026-02-01"]},
    )

    result = retention.prune_trial_state(
        state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert sorted(result.deleted) == [
        "state/trial-runs/item-health/2026/02/01.csv",
        "state/trial-runs/seen/2026/01/01.csv",
    ]
    assert result.kept == 1
    assert (state / TRIAL / "seen" / "2026" / "09" / "10.csv").is_file()


def test_a_dry_run_names_every_file_and_removes_none(tmp_path: Path) -> None:
    """The list is the deliverable. It is what a person reads before switching it on."""
    state = a_tree(tmp_path / "state", days={"seen": ["2026-01-01"]})

    result = retention.prune_trial_state(
        state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90, dry_run=True
    )

    assert result.deleted == ("state/trial-runs/seen/2026/01/01.csv",)
    assert (state / TRIAL / "seen" / "2026" / "01" / "01.csv").is_file()


def test_a_day_dated_ahead_of_today_is_kept(tmp_path: Path) -> None:
    """A run handed an older `--date` must not delete the day the next one appends to.

    The same property `prune_seen` and `prune_traces` hold, restated here
    because this prune walks a tree the others do not.
    """
    state = a_tree(tmp_path / "state", days={"seen": ["2026-12-25"]})

    result = retention.prune_trial_state(
        state, dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert result.deleted == ()
    assert result.kept == 1


def test_a_tree_that_was_never_written_is_not_an_error(tmp_path: Path) -> None:
    """Production is the default, so on nearly every run there is nothing here."""
    result = retention.prune_trial_state(
        tmp_path / "state", dirname=TRIAL, today=date(2026, 9, 15), within_days=90
    )

    assert not result.changed
    assert result.kept == 0


def test_the_prune_does_nothing_when_no_trial_directory_is_named(tmp_path: Path) -> None:
    """The Oracle. A run that names no trial must not walk, delete or log one.

    `trial_state_dirname` defaults to null, which is production, so this is the
    path every scheduled run takes.
    """
    state = a_tree(tmp_path / "state", days={"seen": ["2026-01-01"]})

    assert _prune_trial_shards(state, RunConfig(), RetentionConfig(), date(2026, 9, 15), dry_run=False) == []
    assert _prune_trial_shards(state, None, RetentionConfig(), date(2026, 9, 15), dry_run=False) == []
    assert (state / TRIAL / "seen" / "2026" / "01" / "01.csv").is_file()


def test_a_named_trial_is_pruned_at_the_configured_window(tmp_path: Path) -> None:
    state = a_tree(tmp_path / "state", days={"seen": ["2026-01-01"]})
    run = RunConfig(trial_state_dirname=TRIAL)

    removed = _prune_trial_shards(state, run, RetentionConfig(), date(2026, 9, 15), dry_run=True)

    assert removed == ["state/trial-runs/seen/2026/01/01.csv"]
