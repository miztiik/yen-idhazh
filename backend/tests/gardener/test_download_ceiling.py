"""Does a shard say what its tasks downloaded, and does a compaction choose only what fits?

Read the way a wake reads it: a partial clone of a real origin, whose one task
that reads content fetches the folder it owns, built to hold exactly the
ceiling, one byte under it and one byte over it. A shard over the ceiling still
runs every task and lands its record, then exits 1, and says that is a code
defect: the shipped compaction takes a period only while what it downloads
fits what is left of the shard's budget, so it stops at `ceiling` and never
passes it, and refuses by name a period larger than the whole budget. Every row
records what the shard downloaded. A scheduled pass does not read whole folders
just to weigh them.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.gardener_events import DownloadOverBudget
from idhazh.contracts.gardener_fault import GardenerFault
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener import runner
from idhazh.gardener.file_listing import FileListing, TreeEntry
from idhazh.gardener.ledger_marks import name_marks
from idhazh.gardener.outcome import EXIT_OK, EXIT_TASK_FAILED, Outcome
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

#: The ledger the shipped compaction packs live in these cases, and its task.
PACKED: Final = LedgerName.VISUAL_PRUNES
PACKING: Final = "compact-visual-prunes"

#: Rows that make one raw day weigh about 400 KB: two such days fit 1 MiB, three do not.
ROWS_A_DAY: Final = 14_000

#: Rows that make one raw day weigh more than the whole 1 MiB budget.
ROWS_PAST_THE_BUDGET: Final = 40_000


def a_raw_day(state_dir: Path, day: str, rows: int) -> Path:
    """One writer's raw file for `day`, through the door, its cells drawn from a seed fixed per day.

    Drawn values do not compress, so the file weighs about 28 bytes a row.
    """
    pick = random.Random(day)
    filed: list[VisualPruneRow] = []
    for _ in range(rows):
        weighed = pick.randrange(1 << 40)
        filed.append(
            VisualPruneRow(
                version=VisualPruneRow.schema_version(),
                date=day,
                run_id=f"{day}-1",
                policy_months=-1,
                max_deletes_per_run=200,
                dry_run=True,
                candidates_found=pick.randrange(1 << 40),
                deleted=0,
                skipped_by_fuse=0,
                fuse_tripped=False,
                bytes_reclaimed=0,
                oldest_kept=None,
                payload_bytes_before=weighed,
                payload_bytes_after=weighed,
            )
        )
    (written,) = ledger.persist(
        state_dir,
        filed,
        ledger=PACKED,
        covers=day,
        identity=WriterIdentity(
            run_id=f"{day}-1",
            attempt=1,
            job=ServerJob.RUN_TASKS,
            shard=0,
            producer="gardener.tasks.visual_prune",
            git_sha="a" * 40,
        ),
    )
    return written


def raw_days_on_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows_by_day: dict[str, int]
) -> tuple[Path, Path, dict[str, str]]:
    """An origin holding one raw file a day for these days, its seeding clone, and each file's path."""
    quiet_git(tmp_path, monkeypatch)
    origin, seeder = an_origin(tmp_path, {".gitattributes": "* text=auto eol=lf\n"})
    files = {
        day: a_raw_day(seeder / ledger.STATE_DIRNAME, day, rows).relative_to(seeder).as_posix()
        for day, rows in rows_by_day.items()
    }
    git(seeder, "add", "--all")
    git(seeder, "commit", "--quiet", "-m", "raw days")
    git(seeder, "push", "--quiet", "origin", "HEAD:refs/heads/main")
    return origin, seeder, files


def packed_by_a_shard(
    tmp_path: Path, origin: Path, said: list[str]
) -> tuple[Outcome, CollectionPruneRow]:
    """The shipped compaction run live in a shard's partial clone with a 1 MiB budget, and landed."""
    shard = a_partial_clone(tmp_path, origin, "config")
    declaration = tmp_path / f"{PACKING}.json"
    committed = json.loads(read_text(CONFIG_DIR / "gardener" / f"{PACKING}.json"))
    declaration.write_text(json.dumps(committed | {"dry_run": False}), encoding="ascii")
    config_dir = a_config(shard, declaration)
    knobs = json.loads((config_dir / "idhazh_gardener.json").read_text(encoding="utf-8"))
    (config_dir / "idhazh_gardener.json").write_text(
        json.dumps(knobs | {"max_downloaded_mb": CEILING_MB}), encoding="ascii"
    )
    outcome = gardener_publish.run_and_land(
        (PACKING,),
        settings=config.load_gardener(config_dir),
        repo_root=shard,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        trees=OriginBlobs(origin),
        clock=lambda: WAKE,
        say=said.append,
    )
    assert outcome.record is not None, "the shard wrote no record"
    (row,) = ledger.load([outcome.record], model=CollectionPruneRow)
    return outcome, row


def test_a_compaction_takes_only_the_days_its_shard_s_budget_holds_and_never_passes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE ORACLE for the budget: three raw days of about 400 KB each against 1 MiB.

    The first wake packs from the oldest raw day. The day step takes the two
    days that fit and stops at `ceiling` on the third, so the shard downloads
    less than its budget, never says it went over, and lands the two days it
    packed. The third stays raw for a wake with room.
    """
    days = ("2026-09-20", "2026-09-21", "2026-09-22")
    origin, seeder, files = raw_days_on_origin(
        tmp_path, monkeypatch, dict.fromkeys(days, ROWS_A_DAY)
    )
    weights = [(seeder / path).stat().st_size for path in files.values()]
    assert all(BYTES_PER_MB // 3 < weight < BYTES_PER_MB // 2 for weight in weights), (
        "each raw day must weigh between a third and a half of the budget"
    )
    said: list[str] = []

    outcome, row = packed_by_a_shard(tmp_path, origin, said)

    assert outcome.exit_code == EXIT_OK, said
    assert (row.stopped_because, row.resume_from) == (StopReason.CEILING, "2026-09-22")
    assert row.downloaded_bytes is not None
    assert row.downloaded_bytes <= CEILING_MB * BYTES_PER_MB
    assert not [line for line in said if "over max_downloaded_mb" in line]
    packed = "state/compact/visual-prunes/daily/2026/09"
    assert on_origin(origin, f"{packed}/20.parquet") is not None
    assert on_origin(origin, f"{packed}/21.parquet") is not None
    assert on_origin(origin, f"{packed}/22.parquet") is None
    assert on_origin(origin, files["2026-09-20"]) is None, "a packed day's raw file stayed"
    assert on_origin(origin, files["2026-09-22"]) is not None, "the day past the budget went"


def test_a_day_larger_than_the_whole_budget_is_refused_by_name_and_never_downloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """No wake could take it, so it fails by name for a person to raise the budget."""
    origin, seeder, files = raw_days_on_origin(
        tmp_path, monkeypatch, {"2026-09-20": ROWS_PAST_THE_BUDGET}
    )
    assert (seeder / files["2026-09-20"]).stat().st_size > CEILING_MB * BYTES_PER_MB
    said: list[str] = []

    with caplog.at_level(logging.ERROR):
        outcome, row = packed_by_a_shard(tmp_path, origin, said)

    assert outcome.exit_code == EXIT_TASK_FAILED, said
    assert (row.stopped_because, row.resume_from, row.fault) == (
        StopReason.FAILED,
        "2026-09-20",
        GardenerFault.RAISED,
    )
    assert row.downloaded_bytes == 0
    refusal = the_event(caplog.records, DownloadOverBudget)
    assert (refusal.resume_from, refusal.stopped_because, refusal.max_downloaded_mb) == (
        "2026-09-20",
        StopReason.FAILED,
        CEILING_MB,
    )
    assert refusal.needed_bytes > CEILING_MB * BYTES_PER_MB
    assert on_origin(origin, files["2026-09-20"]) is not None


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

    assert (fits, over) == ([], Stop(StopReason.FAILED, "2026-09-20", GardenerFault.RAISED))
    assert the_event(caplog.records, DownloadOverBudget) == DownloadOverBudget(
        ledger=PACKED,
        resume_from="2026-09-20",
        needed_bytes=BYTES_PER_MB + 1,
        room_bytes=CEILING_MB * BYTES_PER_MB,
        max_downloaded_mb=CEILING_MB,
        stopped_because=StopReason.FAILED,
    )
