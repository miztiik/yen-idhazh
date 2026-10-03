"""Does the trials task keep trial trees out of the published series, and clean them up?

Every tree here is a folder under `state/` that no ledger family claims, so the
runner hands it to the task through the commit's listing - the `_task` helper
lists the tree the test built the same way.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest
from conftest import seed_item_health
from retention._trees import health_row

from idhazh import ledger
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import runner

from ._task import committed_folders, declared, run_task

pytestmark = pytest.mark.contract

NAME: Final = "trials"
TRIAL: Final = "pipeline-tests-production-settings"
TODAY: Final = date(2026, 9, 15)


def a_tree(root: Path, *, days: dict[str, list[str]]) -> Path:
    """One test-run ledger shard below its configured trial root."""
    state = root / ledger.STATE_DIRNAME
    for ledger_name, dates in days.items():
        for written in dates:
            day = (
                state
                / TRIAL
                / ledger_name
                / written[:4]
                / written[5:7]
                / written[8:10]
                / "fixture.csv"
            )
            day.parent.mkdir(parents=True, exist_ok=True)
            day.write_text("version,date\n2026-09-15," + written + "\n", encoding="utf-8")
    return state


def a_ledger_day(state: Path, *, written: str) -> Path:
    """One declared ledger's day, filed through the ledger door beside the trial roots.

    Its path spells its day under `state/raw/`, so a sweep that read that root as
    a trial tree would date the file and take it.
    """
    seed_item_health(
        state, written, [health_row(day=written, run=1, number=1, stage=ItemStage.PUBLISH)]
    )
    (held,) = ledger.list_raw_files(state, LedgerName.ITEM_HEALTH)
    return held.path


def a_file(root: Path, relative: str) -> Path:
    path = root / ledger.STATE_DIRNAME / TRIAL / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")
    return path


def test_a_trial_day_past_the_window_goes_and_a_recent_one_stays(tmp_path: Path) -> None:
    """Ninety days is the artifact retention used everywhere else."""
    state = a_tree(
        tmp_path, days={"seen": ["2026-06-12", "2026-09-10"], "item-health": ["2026-06-11"]}
    )

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert sorted(outcome.taken) == [
        "state/pipeline-tests-production-settings/item-health/2026/06/11/fixture.csv",
        "state/pipeline-tests-production-settings/seen/2026/06/12/fixture.csv",
    ]
    assert (state / TRIAL / "seen" / "2026" / "09" / "10" / "fixture.csv").is_file()


def test_a_dry_run_names_every_file_and_removes_none(tmp_path: Path) -> None:
    state = a_tree(tmp_path, days={"seen": ["2026-06-12"]})

    outcome = run_task(NAME, tmp_path, today=TODAY)

    assert outcome.dry_run, "trials ships in dry run"
    assert outcome.taken == (
        "state/pipeline-tests-production-settings/seen/2026/06/12/fixture.csv",
    )
    assert (state / TRIAL / "seen" / "2026" / "06" / "12" / "fixture.csv").is_file()


def test_a_day_dated_ahead_of_today_is_kept(tmp_path: Path) -> None:
    a_tree(tmp_path, days={"seen": ["2026-12-25"]})

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ()


def test_a_tree_that_was_never_written_is_not_an_error(tmp_path: Path) -> None:
    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert (outcome.taken, outcome.seen) == ((), 0)


def test_the_segments_and_traces_a_trial_run_really_writes_are_read(tmp_path: Path) -> None:
    """A day shard and a trace use the exact paths a pipeline-test run writes."""
    a_file(tmp_path, "feed-health/2026/06/12/40000000001-1-work-00.csv")
    new_segment = a_file(tmp_path, "feed-health/2026/09/10/40000000002-1-work-00.csv")
    a_file(tmp_path, "traces/2026/06/12/40000000001-00.jsonl")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert sorted(outcome.taken) == [
        "state/pipeline-tests-production-settings/feed-health/2026/06/12/40000000001-1-work-00.csv",
        "state/pipeline-tests-production-settings/traces/2026/06/12/40000000001-00.jsonl",
    ]
    assert new_segment.is_file()


def test_a_file_whose_path_spells_no_day_is_kept_rather_than_refused(tmp_path: Path) -> None:
    """Nothing reads a trial tree, so an odd name must not cost the whole pass."""
    stray = a_file(tmp_path, "feed-health/notes.txt")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ()
    assert stray.is_file()


def test_an_emptied_trial_root_is_taken_away_with_its_last_file(tmp_path: Path) -> None:
    """Without this the count of folders under `state/` only ever rises (Guardrail #12)."""
    state = a_tree(tmp_path, days={"seen": ["2026-06-11"]})
    before = len(list(state.iterdir()))

    run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert not (state / TRIAL).exists()
    assert len(list(state.iterdir())) == before - 1


def test_a_month_head_is_kept_until_its_whole_month_has_aged_out(tmp_path: Path) -> None:
    """A month has no day of its own, so it takes the last day it could hold."""
    a_file(tmp_path, "candidate-models/2026-06.csv")

    inside = run_task(
        NAME, tmp_path, today=TODAY, dry_run=True, period_range=("2026-06", "2026-06")
    )
    outside = run_task(
        NAME,
        tmp_path,
        today=date(2026, 9, 30),
        dry_run=True,
        period_range=("2026-06", "2026-06"),
    )

    assert inside.taken == ()
    assert outside.taken == (
        "state/pipeline-tests-production-settings/candidate-models/2026-06.csv",
    )


def test_a_declared_ledger_is_never_a_trial_tree_however_old_its_rows(tmp_path: Path) -> None:
    """Nothing here names the trial: the trees come off the listing."""
    state = a_tree(tmp_path, days={"seen": ["2026-06-12"]})
    ledger_day = a_ledger_day(state, written="2026-01-01")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == (
        "state/pipeline-tests-production-settings/seen/2026/06/12/fixture.csv",
    )
    assert ledger_day.is_file(), "a declared ledger is not a trial tree, however old its rows"


def test_an_unconfigured_state_root_is_not_claimed_by_trials(tmp_path: Path) -> None:
    """The task only owns roots named in its declaration, not new state children."""
    state = tmp_path / ledger.STATE_DIRNAME
    (state / "unconfigured").mkdir(parents=True)
    (state / TRIAL).mkdir()
    tasks = declared()

    folders = runner.folders_of(NAME, tasks, tmp_path, committed_folders(tmp_path, tasks))

    assert folders.walk == (f"{ledger.STATE_DIRNAME}/{TRIAL}",)
