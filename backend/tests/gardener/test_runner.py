"""Does a shard run every task, hold each to what it owns, and land exactly one record?

End to end, with nothing standing in: fixture declarations loaded through the
real loader, real task modules from `tests/fixtures/gardener/task_packages/`,
real day files in a real clone, and a bare repository standing in for origin.
What reaches origin is read back from origin, so a record that was written and
never pushed, or a file deleted and never staged, fails here.

The clock is handed in rather than read, so every instant on a record is one
written out below, in UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.gardener import runner
from idhazh.gardener.publish import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED

from ._garden import GARDENER_FIXTURES, a_config, an_origin, commits_on, git, on_origin, quiet_git
from ._garden import task_package as a_package

pytestmark = pytest.mark.slow

WAKE = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID = "2026-09-27-18012345678"
#: A day the three-day window has aged out, and one it has not.
AGED, FRESH = "2026-09-01.txt", "2026-09-26.txt"


def a_garden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: str, files: dict[str, str]
) -> tuple[Path, Path, GardenerSettings]:
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, files)
    return origin, checkout, config.load_gardener(a_config(checkout, GARDENER_FIXTURES / fixture))


def ran(
    names: tuple[str, ...],
    settings: GardenerSettings,
    checkout: Path,
    package: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    publish_it: bool = True,
) -> tuple[runner.Outcome, list[str]]:
    said: list[str] = []
    outcome = runner.run(
        names,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        publish_it=publish_it,
        package=a_package(package, monkeypatch),
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
    "state/compact/gardener/.keep": "",
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
    assert outcome.record.parent == checkout.joinpath("state", "raw", "gardener", "2026", "09", "27")
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


def test_without_publish_the_record_stays_in_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Landing resets the checkout and pushes to main, so it happens only when asked for."""
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)
    before = commits_on(origin)

    outcome, said = ran(
        ("old-days",), settings, checkout, "garden_tasks_ok", monkeypatch, publish_it=False
    )

    assert outcome.exit_code == EXIT_OK
    assert outcome.record is not None and outcome.record.is_file()
    assert commits_on(origin) == before, "a run without --publish pushed"
    assert said[-1].endswith("and pushed nothing")


def test_a_task_that_fails_still_has_a_row_and_its_sibling_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {f"state/old-days/{AGED}": "aged\n", "state/broken/.keep": ""}
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "breaks", files)

    outcome, _ = ran(("broken", "old-days"), settings, checkout, "garden_tasks_breaks", monkeypatch)

    assert outcome.exit_code == EXIT_TASK_FAILED
    rows = rows_of(outcome.record)
    assert rows["broken"].stopped_because is StopReason.FAILED
    assert (rows["broken"].deleted, rows["broken"].resume_from) == (0, None)
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


def test_a_task_whose_folder_is_missing_fails_and_says_which(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {key: text for key, text in RUNNER_FILES.items() if "rehearsal" not in key}
    _, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", files)

    outcome, _ = ran(
        ("compact-gardener", "old-days", "rehearsal"),
        settings,
        checkout,
        "garden_tasks_ok",
        monkeypatch,
        publish_it=False,
    )

    assert outcome.exit_code == EXIT_TASK_FAILED
    rows = rows_of(outcome.record)
    assert rows["rehearsal"].stopped_because is StopReason.FAILED
    assert rows["old-days"].stopped_because is StopReason.EXHAUSTED


def test_modules_that_do_not_match_the_declarations_stop_the_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)

    outcome, said = ran(("old-days",), settings, checkout, "garden_tasks_wander", monkeypatch)

    assert outcome.exit_code == EXIT_INTEGRITY
    assert outcome.record is None
    assert any("served by no module" in line for line in said)


def test_a_history_task_run_by_name_records_the_history_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {"corpus/corpus.jsonl": "{}\n"})
    settings = config.load_gardener(a_config(checkout, GARDENER_FIXTURES / "garden" / "history.json"))

    outcome, _ = ran(
        ("history",), settings, checkout, "garden_tasks_history", monkeypatch, publish_it=False
    )

    assert outcome.exit_code == EXIT_OK
    assert rows_of(outcome.record)["history"].job is ServerJob.HISTORY


def test_the_complement_owns_nothing_another_task_or_a_ledger_claims(tmp_path: Path) -> None:
    """Every pair of named tasks is disjoint, and the complement reaches none of them.

    What the complement does own is a stray folder under `state/` that no task
    and no ledger family claims, which is the trial tree it exists to sweep.
    """
    settings = config.load_gardener(a_config(tmp_path, GARDENER_FIXTURES / "garden"))
    named = {
        name: tuple(policy.owns) for name, policy in settings.tasks.items() if policy.owns is not None
    }
    folders = [(name, folder) for name, owned in named.items() for folder in owned]
    for index, (first, one) in enumerate(folders):
        for second, other in folders[index + 1 :]:
            if first == second:
                continue
            assert not (one == other or one.startswith(f"{other}/") or other.startswith(f"{one}/"))

    sweeps = runner.owner_of("trials", settings.tasks)
    assert not [folder for _, folder in folders if sweeps(folder) or sweeps(f"{folder}/x.csv")]
    for claimed in sorted(ledger.claimed_roots()):
        assert not sweeps(f"{ledger.STATE_DIRNAME}/{claimed}/2026/09/27/x.csv"), claimed
    assert sweeps(f"{ledger.STATE_DIRNAME}/a-trial-run/2026-09-01.json")
    assert not sweeps(ledger.STATE_DIRNAME), "the complement owns the root itself"
