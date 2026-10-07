"""Does a shard run every task, hold each to what it owns, and land exactly one record?

End to end, with nothing standing in: fixture declarations loaded through the
real loader, real task modules from `tests/fixtures/gardener/task_packages/`,
real day files in a real clone, and a bare repository standing in for origin.
What reaches origin is read back from origin, so a record that was written and
never pushed, or a file deleted and never staged, fails here. A shard that lands
runs the way a wake runs it, through `backend/utilities/gardener_publish.py`.

The clock is handed in rather than read, so every instant on a record is one
written out below, in UTC.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.gardener import runner
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Outcome
from utilities import gardener_publish

from ._garden import (
    GARDENER_FIXTURES,
    a_config,
    an_origin,
    commits_on,
    git,
    on_origin,
    quiet_git,
    write,
)
from ._garden import task_package as a_package

WAKE = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID = "2026-09-27-18012345678"
#: A day the three-day window has aged out, and one it has not.
AGED, FRESH = "2026/09/19/2026-09-19.txt", "2026/09/26/2026-09-26.txt"

DECLARATIONS = {
    "runner": ("compact-gardener.json", "old-days.json", "rehearsal.json"),
    "breaks": ("broken.json", "defect.json", "old-days.json"),
    "wander": ("wanderer.json",),
    "report": ("astray.json", "late.json", "reporter.json"),
}


def a_garden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: str, files: dict[str, str]
) -> tuple[Path, Path, GardenerSettings]:
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, files)
    declarations = (GARDENER_FIXTURES / fixture / name for name in DECLARATIONS[fixture])
    return origin, checkout, config.load_gardener(a_config(checkout, *declarations))


def ran(
    names: tuple[str, ...],
    settings: GardenerSettings,
    checkout: Path,
    package: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    land: bool = True,
) -> tuple[Outcome, list[str]]:
    """One shard run, landed the way a wake lands it, or run alone and left in the checkout."""
    said: list[str] = []
    tasks = a_package(package, monkeypatch)
    if land:
        outcome = gardener_publish.run_and_land(
            names,
            settings=settings,
            repo_root=checkout,
            run_id=RUN_ID,
            attempt=1,
            shard=0,
            package=tasks,
            clock=lambda: WAKE,
            say=said.append,
        )
    else:
        outcome = runner.run(
            names,
            settings=settings,
            repo_root=checkout,
            run_id=RUN_ID,
            attempt=1,
            shard=0,
            git_sha=git(checkout, "rev-parse", "HEAD").strip(),
            committed_folders=None,
            cone_bytes=None,
            listing=None,
            package=tasks,
            clock=lambda: WAKE,
            say=said.append,
        )
    return outcome, said


def rows_of(record: Path | None) -> dict[str, CollectionPruneRow]:
    assert record is not None, "the shard wrote no record"
    return {row.task: row for row in ledger.load([record], model=CollectionPruneRow)}


RUNNER_FILES = {
    f"state/old-days/{AGED}": "aged\n",
    f"state/old-days/{FRESH}": "fresh\n",
    f"state/rehearsal/{AGED}": "aged\n",
    "state/compact/gardener/monthly/2025/08.parquet": "compacted\n",
}


def test_a_shard_runs_its_tasks_writes_one_record_and_lands_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)
    names = ("compact-gardener", "old-days", "rehearsal")

    outcome, _ = ran(names, settings, checkout, "garden_tasks_ok", monkeypatch)

    assert outcome.exit_code == EXIT_OK
    assert on_origin(origin, f"state/old-days/{AGED}") is None, "the live task deleted nothing"
    assert on_origin(origin, f"state/old-days/{FRESH}") == "fresh\n"
    assert on_origin(origin, f"state/rehearsal/{AGED}") == "aged\n", "a dry run deleted a file"
    assert on_origin(origin, "state/compact/gardener/2026-09-27.summary") is not None
    assert outcome.record is not None
    assert outcome.record.parent == checkout.joinpath(
        "state", "raw", "gardener", "2026", "09", "27"
    )
    recorded = outcome.record.relative_to(checkout).as_posix()
    assert on_origin(origin, recorded) is not None, "the record was written and never landed"
    assert commits_on(origin)[0].endswith(f": gardener: {', '.join(names)} on 2026-09-27")

    rows = rows_of(outcome.record)
    assert set(rows) == set(names)
    assert (rows["old-days"].deleted, rows["old-days"].dry_run) == (1, False)
    assert (rows["rehearsal"].deleted, rows["rehearsal"].dry_run) == (1, True)
    assert all(row.job is ServerJob.RUN_TASKS for row in rows.values())
    assert {(row.run_id, row.attempt, row.shard) for row in rows.values()} == {(RUN_ID, 1, 0)}
    assert {row.work_ended_at for row in rows.values()} == {"2026-09-27T00:40:00Z"}


def test_the_runner_writes_the_record_and_hands_back_what_to_land_without_pushing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Landing resets the checkout and pushes to main, so it is never the runner's to do."""
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)
    before = commits_on(origin)

    outcome, _ = ran(("old-days",), settings, checkout, "garden_tasks_ok", monkeypatch, land=False)

    assert outcome.exit_code == EXIT_OK
    assert outcome.record is not None and outcome.record.is_file()
    assert commits_on(origin) == before, "the runner pushed"
    assert outcome.landing is not None
    assert outcome.landing.record_path == outcome.record.relative_to(checkout).as_posix()
    assert outcome.landing.deleted_paths == {f"state/old-days/{AGED}"}
    assert outcome.landing.message == "gardener: old-days on 2026-09-27"


def test_a_task_whose_service_is_down_is_deferred_and_the_shard_stays_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ORACLE for an outage at the shard: its only non-green task is deferred, so it exits 0.

    The listing service did not answer, which is a cause outside the code: the
    row says `deferred` and why, the sibling still runs and lands, and nothing
    asks a person for work.
    """
    files = {f"state/old-days/{AGED}": "aged\n", "state/broken/.keep": ""}
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "breaks", files)

    outcome, said = ran(
        ("broken", "old-days"), settings, checkout, "garden_tasks_breaks", monkeypatch
    )

    assert outcome.exit_code == EXIT_OK, said
    rows = rows_of(outcome.record)
    assert (rows["broken"].stopped_because, rows["broken"].fault) == (
        StopReason.DEFERRED,
        GardenerFault.API_UNAVAILABLE,
    )
    assert (rows["broken"].deleted, rows["broken"].resume_from) == (0, None)
    assert rows["old-days"].stopped_because is StopReason.EXHAUSTED
    assert on_origin(origin, f"state/old-days/{AGED}") is None, "the sibling did not land"


def test_a_task_whose_code_is_wrong_fails_and_its_sibling_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A code defect is the one stop that turns the shard red, and it still lands its record."""
    files = {f"state/old-days/{AGED}": "aged\n", "state/defect/.keep": ""}
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "breaks", files)

    outcome, _ = ran(("defect", "old-days"), settings, checkout, "garden_tasks_breaks", monkeypatch)

    assert outcome.exit_code == EXIT_TASK_FAILED
    rows = rows_of(outcome.record)
    assert (rows["defect"].stopped_because, rows["defect"].fault) == (
        StopReason.FAILED,
        GardenerFault.RAISED,
    )
    assert (rows["defect"].deleted, rows["defect"].resume_from) == (0, None)
    assert rows["old-days"].stopped_because is StopReason.EXHAUSTED
    assert on_origin(origin, f"state/old-days/{AGED}") is None, "the sibling did not land"


def test_a_task_that_reaches_outside_what_it_owns_stops_the_shard_before_anything_stages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checked on a dry run too: the check is over what was selected, not what was deleted."""
    files = {f"state/mine/{AGED}": "mine\n", f"state/neighbour/{AGED}": "theirs\n"}
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "wander", files)
    before = commits_on(origin)

    outcome, said = ran(("wanderer",), settings, checkout, "garden_tasks_wander", monkeypatch)

    assert outcome.exit_code == EXIT_INTEGRITY
    assert outcome.record is None, "a record was written for a shard that broke ownership"
    assert any(f"touched state/neighbour/{AGED}" in line for line in said)
    assert commits_on(origin) == before
    assert git(checkout, "status", "--porcelain", "--", "state") == ""


#: One folder for each fixture task that files a report, so each owns something.
REPORT_FILES = {"state/reporter/.keep": "", "state/astray/.keep": "", "state/late/.keep": ""}

#: Where a report filed on the wake's day sits, up to the name the ledger door mints.
TODAY_S_REPORTS = "state/raw/visual-prunes/2026/09/27/"


def test_a_report_filed_into_a_ledger_the_task_appends_to_lands_on_a_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A report is what a dry run is for, so it lands while every deletion is held back."""
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "report", REPORT_FILES)
    assert settings.tasks["reporter"].dry_run

    outcome, _ = ran(("reporter",), settings, checkout, "garden_tasks_report", monkeypatch)

    assert outcome.exit_code == EXIT_OK
    assert outcome.landing is not None
    reports = sorted(
        path for path in outcome.landing.written_paths if path.startswith(TODAY_S_REPORTS)
    )
    assert len(reports) == 1, outcome.landing.written_paths
    assert on_origin(origin, reports[0]) is not None, "the report was filed and never landed"


@pytest.mark.parametrize("name", ["astray", "late"])
def test_a_report_outside_the_ledgers_a_task_appends_to_today_stops_the_shard(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ledger the declaration never names, or a day that is not the wake's, is refused."""
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "report", REPORT_FILES)
    before = commits_on(origin)

    outcome, said = ran((name,), settings, checkout, "garden_tasks_report", monkeypatch)

    assert outcome.exit_code == EXIT_INTEGRITY
    assert outcome.record is None, "a record was written for a shard that filed astray"
    assert any(
        f"{name} filed state/raw/visual-prunes/" in line
        and "which is not a report of a ledger it appends to under today's day" in line
        for line in said
    ), said
    assert commits_on(origin) == before


def test_a_folder_the_checkout_lacks_is_still_listed_from_the_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Members come from the commit's names, so a folder the checkout lacks is not a zero.

    The deletion lands from the name alone, and the file the window keeps stays.
    """
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)
    shutil.rmtree(checkout / "state" / "old-days")

    outcome, said = ran(
        ("compact-gardener", "old-days", "rehearsal"),
        settings,
        checkout,
        "garden_tasks_ok",
        monkeypatch,
    )

    assert outcome.exit_code == EXIT_OK, said
    rows = rows_of(outcome.record)
    assert (rows["old-days"].stopped_because, rows["old-days"].deleted) == (
        StopReason.EXHAUSTED,
        1,
    )
    assert on_origin(origin, f"state/old-days/{AGED}") is None, "the deletion did not land"
    assert on_origin(origin, f"state/old-days/{FRESH}") == "fresh\n", "a kept file went"


def test_a_folder_the_commit_does_not_hold_yet_is_walked_as_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Nothing has written the folder, so there is nothing in it to take, and the task runs."""
    files = {key: text for key, text in RUNNER_FILES.items() if "rehearsal" not in key}
    _, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", files)

    with caplog.at_level("INFO", logger=runner.__name__):
        outcome, _ = ran(("rehearsal",), settings, checkout, "garden_tasks_ok", monkeypatch)

    assert outcome.exit_code == EXIT_OK
    row = rows_of(outcome.record)["rehearsal"]
    assert (row.stopped_because, row.candidates_seen) == (StopReason.EXHAUSTED, 0)
    assert "which the commit does not hold yet" in caplog.text


def test_without_the_commit_a_missing_folder_is_skipped_rather_than_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`run-task` reads no commit, so the checkout is taken as it stands."""
    _, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)
    shutil.rmtree(checkout / "state" / "rehearsal")

    outcome, _ = ran(("rehearsal",), settings, checkout, "garden_tasks_ok", monkeypatch, land=False)

    assert outcome.exit_code == EXIT_OK
    assert rows_of(outcome.record)["rehearsal"].stopped_because is StopReason.EXHAUSTED


def a_garden_with_the_complement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str]
) -> tuple[Path, GardenerSettings]:
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, files)
    declared = a_config(
        checkout, GARDENER_FIXTURES / "runner", GARDENER_FIXTURES / "garden" / "trials.json"
    )
    return checkout, config.load_gardener(declared)


def test_a_named_trial_root_runs_without_discovering_state_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The declaration names its roots, so the runner needs no child-directory discovery."""
    checkout, settings = a_garden_with_the_complement(tmp_path, monkeypatch, RUNNER_FILES)

    outcome, _ = ran(
        ("trials",), settings, checkout, "garden_tasks_ok", monkeypatch, land=False
    )

    assert outcome.exit_code == EXIT_OK
    assert rows_of(outcome.record)["trials"].selected == 0
    assert (checkout / "state" / "old-days" / AGED).is_file()


def test_a_named_trial_root_selects_its_period_and_ignores_unconfigured_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a configured trial root and a named date are in the pass's listing."""
    stray = "state/pipeline-tests-production-settings/seen/2026/06/25/2026-06-25.txt"
    checkout, settings = a_garden_with_the_complement(
        tmp_path, monkeypatch, {**RUNNER_FILES, stray: "aged\n"}
    )
    write(checkout / "state" / "never-committed" / "2026-05-01.txt", "aged\n")

    outcome, said = ran(("trials",), settings, checkout, "garden_tasks_ok", monkeypatch)

    assert outcome.exit_code == EXIT_OK
    assert rows_of(outcome.record)["trials"].selected == 1
    assert f"  {stray}" in said


def test_modules_that_do_not_match_the_declarations_stop_the_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)

    outcome, said = ran(("old-days",), settings, checkout, "garden_tasks_wander", monkeypatch)

    assert outcome.exit_code == EXIT_INTEGRITY
    assert outcome.record is None
    assert any("served by no module" in line for line in said)


@pytest.mark.parametrize("land", [True, False])
def test_a_history_task_named_to_the_runner_is_refused_and_nothing_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, land: bool
) -> None:
    """Run here, the squash's task would only stamp its day and hold off the real rewrite.

    Both ways a person can name a task - landed through the utility, or run in
    the checkout by the package's own verb - reach the runner, and it refuses
    before anything runs, naming the one program that runs a history task.
    """
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, {"corpus/corpus.jsonl": "{}\n"})
    settings = config.load_gardener(
        a_config(checkout, GARDENER_FIXTURES / "garden" / "history.json")
    )
    before = commits_on(origin)

    outcome, said = ran(
        ("history",), settings, checkout, "garden_tasks_history", monkeypatch, land=land
    )

    assert (outcome.exit_code, outcome.record, outcome.landing) == (EXIT_INTEGRITY, None, None)
    assert any(
        "history rewrites history" in line and runner.HISTORY_PROGRAM in line for line in said
    ), said
    assert commits_on(origin) == before
    assert git(checkout, "status", "--porcelain", "--", "corpus", "state") == ""


def test_trials_owns_only_its_configured_roots(tmp_path: Path) -> None:
    """The trial task neither claims nor discovers any other state directory.

    Its configured roots are disjoint from other tasks and ledger families.
    """
    settings = config.load_gardener(a_config(tmp_path, GARDENER_FIXTURES / "garden"))
    named = {
        name: tuple(policy.owns)
        for name, policy in settings.tasks.items()
    }
    folders = [(name, folder) for name, owned in named.items() for folder in owned]
    for index, (first, one) in enumerate(folders):
        for second, other in folders[index + 1 :]:
            if first == second:
                continue
            assert not (one == other or one.startswith(f"{other}/") or other.startswith(f"{one}/"))

    owns = settings.tasks["trials"].owns
    assert set(owns) == {
        "state/pipeline-tests-production-settings",
        "state/pipeline-tests-no-visual-plan",
        "state/pipeline-tests-parallel-summarization",
    }
    sweeps = runner.owner_of("trials", settings.tasks)
    assert all(sweeps(folder) and sweeps(f"{folder}/x.csv") for folder in owns)
    for claimed in sorted(ledger.claimed_roots()):
        assert not sweeps(f"{ledger.STATE_DIRNAME}/{claimed}/2026/09/27/x.csv"), claimed
    assert not sweeps(f"{ledger.STATE_DIRNAME}/a-trial-run/2026-09-01.json")
    assert not sweeps(ledger.STATE_DIRNAME), "the task does not own the state root"
