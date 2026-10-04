"""Does a shard say what its tasks downloaded, and say so when that passes the ceiling?

Read the way a wake reads it: a partial clone of a real origin, whose one task
that reads content fetches the folder it owns, built to hold exactly the
ceiling, one byte under it and one byte over it. The ceiling is an alarm rather
than a gate: a shard over it still runs every task and lands its record, and
then exits 1. Every row records what the shard downloaded. A scheduled pass
does not read whole folders just to weigh them.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.gardener import runner
from idhazh.gardener.outcome import EXIT_OK, EXIT_TASK_FAILED
from idhazh.site_weight import BYTES_PER_MB
from utilities import gardener_publish

from ._garden import (
    GARDENER_FIXTURES,
    OriginBlobs,
    a_config,
    a_partial_clone,
    an_origin,
    git,
    on_origin,
    quiet_git,
)
from ._garden import task_package as a_package

WAKE: Final = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)
RUN_ID: Final = "2026-09-27-18012345678"
NAMES: Final = ("compact-gardener", "old-days", "rehearsal")

#: The ceiling the fixture config sets, so a download that reaches it stays small.
CEILING_MB: Final = 1

#: A day the live retention task takes by its name, which is never downloaded.
AGED_DAY: Final = "state/old-days/2026/09/19/2026-09-19.txt"
AGED_BYTES: Final = 600_000
#: What the rehearsal owns, which it decides on by name as well.
REHEARSED: Final = "state/rehearsal/2026/09/19/2026-09-19.txt"
#: The two files the compaction reads, one of them sized to put the download
#: exactly at, under or over the ceiling.
KEEP: Final = "state/compact/gardener/monthly/2025/08.json"
KEEP_BYTES: Final = 100
VARIED: Final = "state/compact/gardener/monthly/2025/08.parquet"


def a_garden_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, total: int
) -> tuple[Path, Path, GardenerSettings]:
    """The runner's fixture garden in a shard's clone, whose compaction reads `total` bytes."""
    quiet_git(tmp_path, monkeypatch)
    origin, _ = an_origin(
        tmp_path,
        {
            AGED_DAY: "a" * AGED_BYTES,
            REHEARSED: "rehearsed\n",
            KEEP: "k" * KEEP_BYTES,
            VARIED: "r" * (total - KEEP_BYTES),
        },
    )
    shard = a_partial_clone(tmp_path, origin, "config")
    config_dir = a_config(shard, GARDENER_FIXTURES / "runner")
    knobs = json.loads((config_dir / "idhazh_gardener.json").read_text(encoding="utf-8"))
    (config_dir / "idhazh_gardener.json").write_text(
        json.dumps(knobs | {"max_downloaded_mb": CEILING_MB}), encoding="ascii"
    )
    return origin, shard, config.load_gardener(config_dir)


def landed(
    origin: Path, shard: Path, settings: GardenerSettings, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, list[CollectionPruneRow], list[str], str]:
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        NAMES,
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
    assert outcome.record is not None, "the shard wrote no record"
    rows = ledger.load([outcome.record], model=CollectionPruneRow)
    return outcome.exit_code, rows, said, outcome.record.relative_to(shard).as_posix()


@pytest.mark.parametrize(
    ("offset", "code"), [(-1, EXIT_OK), (0, EXIT_OK), (1, EXIT_TASK_FAILED)]
)
def test_a_shard_at_under_and_over_its_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offset: int, code: int
) -> None:
    """One byte either side of the line, and the line itself, which is inside it."""
    total = CEILING_MB * BYTES_PER_MB + offset
    origin, shard, settings = a_garden_downloading(tmp_path, monkeypatch, total)

    exit_code, rows, said, record = landed(origin, shard, settings, monkeypatch)

    assert exit_code == code
    assert {row.task for row in rows} == set(NAMES), "a task did not run"
    assert {row.downloaded_bytes for row in rows} == {total}, "a row misses what was downloaded"
    assert {row.cone_bytes for row in rows} == {None}, "a fixed-window shard reads no whole-tree weight"
    assert on_origin(origin, record) is not None, "the record did not land"
    assert on_origin(origin, AGED_DAY) is None, "the live task's deletion did not land"
    over = [line for line in said if "over max_downloaded_mb" in line]
    if code == EXIT_OK:
        assert not over
        return
    (line,) = over
    assert line.startswith(f"shard 0: its tasks downloaded 1.0 MB ({total:,} bytes)")
    assert f"over max_downloaded_mb {CEILING_MB} in config/idhazh_gardener.json" in line
    assert (
        "The heaviest: state/compact/gardener 1.0 MB, state/old-days 0.0 MB, "
        "state/rehearsal 0.0 MB." in line
    )


def test_the_listing_is_read_off_the_commit_and_not_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file nobody committed is not listed, even inside a named day, and each file has git's size."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {AGED_DAY: "a" * 10, KEEP: "k" * 3})
    named_day = AGED_DAY.rsplit("/", 1)[0]
    (checkout / named_day / "never-committed.bin").write_bytes(b"x" * 5000)

    listing = gardener_publish.read_the_listing(
        gardener_publish.Checkout(checkout),
        checkout,
        ["state/compact/gardener", "state/old-days", "state/rehearsal"],
        [named_day, KEEP],
        None,
    )

    assert dict(listing.sizes) == {KEEP: 3, AGED_DAY: 10}


def test_a_hand_run_reads_no_commit_and_records_no_weight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`idhazh gardener run-task` starts no process, so nothing is weighed or downloaded."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {AGED_DAY: "a" * 10, KEEP: "k" * (BYTES_PER_MB + 1)})
    config_dir = a_config(checkout, GARDENER_FIXTURES / "runner")

    outcome = runner.run(
        NAMES,
        settings=config.load_gardener(config_dir),
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha=git(checkout, "rev-parse", "HEAD").strip(),
        committed_folders=None,
        cone_bytes=None,
        listing=None,
        package=a_package("garden_tasks_ok", monkeypatch),
        clock=lambda: WAKE,
        say=lambda _: None,
    )

    assert outcome.exit_code == EXIT_OK
    assert outcome.record is not None
    rows = ledger.load([outcome.record], model=CollectionPruneRow)
    assert {(row.cone_bytes, row.downloaded_bytes) for row in rows} == {(None, None)}


def test_the_heaviest_folders_are_named_heaviest_first_and_ties_by_name() -> None:
    weights = {"state/b": 3 * BYTES_PER_MB, "state/a": 3 * BYTES_PER_MB, "state/c": 1, "state/d": 2}

    said = runner.over_the_ceiling(weights, ceiling_mb=5, shard=4)

    assert said is not None and said.startswith("shard 4: its tasks downloaded 6.0 MB")
    assert "The heaviest: state/a 3.0 MB, state/b 3.0 MB, state/d 0.0 MB." in said
    assert runner.over_the_ceiling(weights, ceiling_mb=7, shard=4) is None
