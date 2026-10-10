"""Does the trials task keep declared case traces out of the published series?

Each trace folder is named by the declaration, so the runner hands it to the
task through the commit's listing - the `_task` helper lists the test tree the
same way.
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
TRIAL: Final = "raw/traces/pipeline-tests/production-settings"
TODAY: Final = date(2026, 9, 15)


def a_tree(root: Path, *, days: dict[str, list[str]]) -> Path:
    """One dated trace shard below its configured trial root."""
    state = root / ledger.STATE_DIRNAME
    for ledger_name, dates in days.items():
        for written in dates:
            day = state / TRIAL / written[:4] / written[5:7] / written[8:10]
            day.mkdir(parents=True, exist_ok=True)
            day.joinpath(f"{ledger_name}.jsonl").write_text("{}\n", encoding="utf-8")
    return state


def a_ledger_day(state: Path, *, written: str) -> Path:
    """One declared ledger's day, filed through the ledger door beside trial traces.

    Its path spells its day under `state/raw/`, outside the folders this task owns.
    """
    seed_item_health(
        state, written, [health_row(day=written, run=1, number=1, stage=ItemStage.PUBLISH)]
    )
    (held,) = ledger.list_raw_files(state, LedgerName.ITEM_HEALTH)
    return held.path


def a_file(root: Path, relative: str) -> Path:
    """One file below the configured trial case root."""
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
        "state/raw/traces/pipeline-tests/production-settings/2026/06/11/item-health.jsonl",
        "state/raw/traces/pipeline-tests/production-settings/2026/06/12/seen.jsonl",
    ]
    assert (state / TRIAL / "2026" / "09" / "10" / "seen.jsonl").is_file()


def test_a_dry_run_names_every_file_and_removes_none(tmp_path: Path) -> None:
    state = a_tree(tmp_path, days={"seen": ["2026-06-12"]})

    outcome = run_task(NAME, tmp_path, today=TODAY)

    assert outcome.dry_run, "trials ships in dry run"
    assert outcome.taken == (
        "state/raw/traces/pipeline-tests/production-settings/2026/06/12/seen.jsonl",
    )
    assert (state / TRIAL / "2026" / "06" / "12" / "seen.jsonl").is_file()


def test_a_day_dated_ahead_of_today_is_kept(tmp_path: Path) -> None:
    a_tree(tmp_path, days={"future": ["2026-12-25"]})

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ()


def test_a_tree_that_was_never_written_is_not_an_error(tmp_path: Path) -> None:
    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert (outcome.taken, outcome.seen) == ((), 0)


def test_a_trace_a_trial_run_really_writes_is_read(tmp_path: Path) -> None:
    """The trace uses the exact dated path a pipeline-test run writes."""
    a_file(tmp_path, "2026/06/12/40000000001-00.jsonl")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == (
        "state/raw/traces/pipeline-tests/production-settings/2026/06/12/40000000001-00.jsonl",
    )


def test_a_c1_case_traces_root_dates_files_below_the_traces_folder(tmp_path: Path) -> None:
    """A date-like case slug is outside the folder the task owns, so it cannot date a file."""
    case = "case-2026-09-10"
    root = tmp_path / ledger.STATE_DIRNAME / "raw" / "traces" / "pipeline-tests" / case
    old = root / "2026" / "06" / "12" / "40000000001-00.jsonl"
    new = root / "2026" / "09" / "10" / "40000000002-00.jsonl"
    old.parent.mkdir(parents=True, exist_ok=True)
    new.parent.mkdir(parents=True, exist_ok=True)
    old.write_text("{}\n", encoding="utf-8")
    new.write_text("{}\n", encoding="utf-8")

    outcome = run_task(
        NAME,
        tmp_path,
        today=TODAY,
        dry_run=False,
        owns=[f"state/raw/traces/pipeline-tests/{case}"],
    )

    assert outcome.taken == (
        f"state/raw/traces/pipeline-tests/{case}/2026/06/12/40000000001-00.jsonl",
    )
    assert new.is_file()


def test_a_file_whose_path_spells_no_day_is_kept_rather_than_refused(tmp_path: Path) -> None:
    """An odd trace path must not cost the whole pass."""
    stray = a_file(tmp_path, "notes.txt")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ()
    assert stray.is_file()


def test_an_emptied_trial_root_is_taken_away_with_its_last_file(tmp_path: Path) -> None:
    """Without this the count of folders under `state/` only ever rises (Guardrail #12)."""
    a_tree(tmp_path, days={"seen": ["2026-06-11"]})

    run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert not (tmp_path / ledger.STATE_DIRNAME / TRIAL).exists()


def test_trial_ledger_files_are_left_to_compaction(tmp_path: Path) -> None:
    """The trace task does not claim raw ledger files, which live under a
    different top-level root (`state/raw/pipeline-tests/...`) entirely."""
    raw = tmp_path / ledger.STATE_DIRNAME / "raw" / "pipeline-tests" / "production-settings" / "item-health" / "2026" / "06" / "11" / "fixture.parquet"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text("{}\n", encoding="utf-8")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == ()
    assert raw.is_file()


def test_a_declared_ledger_is_never_a_trial_tree_however_old_its_rows(tmp_path: Path) -> None:
    """Nothing here names the trial: the trees come off the listing."""
    state = a_tree(tmp_path, days={"seen": ["2026-06-12"]})
    ledger_day = a_ledger_day(state, written="2026-01-01")

    outcome = run_task(NAME, tmp_path, today=TODAY, dry_run=False)

    assert outcome.taken == (
        "state/raw/traces/pipeline-tests/production-settings/2026/06/12/seen.jsonl",
    )
    assert ledger_day.is_file(), "a declared ledger is not a trial trace"


def test_an_unconfigured_state_root_is_not_claimed_by_trials(tmp_path: Path) -> None:
    """The task only owns roots named in its declaration, not new state children."""
    state = tmp_path / ledger.STATE_DIRNAME
    (state / "unconfigured").mkdir(parents=True)
    (state / TRIAL).mkdir(parents=True)
    tasks = declared()

    folders = runner.folders_of(NAME, tasks, tmp_path, committed_folders(tmp_path, tasks))

    assert folders.walk == (f"{ledger.STATE_DIRNAME}/{TRIAL}",)
