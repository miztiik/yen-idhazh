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

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import TaskFinished, TaskOutcome, TaskPlanned
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.contracts.ledger_index import CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgerLifecycleStatus, LedgersConfig
from idhazh.gardener import event_log, report, runner
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Outcome
from idhazh.ledger import paths
from utilities import gardener_publish

from ._events import events, the_event
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
from .tasks.test_compaction import a_pass, filed

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


def test_a_shard_whose_own_family_is_paused_fails_loudly_and_records_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gardener's record is a new row, so a paused family refuses it like any other.

    Until 2026-10-08 the ledger door exempted every write carrying a maintenance
    job - `migrate`, `run-tasks`, `history` - from the lifecycle check, on the
    reading that such a job only files rows that were already recorded. This
    write is the one the exemption actually reached, and it is a new row: the
    shard's own record of a wake, which nothing recorded before it.

    With the exemption gone a paused `gardener` family takes no record, and the
    shard says so by its exit code rather than by carrying on with a record it
    never wrote. That loud failure is the point - pausing the family a wake
    writes into is a configuration nobody can act on if the wake reports success.
    """
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "runner", RUNNER_FILES)
    before = commits_on(origin)
    raw = json.loads(read_text(CONFIG_DIR / paths.REGISTRY_FILENAME))
    for family in raw["families"]:
        if any(held["name"] == LedgerName.GARDENER.value for held in family["ledgers"]):
            family["lifecycle_status"] = LedgerLifecycleStatus.PAUSED.value
    monkeypatch.setattr(paths, "_CONFIG", LedgersConfig.model_validate(raw))

    outcome, said = ran(("old-days",), settings, checkout, "garden_tasks_ok", monkeypatch)

    assert outcome.exit_code != EXIT_OK, "a wake that recorded nothing reported success"
    assert outcome.record is None
    assert commits_on(origin) == before, "a record nothing wrote reached main"
    assert any("paused or retired" in line for line in said), (
        f"the shard never said why it refused: {said}"
    )


def test_trial_compaction_runs_each_root_and_leaves_production_rows_unchanged(
    tmp_path: Path,
) -> None:
    settings = config.load_gardener()
    repo_root = tmp_path
    day = "2026-10-02"
    row_template = ItemHealthRow.model_validate_json(
        (CONTRACT_FIXTURES_DIR / "item-health-row" / "published.json").read_text(
            encoding="utf-8"
        )
    )
    production_row = row_template.model_copy(
        update={"date": day, "run_id": f"{day}-100", "item_id": "production-item-01"}
    )
    production_identity = WriterIdentity(
        run_id="2026-10-03-100",
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
        producer="work",
        git_sha="a" * 40,
    )
    production_raw = ledger.persist(
        repo_root / "state",
        [production_row],
        ledger=LedgerName.ITEM_HEALTH,
        covers=day,
        identity=production_identity,
    )[0]
    production_bytes = production_raw.read_bytes()
    expected: dict[str, ItemHealthRow] = {}
    for number, case in enumerate(("production-settings", "no-visual-plan"), start=1):
        row = row_template.model_copy(
            update={
                "date": day,
                "run_id": f"{day}-{number}",
                "item_id": f"trial-item-{number}-01",
            }
        )
        expected[case] = row
        with ledger.use_registry(ledger.overlay_registry(("pipeline-tests", case))):
            ledger.persist(
                repo_root / "state",
                [row],
                ledger=LedgerName.ITEM_HEALTH,
                covers=day,
                identity=WriterIdentity(
                    run_id=f"{day}-{number}",
                    attempt=1,
                    job=ServerJob.WORK,
                    shard=0,
                    producer="work",
                    git_sha="a" * 40,
                ),
            )

    outcome = runner.run(
        ["compact-trial-item-health"],
        settings=settings,
        repo_root=repo_root,
        run_id="2026-10-04-9001",
        attempt=1,
        shard=0,
        git_sha="b" * 40,
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        clock=lambda: datetime(2026, 10, 4, tzinfo=UTC),
    )

    assert outcome.exit_code == EXIT_OK
    task_row = rows_of(outcome.record)["compact-trial-item-health"]
    assert task_row.selected > 0, task_row.model_dump_json()
    for case, row in expected.items():
        root = repo_root / "state"
        with ledger.use_registry(ledger.overlay_registry(("pipeline-tests", case))):
            daily_index = ledger.compact_index_path(
                root, LedgerName.ITEM_HEALTH, Period.DAILY
            )
            assert daily_index.is_file()
            assert day in {
                entry.covers for entry in CompactIndex.read(daily_index).entries
            }
            assert ledger.load_days(
                root, LedgerName.ITEM_HEALTH, [day], model=ItemHealthRow
            ) == [row]
            compact = ledger.compact_file(root, LedgerName.ITEM_HEALTH, Period.DAILY, day)
            assert compact is not None and compact.is_file()
            envelope = ledger.read_envelope(compact)
            assert envelope.identity.run_id == "2026-10-04-9001"
            assert envelope.identity.job is ServerJob.RUN_TASKS
            assert envelope.identity.git_sha == "b" * 40

    assert production_raw.read_bytes() == production_bytes
    assert not ledger.compact_index_path(
        repo_root / "state", LedgerName.ITEM_HEALTH, Period.DAILY
    ).exists()
    assert outcome.record is not None
    (recorded,) = ledger.load([outcome.record], model=CollectionPruneRow)
    assert recorded.task == "compact-trial-item-health"


def test_a_task_whose_service_is_down_is_deferred_and_the_shard_stays_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for an outage at the shard: its only non-green task is deferred, so it exits 0.

    The listing service did not answer, which is a cause outside the code: the
    row says `deferred` and why, the sibling still runs and lands, and nothing
    asks a person for work. Its event is a warning, never an error.
    """
    files = {f"state/old-days/{AGED}": "aged\n", "state/broken/.keep": ""}
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "breaks", files)

    with caplog.at_level("INFO", logger=event_log.__name__):
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
    assert finished_levels(caplog) == {
        "broken": (TaskOutcome.DEFERRED, logging.WARNING),
        "old-days": (TaskOutcome.DONE, logging.INFO),
    }


def test_a_task_whose_code_is_wrong_fails_and_its_sibling_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A code defect turns the shard red, and it still lands its record.

    Its event is an error naming the exception's type and never what it said.
    """
    files = {f"state/old-days/{AGED}": "aged\n", "state/defect/.keep": ""}
    origin, checkout, settings = a_garden(tmp_path, monkeypatch, "breaks", files)

    with caplog.at_level("INFO", logger=event_log.__name__):
        outcome, _ = ran(
            ("defect", "old-days"), settings, checkout, "garden_tasks_breaks", monkeypatch
        )

    assert outcome.exit_code == EXIT_TASK_FAILED
    rows = rows_of(outcome.record)
    assert (rows["defect"].stopped_because, rows["defect"].fault) == (
        StopReason.FAILED,
        GardenerFault.RAISED,
    )
    assert (rows["defect"].deleted, rows["defect"].resume_from) == (0, None)
    assert rows["old-days"].stopped_because is StopReason.EXHAUSTED
    assert on_origin(origin, f"state/old-days/{AGED}") is None, "the sibling did not land"
    assert finished_levels(caplog)["defect"] == (TaskOutcome.FAILED, logging.ERROR)
    (defect,) = [held for held in events(caplog.records, TaskFinished) if held.task == "defect"]
    assert (defect.error, defect.next) == ("KeyError", report.WHY[GardenerFault.RAISED])
    assert defect.where is not None and defect.where.startswith("idhazh.gardener.runner:")
    assert "created_at" not in defect.model_dump_json(), "the exception's text reached a line"


def test_a_missing_yearly_index_needs_manual_action_and_lands_the_failed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE: the real runner preserves an established tree and records the refusal."""
    indexes = {
        f"state/compact/gardener/index/{period.value}.json": CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=LedgerName.GARDENER,
            period=period,
            entries=[],
        ).to_json()
        for period in (Period.DAILY, Period.MONTHLY)
    }
    ledger_files = {
        **indexes,
        "state/compact/gardener/monthly/2025/08.parquet": "already packed\n",
        "state/raw/gardener/2026/09/20/held.jsonl": "already filed\n",
    }
    origin, checkout, _ = a_garden(tmp_path, monkeypatch, "runner", ledger_files)
    settings = config.load_gardener(
        a_config(checkout, CONFIG_DIR / "gardener" / "compact-gardener.json")
    )
    said: list[str] = []

    with caplog.at_level(logging.INFO, logger=event_log.__name__):
        outcome = gardener_publish.run_and_land(
            ("compact-gardener",),
            settings=settings,
            repo_root=checkout,
            run_id=RUN_ID,
            attempt=1,
            shard=0,
            clock=lambda: WAKE,
            say=said.append,
        )

    assert outcome.exit_code == EXIT_TASK_FAILED, said
    row = rows_of(outcome.record)["compact-gardener"]
    assert (row.stopped_because, row.fault.value if row.fault else None) == (
        StopReason.FAILED,
        "manual-action",
    )
    finished_record = next(
        record
        for record in caplog.records
        if isinstance(event_log.payload(record), TaskFinished)
    )
    finished = event_log.payload(finished_record)
    assert isinstance(finished, TaskFinished)
    assert (finished.outcome, finished_record.levelno) == (TaskOutcome.FAILED, logging.ERROR)
    assert (finished.error, finished.next) == (
        "ManualActionError",
        "a known refusal needs a person's action before the next wake can continue",
    )
    assert outcome.record is not None and outcome.record.is_file()
    recorded = outcome.record.relative_to(checkout).as_posix()
    landed = git(origin, "--git-dir=.", "ls-tree", "-r", "--name-only", "main").splitlines()
    assert recorded in landed, "the failed task's record did not land"
    assert {
        path: git(origin, "--git-dir=.", "show", f"main:{path}") for path in ledger_files
    } == ledger_files, "the refusal changed an existing ledger file"
    assert "state/compact/gardener/index/yearly.json" not in landed


def finished_levels(caplog: pytest.LogCaptureFixture) -> dict[str, tuple[TaskOutcome, int]]:
    """How each task ended, and the level its finished event was logged at."""
    return {
        held.task: (held.outcome, record.levelno)
        for record in caplog.records
        if isinstance(held := event_log.payload(record), TaskFinished)
    }


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
    assert [held.task for held in outcome.finished_tasks] == ["wanderer"], (
        "a shard refused after its task ran forgot how that task ended"
    )
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

    with caplog.at_level("INFO", logger=event_log.__name__):
        outcome, _ = ran(("rehearsal",), settings, checkout, "garden_tasks_ok", monkeypatch)

    assert outcome.exit_code == EXIT_OK
    row = rows_of(outcome.record)["rehearsal"]
    assert (row.stopped_because, row.candidates_seen) == (StopReason.EXHAUSTED, 0)
    assert the_event(caplog.records, TaskPlanned).absent == ["state/rehearsal"]


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Only a configured trial root and a named date are in the pass's listing."""
    stray = (
        "state/raw/traces/pipeline-tests/production-settings/"
        "2026/06/25/2026-06-25.txt"
    )
    checkout, settings = a_garden_with_the_complement(
        tmp_path, monkeypatch, {**RUNNER_FILES, stray: "aged\n"}
    )
    write(checkout / "state" / "never-committed" / "2026-05-01.txt", "aged\n")

    with caplog.at_level("INFO", logger=event_log.__name__):
        outcome, _ = ran(("trials",), settings, checkout, "garden_tasks_ok", monkeypatch)

    assert outcome.exit_code == EXIT_OK
    assert rows_of(outcome.record)["trials"].selected == 1
    assert the_event(caplog.records, TaskFinished).taken == [stray]


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
        "state/raw/traces/pipeline-tests/production-settings",
        "state/raw/traces/pipeline-tests/no-visual-plan",
        "state/raw/traces/pipeline-tests/parallel-summarization",
    }
    sweeps = runner.owner_of("trials", settings.tasks)
    assert all(sweeps(folder) and sweeps(f"{folder}/x.csv") for folder in owns)
    for claimed in sorted(ledger.claimed_roots()):
        assert not sweeps(f"{ledger.STATE_DIRNAME}/{claimed}/2026/09/27/x.csv"), claimed
    assert not sweeps(f"{ledger.STATE_DIRNAME}/a-trial-run/2026-09-01.json")
    assert not sweeps(ledger.STATE_DIRNAME), "the task does not own the state root"


# --- What a task says before it runs and when it ends ---------------------------------

#: The one compaction the outcome cases run, and the wakes they run at: 2026-09-21
#: is the newest day the first may pack, and 2026-10-22 the newest the second may.
PACKING: Final = "compact-visual-prunes"
FIRST_WAKE: Final = datetime(2026, 9, 23, 0, 40, tzinfo=UTC)
LATER_WAKE: Final = datetime(2026, 10, 24, 0, 40, tzinfo=UTC)

#: The level each ending is logged at: a failure is an error, a deferred task a warning.
LEVEL: Final = {TaskOutcome.FAILED: logging.ERROR, TaskOutcome.DEFERRED: logging.WARNING}


def a_compaction(root: Path, **changed: Any) -> GardenerSettings:
    """The committed visual-prunes compaction, live unless `changed` says otherwise."""
    declared = root / "declared" / f"{PACKING}.json"
    declared.parent.mkdir(parents=True)
    committed = json.loads(read_text(CONFIG_DIR / "gardener" / f"{PACKING}.json"))
    declared.write_text(json.dumps(committed | {"dry_run": False} | changed), encoding="ascii")
    return config.load_gardener(a_config(root, declared))


def compacted(
    root: Path, settings: GardenerSettings, wake: datetime, named: tuple[str, str] | None
) -> Outcome:
    """One run of the compaction alone, in the checkout, at `wake`, over a range a person named."""
    return runner.run(
        (PACKING,),
        settings=settings,
        repo_root=root,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha="a" * 40,
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        period_range=named,
        clock=lambda: wake,
    )


def a_ledger_ending(
    word: TaskOutcome, root: Path
) -> tuple[GardenerSettings, datetime, tuple[str, str] | None]:
    """A ledger under `root` whose next pass ends on `word`, the wake it runs at, and its range.

    Each starts from one raw day of the cleanup report, filed through the ledger
    door, except the ledger with nothing in it. Idle cases disable yearly pruning
    so a new expiry index does not turn initialization into completed work.
    """
    if word is not TaskOutcome.EMPTY:
        filed(root, a_pass("2026-09-22" if word is TaskOutcome.NOT_DUE else "2026-09-20"))
    match word:
        case TaskOutcome.FAILED:
            # A folder inside a raw day: there is no file to move aside, so the
            # day is refused for manual action.
            write(root / "state/raw/visual-prunes/2026/09/20/sub/stray.txt", "stray\n")
            return a_compaction(root), FIRST_WAKE, None
        case TaskOutcome.DEFERRED:
            settings = a_compaction(root)
            compacted(root, settings, FIRST_WAKE, None)
            return settings, LATER_WAKE, ("2026-10", "2026-10")
        case TaskOutcome.DRY_RUN:
            return a_compaction(root, dry_run=True), FIRST_WAKE, None
        case TaskOutcome.CEILING:
            return a_compaction(root, max_periods_per_run=1), FIRST_WAKE, None
        case TaskOutcome.OUTSIDE_RANGE:
            return (
                a_compaction(root, yearly_prune_enable=False),
                FIRST_WAKE,
                ("2026-08", "2026-08"),
            )
        case TaskOutcome.EMPTY | TaskOutcome.NOT_DUE:
            return a_compaction(root, yearly_prune_enable=False), FIRST_WAKE, None
        case _:
            return a_compaction(root), FIRST_WAKE, None


@pytest.mark.parametrize("word", list(TaskOutcome), ids=str)
def test_each_way_a_task_can_end_is_said_once_after_what_it_was_planned_with(
    word: TaskOutcome, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """THE ORACLE for the events: one ledger for each word a task can end on, run by the runner.

    The task says what it runs with before it runs, and how it ended after, in
    that order and once each; both are read off the records, never the text.
    How it ended agrees with the row the shard writes, and the level it is
    logged at is an error for either failed fault.
    """
    root = tmp_path / "checkout"
    settings, wake, named = a_ledger_ending(word, root)
    caplog.clear()

    with caplog.at_level(logging.INFO, logger=event_log.__name__):
        outcome = compacted(root, settings, wake, named)

    said = [event_log.payload(record) for record in caplog.records]
    kinds = [type(held) for held in said if isinstance(held, (TaskPlanned, TaskFinished))]
    assert kinds == [TaskPlanned, TaskFinished]
    planned = the_event(caplog.records, TaskPlanned)
    assert (planned.task, planned.kind, planned.run_id, planned.today) == (
        PACKING,
        TaskKind.COMPACTION,
        RUN_ID,
        wake.date().isoformat(),
    )
    assert planned.operator_range == named
    assert planned.declared["dry_run"] is (word is TaskOutcome.DRY_RUN)
    assert {"kind", "owns", "reads", "prune_refusal"}.isdisjoint(planned.declared)
    (record,) = [held for held in caplog.records if isinstance(event_log.payload(held), TaskFinished)]
    ended = the_event(caplog.records, TaskFinished)
    assert (ended.task, ended.outcome) == (PACKING, word)
    assert record.levelno == LEVEL.get(word, logging.INFO)
    row = rows_of(outcome.record)[PACKING]
    assert (ended.stopped_because, ended.fault, ended.resume_from) == (
        row.stopped_because,
        row.fault,
        row.resume_from,
    )
    if word is TaskOutcome.FAILED:
        assert row.fault is GardenerFault.MANUAL_ACTION
    assert ended.periods is not None, "a compaction says what it did, period by period"
    assert outcome.exit_code == (EXIT_TASK_FAILED if word is TaskOutcome.FAILED else EXIT_OK)
    if word is TaskOutcome.EMPTY:
        assert planned.absent == ["state/raw/visual-prunes", "state/compact/visual-prunes"]


def test_empty_retention_range_keeps_operator_intent_separate_from_scheduled_window(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    declaration = CONFIG_DIR / "gardener" / "digest-fragments.json"
    settings = config.load_gardener(a_config(tmp_path, declaration))
    named = ("2024-08-01", "2024-08-02")

    def run(
        run_id: str, period_range: tuple[str, str] | None
    ) -> tuple[TaskPlanned, TaskFinished]:
        caplog.clear()
        with caplog.at_level(logging.INFO, logger=event_log.__name__):
            runner.run(
                ("digest-fragments",),
                settings=settings,
                repo_root=tmp_path,
                run_id=run_id,
                attempt=1,
                shard=0,
                git_sha="a" * 40,
                committed_folders=None,
                cone_bytes=None,
                listing=None,
                period_range=period_range,
                clock=lambda: WAKE,
            )
        planned = the_event(caplog.records, TaskPlanned)
        finished = the_event(caplog.records, TaskFinished)
        return planned, finished

    named_planned, named_finished = run(RUN_ID, named)
    scheduled_planned, scheduled_finished = run("2026-09-27-18012345679", None)

    assert named_planned.operator_range == named
    assert named_finished.outcome is TaskOutcome.OUTSIDE_RANGE
    assert scheduled_planned.operator_range is None
    assert scheduled_finished.outcome is TaskOutcome.NOT_DUE
