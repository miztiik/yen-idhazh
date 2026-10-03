"""Does a live fold inside a dry task land on main, and leave alone what the window only reported?

One shard at a time through `backend/utilities/gardener_publish.py`, the way a
wake runs it, against a bare repository standing in for origin - no network
(CLAUDE.md section 13). The task is the shipped `feed-health` module under the
committed declarations, whose window reports and whose fold is live, over a
tree its own writer files: three closed days, one day the window ages out and
one open day, each holding the files of two runs. What reached origin is read
back from origin, so a settled file written and never staged, or a writer file
deleted and never staged, fails here. The last test asks the same ledger to
settle a closed month into one file.

The clock is handed in rather than read, so the wake is one written out below,
in UTC.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, seed_feed_health

from idhazh import config, day_shards, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.feed_health import FeedHealthRow, FetchOutcome
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import runner
from idhazh.gardener.outcome import EXIT_OK, EXIT_TASK_FAILED
from utilities import gardener_publish

from ._garden import (
    GARDENER_FIXTURES,
    a_config,
    an_origin,
    commits_on,
    git,
    named_task_package,
    on_origin,
    quiet_git,
    read_origin,
)
from ._garden import task_package as a_package

#: A wake on the 28th. The 27th ended at its first instant, so it is still open;
#: the three closed September days closed weeks ago.
WAKE: Final = datetime(2026, 9, 28, 0, 40, tzinfo=UTC)
RUN_ID: Final = "2026-09-28-18099999999"
OPEN_DAY: Final = "2026-09-27"
CLOSED_DAYS: Final = ("2026-09-19", "2026-09-20", "2026-09-21")
#: A day the 14-month window has aged out. The window is a dry run, so it only
#: reports this day's files, and the fold leaves the day to the window.
REPORTED_DAY: Final = "2025-06-10"
#: How many runs filed each day of the tree, so how many writer files it holds.
RUNS_A_DAY: Final = 2

TREE: Final = LedgerName.FEED_HEALTH


def a_verdict(day: str, *, run: str, feed: str) -> FeedHealthRow:
    return FeedHealthRow.model_validate(
        {
            "run_id": run,
            "date": day,
            "feed_id": feed,
            "checked_at": f"{day}T06:00:00Z",
            "outcome": FetchOutcome.OK,
            "status": 200,
            "items": 3,
        }
    )


def writer_files(scratch: Path, day: str) -> dict[str, str]:
    """Each run's plan job filing a verdict into one day, as repository paths and text."""
    state = scratch / ledger.STATE_DIRNAME
    for number in range(1, RUNS_A_DAY + 1):
        run = f"{day}-90000000{number}"
        seed_feed_health(state, day, [a_verdict(day, run=run, feed=f"feed-{number}")], run_id=run)
    folder = ledger.path(state, TREE, day)
    return {
        path.relative_to(scratch).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(folder.iterdir())
    }


def the_tree(scratch: Path, days: tuple[str, ...]) -> dict[str, str]:
    """These days of the tree, every one filed by its own writer."""
    files: dict[str, str] = {}
    for day in days:
        files |= writer_files(scratch, day)
    return files


def folder_of(day: str) -> str:
    """Where one day of the tree sits, as a repository path."""
    return f"{ledger.STATE_DIRNAME}/{TREE.value}/{day[:4]}/{day[5:7]}/{day[8:10]}"


def settled_rows(state: Path, day: str) -> list[dict[str, str]]:
    return day_shards.settled_day(
        ledger.tree_root(state, TREE), day, ledger.segment_key(TREE), ledger.segment_contract(TREE)
    )


@pytest.fixture(scope="module")
def tree_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """The tree's writer files, filed once for the module. Tests only read them."""
    return the_tree(tmp_path_factory.mktemp("scratch"), (*CLOSED_DAYS, REPORTED_DAY, OPEN_DAY))


def a_garden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str]
) -> tuple[Path, Path, dict[str, str], GardenerSettings]:
    """The committed declarations over a clone of an origin holding the tree."""
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, files)
    settings = config.load_gardener(a_config(checkout, CONFIG_DIR / "gardener"))
    return origin, checkout, files, settings


def only_row(record: Path | None, task: str) -> CollectionPruneRow:
    assert record is not None, "the shard wrote no record"
    rows = {row.task: row for row in ledger.load([record], model=CollectionPruneRow)}
    return rows[task]


def test_a_live_fold_inside_a_dry_task_lands_and_the_window_s_report_stays_a_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_files: dict[str, str]
) -> None:
    """The window is dry and the fold is live, so main gains the fold and nothing else.

    After the push, main holds each closed day's `settled.csv` with the rows its
    writer files settled to, none of those writer files, every file the window
    only reported - untouched and unfolded - and the open day as it was.
    """
    origin, checkout, files, settings = a_garden(tmp_path, monkeypatch, tree_files)
    policy = settings.tasks[TREE.value]
    assert policy.dry_run is True, "the window has to be the dry half, or this proves less"
    before = {day: settled_rows(checkout / ledger.STATE_DIRNAME, day) for day in CLOSED_DAYS}
    said: list[str] = []

    outcome = gardener_publish.run_and_land(
        (TREE.value,),
        settings=settings,
        repo_root=checkout,
        package=named_task_package(tmp_path, monkeypatch),
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        clock=lambda: WAKE,
        say=said.append,
    )

    assert outcome.exit_code == EXIT_OK, said
    for day in CLOSED_DAYS:
        folder = folder_of(day)
        settled = on_origin(origin, f"{folder}/{day_shards.SETTLED_NAME}")
        assert settled is not None, f"{day}'s settled file was written and never landed"
        assert settled == (checkout / folder / day_shards.SETTLED_NAME).read_text(encoding="utf-8")
        assert settled_rows(checkout / ledger.STATE_DIRNAME, day) == before[day]
        for relpath in files:
            if relpath.startswith(f"{folder}/"):
                assert on_origin(origin, relpath) is None, f"{relpath} was folded and not deleted"
    untouched = [
        (relpath, text)
        for relpath, text in files.items()
        if relpath.startswith((f"{folder_of(REPORTED_DAY)}/", f"{folder_of(OPEN_DAY)}/"))
    ]
    assert len(untouched) == 4, "two reported files and two open-day files, or this proves less"
    for relpath, text in untouched:
        assert on_origin(origin, relpath) == text, f"{relpath} changed on main"
    assert on_origin(origin, f"{folder_of(REPORTED_DAY)}/{day_shards.SETTLED_NAME}") is None, (
        "the fold wrote a day the window was reporting"
    )
    assert commits_on(origin)[0].endswith(f": gardener: {TREE.value} on 2026-09-28")

    row = only_row(outcome.record, TREE.value)
    assert (row.dry_run, row.deleted) == (True, 2), "the window reports the aged-out day's files"
    assert (row.fold_dry_run, row.folded_days, row.folded_files) == (False, 3, 6)
    assert row.stopped_because is StopReason.EXHAUSTED


def test_a_writer_file_that_lands_while_the_fold_runs_survives_beside_the_settled_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tree_files: dict[str, str]
) -> None:
    """A re-run's file reaches main between the fold and its push, and its rows are kept.

    The push loses to the re-run, so the shard stages its own paths again on the
    new tip. The re-run's file is not one of them, so it stays beside the settled
    file, and the next wake folds it in.
    """
    origin, checkout, _, settings = a_garden(tmp_path, monkeypatch, tree_files)
    ran = runner.run(
        (TREE.value,),
        settings=settings,
        repo_root=checkout,
        package=named_task_package(tmp_path, monkeypatch),
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha=git(checkout, "rev-parse", "HEAD").strip(),
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        clock=lambda: WAKE,
        say=lambda _: None,
    )
    assert ran.landing is not None
    day = CLOSED_DAYS[0]
    seed = tmp_path / "other-run"
    git(tmp_path, "clone", "--quiet", str(origin), str(seed))
    late = f"{day}-900000009"
    seed_feed_health(
        seed / ledger.STATE_DIRNAME,
        day,
        [a_verdict(day, run=late, feed="a-late-feed")],
        run_id=late,
    )
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "a re-run files a verdict on a closed day")
    git(seed, "push", "--quiet", "origin", "HEAD:refs/heads/main")

    said: list[str] = []
    pushed = gardener_publish.publish(
        ran.landing, attempts=settings.config.attempts, repo=checkout, say=said.append
    )

    assert pushed == EXIT_OK, said
    after = read_origin(origin, tmp_path / "after", folder_of(day))
    folder = ledger.path(after / ledger.STATE_DIRNAME, TREE, day)
    names = sorted(path.name for path in folder.iterdir())
    assert day_shards.SETTLED_NAME in names and len(names) == 2, names
    feeds = [row["feed_id"] for row in settled_rows(after / ledger.STATE_DIRNAME, day)]
    assert "a-late-feed" in feeds, "the re-run's rows are in no file"


def test_a_window_that_fails_leaves_the_fold_for_the_next_wake(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed window hands on a list of what it took that nothing has checked.

    So the fold does not run that wake, the closed days keep every file, and the
    row's fold cells are empty - "did not run" - rather than zero.
    """
    quiet_git(tmp_path, monkeypatch)
    files = the_tree(tmp_path / "scratch", CLOSED_DAYS)
    _, checkout = an_origin(tmp_path, files)
    config_dir = a_config(checkout, GARDENER_FIXTURES / "breaks")
    broken = config_dir / "gardener" / "broken.json"
    declared = json.loads(broken.read_text(encoding="utf-8"))
    # Whatever a task is called, owning this ledger's folder makes it the one the
    # loader holds to the fourteen month files the widest console read opens.
    declared |= {
        "owns": [f"state/{TREE.value}"],
        "fold": {"dry_run": False},
        "window": {"unit": "months", "value": 14},
    }
    broken.write_text(json.dumps(declared), encoding="utf-8")
    settings = config.load_gardener(config_dir)

    outcome = runner.run(
        ("broken",),
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha=git(checkout, "rev-parse", "HEAD").strip(),
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        package=a_package("garden_tasks_breaks", monkeypatch),
        clock=lambda: WAKE,
        say=lambda _: None,
    )

    assert outcome.exit_code == EXIT_TASK_FAILED
    row = only_row(outcome.record, "broken")
    assert row.stopped_because is StopReason.FAILED
    assert (row.fold_dry_run, row.folded_days, row.folded_files) == (None, None, None)
    for relpath, text in files.items():
        assert (checkout / relpath).read_text(encoding="utf-8") == text
    assert outcome.landing is not None
    assert outcome.landing.deleted_paths == frozenset()


#: A wake on the first of October: August closed a month ago, the 29th of
#: September closed a day ago, and the 30th ended at this wake's own day.
MONTH_WAKE: Final = datetime(2026, 10, 1, 0, 40, tzinfo=UTC)


def test_a_settled_month_lands_as_one_file_and_its_days_files_leave_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real feed-health task lands its fold when configured to settle whole months.

    After the push, main holds August's one `settled.csv` with every ID its days
    held and none of the files it replaced, the closed day of September settled
    in its own folder, and the open day as it was.
    """
    quiet_git(tmp_path, monkeypatch)
    files = the_tree(
        tmp_path / "scratch",
        ("2026-08-03", "2026-08-17", "2026-08-31", "2026-09-29", "2026-09-30"),
    )
    tree = ledger.tree_relpath(TREE)
    origin, checkout = an_origin(tmp_path, files)
    config_dir = a_config(checkout, CONFIG_DIR / "gardener")
    declaration = config_dir / "gardener" / f"{TREE.value}.json"
    policy = json.loads(declaration.read_text(encoding="utf-8"))
    policy["fold"]["settles_months"] = True
    declaration.write_text(json.dumps(policy) + "\n", encoding="utf-8", newline="\n")
    settings = config.load_gardener(config_dir)
    key, model = ledger.segment_key(TREE), ledger.segment_contract(TREE)
    root = ledger.tree_root(checkout / ledger.STATE_DIRNAME, TREE)
    before = day_shards.settled_rows(root, key, model, days=UNBOUNDED_WINDOW)
    said: list[str] = []

    outcome = gardener_publish.run_and_land(
        (TREE.value,),
        settings=settings,
        repo_root=checkout,
        package=named_task_package(tmp_path, monkeypatch),
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        clock=lambda: MONTH_WAKE,
        say=said.append,
    )

    assert outcome.exit_code == EXIT_OK, said
    month = f"{tree}/2026/08/{day_shards.SETTLED_NAME}"
    assert on_origin(origin, month) == (checkout / month).read_text(encoding="utf-8")
    assert on_origin(origin, f"{tree}/2026/09/29/{day_shards.SETTLED_NAME}") is not None
    for relpath, text in files.items():
        if relpath.startswith(f"{tree}/2026/09/30/"):
            assert on_origin(origin, relpath) == text, f"{relpath} changed on main"
        else:
            assert on_origin(origin, relpath) is None, f"{relpath} was folded and not deleted"
    after = read_origin(origin, tmp_path / "after", tree)
    landed = ledger.tree_root(after / ledger.STATE_DIRNAME, TREE)
    assert day_shards.settled_rows(landed, key, model, days=UNBOUNDED_WINDOW) == before

    row = only_row(outcome.record, TREE.value)
    assert (row.fold_dry_run, row.folded_months, row.folded_days) == (False, 1, 1)
    assert row.folded_files == 8, "six August files and two files of the 29th"
    assert row.deleted == 0, "the window keeps these fixture months and takes nothing"
