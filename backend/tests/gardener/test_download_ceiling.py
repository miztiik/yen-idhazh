"""Does a shard say what its tasks downloaded, and does a compaction choose only what fits?

A real shard tests the aggregate ceiling and records what it downloaded even
when it exceeded the limit. The compaction tests decide what fits from listed
file sizes: a period that needs another wake waits, and one that can never fit
is a named manual action.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.gardener_events import DownloadOverBudget
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener import runner
from idhazh.gardener.file_listing import FileListing, TreeEntry
from idhazh.gardener.ledger_marks import name_marks
from idhazh.gardener.outcome import EXIT_OK, EXIT_TASK_FAILED
from idhazh.gardener.tasks._compact_tree import CompactTree, PeriodFetch, Stop
from idhazh.site_weight import BYTES_PER_MB
from utilities import gardener_publish

from ._events import the_event
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
    knobs = json.loads((config_dir / "gardener/config/idhazh_gardener.json").read_text(encoding="utf-8"))
    (config_dir / "gardener/config/idhazh_gardener.json").write_text(
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
    assert f"over max_downloaded_mb {CEILING_MB} in config/gardener/config/idhazh_gardener.json" in line
    assert (
        "The heaviest: state/compact/gardener 1.0 MB, state/old-days 0.0 MB, "
        "state/rehearsal 0.0 MB." in line
    )
    assert "a task downloaded without choosing by it, which is a code defect" in line


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


# --- a compaction chooses only what fits the shard's budget -------------------------

PACKED: Final = LedgerName.VISUAL_PRUNES


def a_tree_of_raw_days(tmp_path: Path, sizes: dict[str, int]) -> CompactTree:
    """A pass's view of raw days a commit lists, one file a day of these sizes, none downloaded."""
    raw = "state/raw/visual-prunes"
    marks = [
        path.relative_to(tmp_path).as_posix()
        for path in name_marks(tmp_path / ledger.STATE_DIRNAME, PACKED)
    ]
    listing = FileListing.from_commit(
        tmp_path,
        [raw, "state/compact/visual-prunes"],
        [
            TreeEntry(
                path=f"{raw}/{day.replace('-', '/')}/a.parquet", blob=f"{number:040x}", size=size
            )
            for number, (day, size) in enumerate(sizes.items(), start=1)
        ],
        {},
        paths=[*marks, f"{raw}/2026/09"],
        widen=lambda _: None,
        budget=CEILING_MB * BYTES_PER_MB,
    )
    return CompactTree.read(tmp_path / ledger.STATE_DIRNAME, PACKED, listing)


def test_a_step_takes_the_periods_that_fit_and_stops_at_the_first_that_does_not(
    tmp_path: Path,
) -> None:
    """Read off the listing's sizes: 800,000 bytes fit 1 MiB, and 1,200,000 do not."""
    tree = a_tree_of_raw_days(
        tmp_path, dict.fromkeys(("2026-09-20", "2026-09-21", "2026-09-22"), 400_000)
    )

    fits, over = tree.fit_to_budget(
        ["2026-09-20", "2026-09-21", "2026-09-22", "2026-09-23"],
        lambda day: PeriodFetch(folders=(tree.raw_day_folder(day),)),
    )

    assert (fits, over) == (["2026-09-20", "2026-09-21"], Stop(StopReason.CEILING, "2026-09-22"))


def test_a_file_two_periods_fetch_counts_once(tmp_path: Path) -> None:
    tree = a_tree_of_raw_days(tmp_path, {"2026-09-20": 900_000})
    month = tree.raw_month_folder("2026-09")

    fits, over = tree.fit_to_budget(
        ["2026-09-20", "2026-09-21"], lambda _day: PeriodFetch(folders=(month,))
    )

    assert (fits, over) == (["2026-09-20", "2026-09-21"], None)


def test_a_period_larger_than_the_whole_budget_is_refused_by_name(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    tree = a_tree_of_raw_days(tmp_path, {"2026-09-20": BYTES_PER_MB + 1})

    with caplog.at_level(logging.ERROR):
        fits, over = tree.fit_to_budget(
            ["2026-09-20"], lambda day: PeriodFetch(folders=(tree.raw_day_folder(day),))
        )

    assert (fits, over) == (
        [],
        Stop(StopReason.FAILED, "2026-09-20", GardenerFault.MANUAL_ACTION),
    )
    assert the_event(caplog.records, DownloadOverBudget) == DownloadOverBudget(
        ledger=PACKED,
        resume_from="2026-09-20",
        needed_bytes=BYTES_PER_MB + 1,
        room_bytes=CEILING_MB * BYTES_PER_MB,
        max_downloaded_mb=CEILING_MB,
        stopped_because=StopReason.FAILED,
    )
