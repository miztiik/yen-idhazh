"""Does a shard that checks out only its code decide from names and download only what it reads?

A wake's shard is a depth-1 partial clone whose sparse checkout names the
folders its code lives in and none of the folders its tasks own. Every name a
task decides from comes from the commit, the complement task's folders included,
so a task that decides from dates in paths downloads nothing, and a deletion
lands from the name alone. A task that reads a file's content fetches its folder
first, in one download. These tests clone the way a wake clones - a partial clone
of a `file://` origin, which a plain local clone would not be, because a local
clone copies every file and would hide a file the shard never downloaded - and
count what the clone downloaded from git's own trace of it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.gardener.outcome import EXIT_INTEGRITY, EXIT_OK, EXIT_TASK_FAILED, Outcome
from utilities import gardener_publish

from ._garden import (
    GARDENER_FIXTURES,
    OriginBlobs,
    a_config,
    a_partial_clone,
    an_origin,
    lazy_fetches,
    on_origin,
    quiet_git,
)
from ._garden import task_package as a_package

WAKE: Final = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID: Final = "2026-09-27-18012345678"

#: A day `old-days` has aged out, and one it keeps.
AGED: Final = "state/old-days/2026/09/19/2026-09-19.txt"
FRESH: Final = "state/old-days/2026/09/26/2026-09-26.txt"
#: A configured trial root and period, both named by the declaration and the wake.
STRAY: Final = "state/pipeline-tests-production-settings/seen/2026/06/25/2026-06-25.txt"
#: What the fixture compaction reads before it writes its summary.
COMPACTED: Final = "state/compact/gardener/monthly/2025/08.parquet"

#: Every file holds different bytes: git keeps equal files as one object, and a
#: file outside the checkout whose bytes matched one inside it would be in the
#: clone after all. The attributes are the repository's own rule, so writes are
#: hashed the way a wake hashes them.
FILES: Final = {
    ".gitattributes": "* text=auto eol=lf\n",
    AGED: "aged\n",
    FRESH: "fresh\n",
    "state/rehearsal/2026/09/19/2026-09-19.txt": "rehearsed\n",
    STRAY: "a trial run\n",
    COMPACTED: "compacted before this wake\n",
}


def a_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, GardenerSettings]:
    """An origin holding `FILES`, and a shard's clone of it whose checkout holds only config."""
    quiet_git(tmp_path, monkeypatch)
    origin, _ = an_origin(tmp_path, FILES)
    shard = a_partial_clone(tmp_path, origin, "config")
    declared = a_config(
        shard, GARDENER_FIXTURES / "runner", GARDENER_FIXTURES / "garden" / "trials.json"
    )
    return origin, shard, config.load_gardener(declared)


def landed(
    names: tuple[str, ...],
    settings: GardenerSettings,
    shard: Path,
    origin: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Outcome, dict[str, CollectionPruneRow], list[str], int]:
    """One shard run and landed, and how many downloads the clone started while it ran."""
    trace = shard.parent / "git-trace.log"
    monkeypatch.setenv("GIT_TRACE", str(trace))
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        names,
        settings=settings,
        repo_root=shard,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        package=a_package("garden_tasks_ok", monkeypatch),
        trees=OriginBlobs(origin),
        clock=lambda: WAKE,
        say=said.append,
    )
    monkeypatch.delenv("GIT_TRACE")
    assert outcome.record is not None, "the shard wrote no record"
    rows = {row.task: row for row in ledger.load([outcome.record], model=CollectionPruneRow)}
    return outcome, rows, said, lazy_fetches(trace)


def test_a_shard_that_decides_from_names_downloads_nothing_and_its_deletion_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every task here decides from the day in a path, the complement's included.

    The file the live task deleted was never downloaded, and the push still
    lands its deletion. The shard's weight still counts every file it owns.
    """
    origin, shard, settings = a_shard(tmp_path, monkeypatch)

    outcome, rows, said, downloads = landed(
        ("old-days", "rehearsal", "trials"), settings, shard, origin, monkeypatch
    )

    assert outcome.exit_code == EXIT_OK, said
    assert downloads == 0, "a task that decides from names downloaded a file"
    assert on_origin(origin, AGED) is None, "the deletion of a file never downloaded did not land"
    assert on_origin(origin, FRESH) == FILES[FRESH]
    assert on_origin(origin, STRAY) == FILES[STRAY], "a dry run deleted a file"
    assert not (shard / "state" / "old-days").exists(), "a folder was checked out"
    assert (rows["trials"].stopped_because, rows["trials"].selected) == (StopReason.EXHAUSTED, 1)
    assert (rows["rehearsal"].dry_run, rows["rehearsal"].deleted) == (True, 1)
    assert {row.cone_bytes for row in rows.values()} == {None}
    assert {row.downloaded_bytes for row in rows.values()} == {0}


def test_a_task_that_reads_its_folder_downloads_it_in_one_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The compaction reads what it owns, so that folder arrives whole, and nothing else does."""
    origin, shard, settings = a_shard(tmp_path, monkeypatch)

    outcome, rows, said, downloads = landed(
        ("compact-gardener", "old-days"), settings, shard, origin, monkeypatch
    )

    assert outcome.exit_code == EXIT_OK, said
    assert downloads == 1
    assert (shard / COMPACTED).is_file()
    assert not (shard / "state" / "old-days").exists(), "a folder nobody read was checked out"
    assert {row.downloaded_bytes for row in rows.values()} == {len(FILES[COMPACTED])}
    assert on_origin(origin, "state/compact/gardener/2026-09-27.summary") is not None
    assert on_origin(origin, AGED) is None


def test_a_listing_github_cannot_size_runs_no_task_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A size nobody can give is refused rather than read as nothing, so no task runs on it."""
    origin, shard, settings = a_shard(tmp_path, monkeypatch)

    class MissingSize(OriginBlobs):
        def read(self, path: str) -> dict[str, Any]:
            return {}

    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        ("old-days",),
        settings=settings,
        repo_root=shard,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        package=a_package("garden_tasks_ok", monkeypatch),
        trees=MissingSize(origin),
        clock=lambda: WAKE,
        say=said.append,
    )

    assert (outcome.exit_code, outcome.record, outcome.landing) == (EXIT_TASK_FAILED, None, None)
    assert any(
        "could not be listed, so no task ran" in line and "did not report a size" in line
        for line in said
    ), said
    assert on_origin(origin, AGED) == FILES[AGED]


def test_a_deletion_the_commit_never_listed_lands_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A task that walked the disk took a file nobody committed, so its shard lands nothing."""
    quiet_git(tmp_path, monkeypatch)
    origin, checkout = an_origin(tmp_path, FILES)
    declared = a_config(checkout, GARDENER_FIXTURES / "runner" / "old-days.json")
    settings = config.load_gardener(declared)
    uncommitted = checkout / "state" / "old-days" / "2026-09-18.txt"
    uncommitted.write_text("left here\n", encoding="ascii")

    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        ("old-days",),
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        package=a_package("garden_tasks_disk", monkeypatch),
        clock=lambda: WAKE,
        say=said.append,
    )

    assert outcome.exit_code == EXIT_INTEGRITY
    assert (
        "shard 0: state/old-days/2026-09-18.txt was deleted, and the commit this shard read "
        "lists no such file. Nothing lands"
    ) in said
    assert on_origin(origin, AGED) == FILES[AGED], "a deletion landed"
