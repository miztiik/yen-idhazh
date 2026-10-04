"""Does packing leave what a live compaction leaves, including after a late file?"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import pytest
from conftest import SEED_COMMIT
from gardener.tasks._task import declared as task_declarations

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import compaction
from utilities.ledger_migration import (
    csv_files,
    csv_layouts,
)
from utilities.ledger_migration.identity import writer_identity

from ._fixtures import (
    FIRST,
    ITEM,
    MONTHS,
    OLD,
    ROWS,
    RUN,
    item_row,
    run_migration,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


@dataclass(frozen=True, slots=True)
class _Packed:
    """What packing left for one ledger, less what names who packed it and when.

    Each daily file's path, row count, source count, content digest and rows
    beside the identity their raw file gave them; the daily watermark's day; and
    the raw days still waiting and the days listed. A file's envelope also names
    its writer and the instant it was written, which two writers never share.
    """

    daily: dict[str, tuple[object, ...]]
    through: str
    monthly: bool
    raw: list[str]
    listed: list[str]


def _packed(state: Path, which: LedgerName) -> _Packed:
    model = ROWS[which]
    index = CompactIndex.read(ledger.compact_index_path(state, which, Period.DAILY))
    daily: dict[str, tuple[object, ...]] = {}
    for entry in index.entries:
        found = ledger.compact_file(state, which, Period.DAILY, entry.covers)
        assert found is not None and found.stat().st_size == entry.bytes
        envelope = ledger.read_envelope(found)
        stored = ledger.load_stored([found], model=model)
        daily[entry.covers] = (
            found.relative_to(state).as_posix(),
            entry.rows,
            envelope.built_from,
            envelope.content_sha256,
            [(held.identity, held.row) for held in stored],
        )
    return _Packed(
        daily=daily,
        through=Watermark.read(ledger.watermark_path(state, which, Period.DAILY)).through,
        monthly=ledger.compact_index_path(state, which, Period.MONTHLY).exists(),
        raw=ledger.raw_days(state, which),
        listed=ledger.listed_days(state, which),
    )


def _live(root: Path, which: LedgerName, today: date) -> TaskContext:
    """What the gardener hands this ledger's declared compaction over `root`, turned live."""
    declared = task_declarations()[f"compact-{which.value}"]
    assert isinstance(declared, CompactionPolicy)
    return TaskContext(
        state_dir=root / ledger.STATE_DIRNAME,
        repo_root=root,
        today=today,
        policy=declared.model_copy(update={"dry_run": False}),
        run_id=RUN,
        attempt=1,
        job=ServerJob.RUN_TASKS,
        shard=0,
        git_sha=SEED_COMMIT,
        owned_folders=tuple(declared.owns),
        listing=FileListing.from_disk(
            root,
            declared.owns,
            paths=(root / folder for folder in declared.owns),
        ),
    )


def test_packing_leaves_what_a_live_compaction_leaves_over_the_same_raw_files(
    tmp_path: Path,
) -> None:
    """The migration packs with the compaction's own daily step and the declared policy.

    Both trees get the same raw files: one a CSV day, filed under the
    migration's own writer. The declared compaction turned live then leaves the
    same daily files, index and watermark, so a compaction turned on after the
    move resumes from the right day. It takes two wakes where the migration takes
    one pass, because its declared budget is eight days a wake and the
    migration's is every day the rule admits: that changes when a day is packed,
    never what it holds. A first packing starts on the first of the month, so
    the days no CSV held are packed empty; yesterday and today stay raw.
    """
    today = date(2026, 9, 12)
    days = ("2026-09-02", "2026-09-05", "2026-09-10", "2026-09-11", "2026-09-12")
    migrated, live = tmp_path / "migrated", tmp_path / "live"
    for root in (migrated, live):
        for number, day in enumerate(days):
            row = item_row(day, f"ai-{number:02d}", machine=False)
            write_csv(root / "state", ITEM, day, writer_file_name(day, 1, ServerJob.ASSEMBLE), [row.csv_row()])

    run_migration(migrated / "state", ITEM, today=today)
    model, key = ROWS[ITEM], ledger.door_key(ITEM)
    identity = writer_identity(RUN, SEED_COMMIT)
    for day in days:
        cells = day_shards.settled_day(
            csv_layouts.csv_root(live / "state", ITEM),
            day,
            key,
            cast("type[ledger.CsvContract]", model),
        )
        rows = [model.from_csv_row(each) for each in cells]
        ledger.persist(live / "state", rows, ledger=ITEM, covers=day, identity=identity)
    wakes = [compaction.run(_live(live, ITEM, today)) for _ in range(2)]

    assert [wake.stopped_because for wake in wakes] == [StopReason.CEILING, StopReason.EXHAUSTED]
    packed = _packed(migrated / "state", ITEM)
    assert packed == _packed(live / "state", ITEM)
    assert list(packed.daily) == [f"2026-09-{number:02d}" for number in range(1, 11)]
    assert (packed.through, packed.raw) == ("2026-09-10", ["2026-09-11", "2026-09-12"])


def test_a_late_file_for_a_moved_day_is_folded_in_packed_again_and_proven(tmp_path: Path) -> None:
    """A run started before the merge can push its CSV file after the move.

    Its day was already moved and packed. The next run folds the file onto what
    the door holds, files the answer under the migration's own work unit, packs
    the day again and proves it; the watermark stays where it was. A run with
    nothing new in between moves nothing.
    """
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    (first,) = run_migration(state, ITEM)
    (again,) = run_migration(state, ITEM)

    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 2, ServerJob.WORK),
        [item_row(OLD, "ai-04", machine=True).csv_row()],
    )
    (late,) = run_migration(state, ITEM)

    assert first.packed == [FIRST, OLD]
    assert (again.days, again.filed, again.packed) == (0, 0, [])
    assert (late.days, late.filed, late.packed) == (1, 1, [OLD])
    held = ledger.load_days(state, ITEM, [OLD], model=ItemHealthRow)
    assert sorted(row.item_id for row in held) == ["ai-01", "ai-04"]
    index = CompactIndex.read(ledger.compact_index_path(state, ITEM, Period.DAILY))
    assert {entry.covers: entry.rows for entry in index.entries} == {FIRST: 0, OLD: 2}
    assert ledger.raw_days(state, ITEM) == [], "the day's new raw file was packed in"
    assert Watermark.read(ledger.watermark_path(state, ITEM, Period.DAILY)).through == OLD
    assert not csv_files.left(state, [ITEM], months=MONTHS)
