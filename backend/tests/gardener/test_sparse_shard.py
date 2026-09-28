"""Does a shard's sparse checkout hold every folder its tasks walk, the complement's included?

A wake's shard is a depth-1 clone that downloads no file outside its cone, and
the plan job can put in that cone only the folders a declaration names. The one
task that owns everything else under `state` sweeps folders only the commit can
name, so `backend/utilities/gardener_publish.py` adds them to the checkout before
anything runs. These tests clone the way a wake clones - a partial clone of a
`file://` origin, which a plain local clone would not be, because a local clone
copies every file and would hide a folder the shard never downloaded.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.gardener.outcome import EXIT_OK, EXIT_TASK_FAILED, Outcome
from utilities import gardener_publish

from ._garden import GARDENER_FIXTURES, a_config, an_origin, git, on_origin, quiet_git
from ._garden import task_package as a_package

pytestmark = pytest.mark.slow

WAKE: Final = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID: Final = "2026-09-27-18012345678"

#: A day `old-days` has aged out, and one it keeps.
AGED: Final = "state/old-days/2026-09-01.txt"
FRESH: Final = "state/old-days/2026-09-26.txt"
#: A folder no declaration names and no ledger claims, so the complement sweeps it.
STRAY: Final = "state/a-trial-run/2026-05-01.txt"

#: Every file holds different bytes: git stores equal files as one object, and a
#: folder outside the cone whose file matched one inside it would be in the
#: clone after all.
FILES: Final = {
    AGED: "aged\n",
    FRESH: "fresh\n",
    "state/rehearsal/2026-09-01.txt": "rehearsed\n",
    STRAY: "a trial run\n",
}


def a_shard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cone: tuple[str, ...]
) -> tuple[Path, Path, GardenerSettings]:
    """An origin holding `FILES`, and a shard's clone of it that holds only `cone`."""
    quiet_git(tmp_path, monkeypatch)
    origin, _ = an_origin(tmp_path, FILES)
    git(origin, "config", "uploadpack.allowFilter", "true")
    git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    shard = tmp_path / "shard"
    git(
        tmp_path,
        "clone",
        "--quiet",
        "--filter=blob:none",
        "--depth=1",
        "--sparse",
        origin.as_uri(),
        str(shard),
    )
    git(shard, "sparse-checkout", "set", "--cone", *cone)
    git(shard, "config", "index.sparse", "true")
    declared = a_config(
        shard, GARDENER_FIXTURES / "runner", GARDENER_FIXTURES / "garden" / "trials.json"
    )
    return origin, shard, config.load_gardener(declared)


def landed(
    names: tuple[str, ...],
    settings: GardenerSettings,
    checkout: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Outcome, dict[str, CollectionPruneRow], list[str]]:
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        names,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        package=a_package("garden_tasks_ok", monkeypatch),
        clock=lambda: WAKE,
        say=said.append,
    )
    assert outcome.record is not None, "the shard wrote no record"
    rows = {row.task: row for row in ledger.load([outcome.record], model=CollectionPruneRow)}
    return outcome, rows, said


def test_a_sparse_shard_adds_the_folders_the_complement_sweeps_then_weighs_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The plan's cone holds `old-days` alone; the stray folder arrives before the tasks run."""
    origin, shard, settings = a_shard(tmp_path, monkeypatch, ("state/old-days",))
    assert not (shard / "state" / "a-trial-run").exists(), "the clone already held the folder"

    outcome, rows, said = landed(("old-days", "trials"), settings, shard, monkeypatch)

    assert outcome.exit_code == EXIT_OK, said
    assert "shard 0: added state/a-trial-run to the checkout" in said
    assert (rows["trials"].stopped_because, rows["trials"].selected) == (StopReason.EXHAUSTED, 1)
    weighed = len(FILES[AGED]) + len(FILES[FRESH]) + len(FILES[STRAY])
    assert {row.cone_bytes for row in rows.values()} == {weighed}, "a swept folder was not weighed"
    assert on_origin(origin, AGED) is None, "the live task's deletion did not land"
    assert on_origin(origin, STRAY) == FILES[STRAY], "a dry run deleted a file"


def test_a_declared_folder_the_sparse_checkout_lacks_is_not_added_and_its_task_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A declared folder outside the cone means the plan was wrong, so it stays red.

    Its files are not in the clone, so it is weighed as nothing rather than
    downloaded to be weighed.
    """
    _, shard, settings = a_shard(tmp_path, monkeypatch, ("state/old-days",))

    outcome, rows, said = landed(("old-days", "rehearsal"), settings, shard, monkeypatch)

    assert outcome.exit_code == EXIT_TASK_FAILED
    assert rows["rehearsal"].stopped_because is StopReason.FAILED
    assert rows["old-days"].stopped_because is StopReason.EXHAUSTED
    assert not (shard / "state" / "rehearsal").exists(), "a declared folder was added"
    assert not [line for line in said if "to the checkout" in line]
    weighed = len(FILES[AGED]) + len(FILES[FRESH])
    assert {row.cone_bytes for row in rows.values()} == {weighed}


def test_a_full_checkout_that_lacks_a_swept_folder_still_fails_the_complement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a sparse checkout is widened; a full one that lost a folder is a wrong checkout."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, FILES)
    settings = config.load_gardener(
        a_config(
            checkout, GARDENER_FIXTURES / "runner", GARDENER_FIXTURES / "garden" / "trials.json"
        )
    )
    shutil.rmtree(checkout / "state" / "a-trial-run")

    outcome, rows, said = landed(("trials",), settings, checkout, monkeypatch)

    assert outcome.exit_code == EXIT_TASK_FAILED
    assert rows["trials"].stopped_because is StopReason.FAILED
    assert not [line for line in said if "to the checkout" in line]
