"""Does the one-shot migration move every row today's CSV reader returns, and nothing else?

Each case builds a small CSV day tree under `tmp_path` the way the retired
writers filed one - one file per writer, `<run_id>-<attempt>-<job>-<shard>.csv`,
beside the reserved `settled.csv` and `before-partition.csv` - and runs the
migration over it. "Every row" is what today's CSV reader,
`day_shards.settled_day`, returns for a day, read before the migration deletes
the files: a re-run's superseded attempt is not one of those rows. Nothing here
reads the committed `state/` (CLAUDE.md section 13): the parity run over the
committed tree is an operator's one-off, and its figures are in the pull request
that carried the move.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, SEED_COMMIT
from gardener._garden import a_config

from idhazh import config, day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.eval_row import DROPPED_CELLS as DROPPED_EVAL_CELLS
from idhazh.contracts.eval_row import RENAMED_CELLS, EvalRow
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import DROPPED_CELLS, MACHINE_CELLS_RENAMED, ItemHealthRow
from idhazh.contracts.knobs.gardener import CompactionPolicy, ForeverWindow, RetentionPolicy
from idhazh.contracts.ledger_index import CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import compaction
from idhazh.ledger import json_lines, parquet, render_file
from utilities import migrate_to_parquet as migration

pytestmark = pytest.mark.contract

#: A day old enough to pack, and the day after it, which the rule does not admit yet.
OLD: Final = "2026-09-02"
NEW: Final = "2026-09-03"
#: The first day of their month. A first packing starts there, so it is packed too, empty.
FIRST: Final = "2026-09-01"
#: The wake the migration runs on: a day is packed once a whole day has passed after it.
TODAY: Final = date(2026, 9, 4)
RUN: Final = "2026-09-29-9001"
ITEM: Final = LedgerName.ITEM_HEALTH
EVALS: Final = LedgerName.SUMMARY_QUALITY_EVALS
HOST: Final = LedgerName.HOST_FINGERPRINT
#: The ledgers these cases build CSV trees for, each filed through the door.
MOVED: Final = (ITEM, EVALS, HOST)
#: Each one's row contract, the one the door table pairs it with.
ROWS: Final[dict[LedgerName, type[ItemHealthRow | EvalRow | HostFingerprintRow]]] = {
    ITEM: ItemHealthRow,
    EVALS: EvalRow,
    HOST: HostFingerprintRow,
}
#: A ledger the registry still files as CSV, whose CSV tree a case builds.
ON_CSV: Final = LedgerName.FEED_HEALTH

type Cells = dict[str, str]
type ByKey = dict[tuple[str, ...], Cells]


def _fixture(folder: str, name: str) -> str:
    return (CONTRACT_FIXTURES_DIR / folder / name).read_text(encoding="utf-8")


def _item(day: str, item: str, *, machine: bool, words: int = 120) -> ItemHealthRow:
    """One item-health row, from the committed fixture, filed for `day`."""
    base = ItemHealthRow.model_validate_json(_fixture("item-health-row", "published.json"))
    return ItemHealthRow.model_validate(
        {
            **base.model_dump(),
            "date": day,
            "run_id": f"{day}-100",
            "item_id": item,
            "source_words": words,
            "machine_job": ServerJob.WORK if machine else None,
            "machine_shard": 0 if machine else None,
        }
    )


def _score(day: str, number: int, **changed: Any) -> EvalRow:
    """One eval row, from the committed fixture: the `number`th article measured on `day`."""
    base = EvalRow.model_validate_json(_fixture("eval-row", "high.json"))
    return EvalRow.model_validate(
        {
            **base.model_dump(),
            "date": day,
            "run_id": f"{day}-100",
            "item_id": f"ai-{number:02d}",
            "url_key": hashlib.sha256(f"{day}/{number}".encode()).hexdigest(),
            **changed,
        }
    )


def _under_old_headings(row: EvalRow) -> Cells:
    """An eval row as a file written before the renames spelled it, a dropped column still in."""
    retired = {current: old for old, current in RENAMED_CELLS.items()}
    cells = {retired.get(name, name): value for name, value in row.csv_row().items()}
    return cells | dict.fromkeys(sorted(DROPPED_EVAL_CELLS), "0.5")


def _filled(row: HostFingerprintRow) -> Cells:
    """The cells a host row fills, less the schema stamp, which a join keeps from one side."""
    return {name: value for name, value in row.csv_row().items() if value and name != "version"}


def _clock(day: str, job: ServerJob = ServerJob.WORK) -> HostFingerprintRow:
    """The half of a job's host row written at the job's end: its time, and no machine."""
    base = HostFingerprintRow.model_validate_json(
        _fixture("host-fingerprint-row", "the-clock-a-job-kept.json")
    )
    return HostFingerprintRow.model_validate(
        {**base.model_dump(), "date": day, "run_id": f"{day}-100", "job": job, "shard": 0}
    )


def _probe(day: str, job: ServerJob = ServerJob.WORK) -> HostFingerprintRow:
    """The half written as the job starts: the machine, with every cell the clock fills empty."""
    base = HostFingerprintRow.model_validate_json(
        _fixture("host-fingerprint-row", "every-reading-taken.json")
    )
    clock = [name for name in _filled(_clock(day, job)) if name not in ledger.HOST_FINGERPRINT_KEY]
    return HostFingerprintRow.model_validate(
        {
            **base.model_dump(),
            "date": day,
            "run_id": f"{day}-100",
            "job": job,
            "shard": 0,
            **dict.fromkeys(clock),
        }
    )


def _writer(day: str, attempt: int, job: ServerJob) -> str:
    """A retired writer's file name for one day: `<run_id>-<attempt>-<job>-<shard>.csv`."""
    return ledger.segment_name(run_id=f"{day}-100", attempt=attempt, job=job, shard=0)


def _csv(
    state: Path,
    which: LedgerName,
    day: str,
    name: str,
    rows: Sequence[Cells],
    *,
    columns: tuple[str, ...] | None = None,
) -> Path:
    """One CSV file of one day, in the layout the retired writers used."""
    folder = migration.csv_root(state, which) / day[:4] / day[5:7] / day[8:10]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(render_file(columns or tuple(rows[0]), rows), encoding="utf-8", newline="")
    return path


def _by_key(which: LedgerName, rows: Sequence[Cells]) -> ByKey:
    key = ledger.door_key(which)
    return {tuple(cells[name] for name in key): cells for cells in rows}


def _todays_reader(state: Path, which: LedgerName) -> dict[str, ByKey]:
    """Every CSV day of a ledger, as today's CSV reader returns it."""
    root = migration.csv_root(state, which)
    return {
        day: _by_key(which, day_shards.settled_day(root, day, ledger.door_key(which), ROWS[which]))
        for day in migration.csv_days(state, which)
    }


def _read_back(state: Path, which: LedgerName, day: str) -> ByKey:
    """One day as the door serves it, from whichever file serves it."""
    rows = ledger.load_days(state, which, [day], model=ROWS[which])
    return _by_key(which, [row.csv_row() for row in rows])


def _hashes(root: Path) -> dict[str, str]:
    """Every file under a tree, by its path relative to the tree, to the digest of its bytes."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _stored(path: Path) -> list[dict[str, Any]]:
    """A ledger file's rows as stored, the door's own columns included."""
    data = path.read_bytes()
    return (parquet.read if data.startswith(b"PAR1") else json_lines.read)(data)[1]


def _beside(state: Path) -> Path:
    """A config folder beside this state tree, holding every committed declaration.

    Only the state tree beside its config folder is packed, so a case that wants
    packing builds one, as a checkout holds one beside `state/`.
    """
    return a_config(state.parent, CONFIG_DIR / "gardener")


def _run(state: Path, *which: LedgerName, today: date = TODAY) -> list[migration.Moved]:
    """The migration of these ledgers, run on the wake `today` with the committed declarations."""
    return migration.migrate(
        state, which, run_id=RUN, git_sha=SEED_COMMIT, today=today, config_dir=_beside(state)
    )


def test_every_row_todays_reader_returns_reads_back_and_every_csv_goes(tmp_path: Path) -> None:
    """All three ledgers, over every kind of file a CSV day held.

    A closed day's `settled.csv`, a committed head's `before-partition.csv`,
    writer files, a re-run's second attempt, a file under the eval ledger's old
    headings, and a closed day that held nothing. The door serves each day
    exactly as today's reader read it: no row lost, none invented, every cell
    equal. The old day is packed, with the first of its month before it as an
    empty day, and the new day stays a raw file.
    """
    state = tmp_path / "state"
    census = [_item(OLD, "ai-01", machine=False), _item(OLD, "ai-02", machine=False)]
    _csv(state, ITEM, OLD, day_shards.SETTLED_NAME, [row.csv_row() for row in census])
    _csv(state, ITEM, OLD, _writer(OLD, 1, ServerJob.WORK), [_item(OLD, "ai-01", machine=True).csv_row()])
    _csv(state, ITEM, NEW, ledger.BEFORE_PARTITION_NAME, [_item(NEW, "ai-03", machine=True).csv_row()])
    assembled = [_item(NEW, "ai-03", machine=False), _item(NEW, "ai-04", machine=False)]
    _csv(state, ITEM, NEW, _writer(NEW, 1, ServerJob.ASSEMBLE), [row.csv_row() for row in assembled])
    _csv(state, EVALS, OLD, day_shards.SETTLED_NAME, [_score(OLD, 1).csv_row()])
    _csv(state, EVALS, OLD, _writer(OLD, 1, ServerJob.WORK), [_score(OLD, 2, score_ms=100).csv_row()])
    _csv(state, EVALS, OLD, _writer(OLD, 2, ServerJob.WORK), [_score(OLD, 2, score_ms=200).csv_row()])
    _csv(state, EVALS, NEW, _writer(NEW, 1, ServerJob.WORK), [_under_old_headings(_score(NEW, 3))])
    _csv(state, HOST, FIRST, day_shards.SETTLED_NAME, [], columns=HostFingerprintRow.csv_columns())
    halves = [_probe(OLD).csv_row(), _clock(OLD).csv_row()]
    _csv(state, HOST, OLD, _writer(OLD, 1, ServerJob.WORK), halves)
    halves = [_probe(NEW, ServerJob.PLAN).csv_row(), _clock(NEW, ServerJob.PLAN).csv_row()]
    _csv(state, HOST, NEW, _writer(NEW, 1, ServerJob.PLAN), halves)
    wanted = {which: _todays_reader(state, which) for which in MOVED}
    lines = {
        which: sum(1 for path in migration.left(state, [which]) for _ in day_shards.rows_of(path))
        for which in MOVED
    }

    moved = {each.which: each for each in _run(state, *MOVED)}

    for which, days in wanted.items():
        assert moved[which].rows == sum(len(rows) for rows in days.values())
        for day, rows in days.items():
            assert _read_back(state, which, day) == rows, f"{which.value} {day}"
        assert moved[which].packed == [FIRST, OLD]
        assert ledger.raw_days(state, which) == [NEW]
        assert not migration.csv_root(state, which).exists(), (
            "every CSV file and emptied folder goes"
        )
    assert not migration.left(state, list(MOVED))
    item_key = (OLD, f"{OLD}-100", "ai-01")
    assert _read_back(state, ITEM, OLD)[item_key]["machine_job"] == ServerJob.WORK.value
    assert {cells["score_ms"] for cells in _read_back(state, EVALS, OLD).values()} == {"0", "200"}
    assert (lines[EVALS], moved[EVALS].rows) == (4, 3), "a re-run's first attempt is no row"
    assert list(_read_back(state, EVALS, NEW).values()) == [_score(NEW, 3).csv_row()]
    assert [len(wanted[HOST][day]) for day in (FIRST, OLD, NEW)] == [0, 1, 1]


def test_a_second_run_changes_no_byte(tmp_path: Path) -> None:
    """Over a migrated tree the migration finds nothing, so it writes, packs and deletes nothing.

    The second run is a week later, when the day the first run left raw is old
    enough to pack. Packing it is the compaction's job by then: the migration
    packs only in a run that moved a CSV day.
    """
    state = tmp_path / "state"
    _csv(state, ITEM, NEW, _writer(NEW, 1, ServerJob.ASSEMBLE), [_item(NEW, "ai-03", machine=False).csv_row()])
    _csv(state, EVALS, NEW, _writer(NEW, 1, ServerJob.WORK), [_score(NEW, 1).csv_row()])
    _csv(state, HOST, NEW, _writer(NEW, 1, ServerJob.WORK), [_probe(NEW).csv_row(), _clock(NEW).csv_row()])
    _run(state, *MOVED)
    before = _hashes(tmp_path)
    waiting = [ledger.raw_days(state, which) for which in MOVED]

    again = _run(state, *MOVED, today=date(2026, 9, 11))
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]

    assert [(each.days, each.filed, each.packed) for each in again] == [(0, 0, [])] * 3
    assert migration.main(argv) == migration.EXIT_MIGRATED
    assert _hashes(tmp_path) == before
    assert waiting == [[NEW]] * 3, "the day the second run could have packed is still raw"


def test_check_says_whether_a_csv_is_left_and_writes_nothing(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _csv(state, ITEM, NEW, _writer(NEW, 1, ServerJob.ASSEMBLE), [_item(NEW, "ai-03", machine=False).csv_row()])
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT, "--check"]
    before = _hashes(tmp_path)

    assert migration.main(argv) == migration.EXIT_NOT_PROVEN
    assert migration.main([*argv, "--ledger", EVALS.value]) == migration.EXIT_MIGRATED
    assert _hashes(tmp_path) == before, "a check writes nothing"
    _run(state, ITEM)
    assert migration.main(argv) == migration.EXIT_MIGRATED


def test_the_eval_ledgers_csv_tree_is_read_where_its_old_name_filed_it(tmp_path: Path) -> None:
    """A re-run of a commit from before the rename writes its CSV day under `scores/`.

    That tree is the one this moves for the eval ledger, whatever the ledger is
    called now, so a late CSV file still reaches the door under the new name.
    """
    state = tmp_path / "state"
    assert migration.csv_root(state, EVALS) == state / "scores"
    _csv(state, EVALS, NEW, _writer(NEW, 1, ServerJob.WORK), [_score(NEW, 1).csv_row()])

    (moved,) = _run(state, EVALS)

    assert (moved.days, moved.rows) == (1, 1)
    assert list(_read_back(state, EVALS, NEW).values()) == [_score(NEW, 1).csv_row()]
    assert not (state / "scores").exists()


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
    declared = config.load_gardener(CONFIG_DIR).tasks[f"compact-{which.value}"]
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
        owned_folders=tuple(declared.owns or ()),
        listing=FileListing.from_disk(root, declared.owns or ()),
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
            row = _item(day, f"ai-{number:02d}", machine=False)
            _csv(root / "state", ITEM, day, _writer(day, 1, ServerJob.ASSEMBLE), [row.csv_row()])

    _run(migrated / "state", ITEM, today=today)
    model, key = migration.LEDGERS[ITEM]
    identity = migration._identity(RUN, SEED_COMMIT)
    for day in days:
        cells = day_shards.settled_day(migration.csv_root(live / "state", ITEM), day, key, model)
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
    _csv(state, ITEM, OLD, _writer(OLD, 1, ServerJob.WORK), [_item(OLD, "ai-01", machine=True).csv_row()])
    (first,) = _run(state, ITEM)
    (again,) = _run(state, ITEM)

    _csv(state, ITEM, OLD, _writer(OLD, 2, ServerJob.WORK), [_item(OLD, "ai-04", machine=True).csv_row()])
    (late,) = _run(state, ITEM)

    assert first.packed == [FIRST, OLD]
    assert (again.days, again.filed, again.packed) == (0, 0, [])
    assert (late.days, late.filed, late.packed) == (1, 1, [OLD])
    held = ledger.load_days(state, ITEM, [OLD], model=ItemHealthRow)
    assert sorted(row.item_id for row in held) == ["ai-01", "ai-04"]
    index = CompactIndex.read(ledger.compact_index_path(state, ITEM, Period.DAILY))
    assert {entry.covers: entry.rows for entry in index.entries} == {FIRST: 0, OLD: 2}
    assert ledger.raw_days(state, ITEM) == [], "the day's new raw file was packed in"
    assert Watermark.read(ledger.watermark_path(state, ITEM, Period.DAILY)).through == OLD
    assert not migration.left(state, [ITEM])


@pytest.mark.parametrize("files", [1, 2], ids=["in one file", "in two files"])
def test_a_probe_and_its_clock_arrive_as_one_row(tmp_path: Path, files: int) -> None:
    """A job's two halves share one key, in one file or two, and the door holds one row of both.

    The probe writes the machine as the job starts and the clock writes the
    job's time at its end, into the job's own file. A re-run that reached only
    the clock left its half in a file of its own.
    """
    state = tmp_path / "state"
    probe, clock = _probe(OLD), _clock(OLD)
    if files == 1:
        _csv(state, HOST, OLD, _writer(OLD, 1, ServerJob.WORK), [probe.csv_row(), clock.csv_row()])
    else:
        _csv(state, HOST, OLD, _writer(OLD, 1, ServerJob.WORK), [probe.csv_row()])
        _csv(state, HOST, OLD, _writer(OLD, 2, ServerJob.WORK), [clock.csv_row()])

    (moved,) = _run(state, HOST)

    (row,) = ledger.load_days(state, HOST, [OLD], model=HostFingerprintRow)
    both = _filled(probe) | _filled(clock)
    assert _filled(probe).keys() & _filled(clock).keys() == set(ledger.HOST_FINGERPRINT_KEY)
    assert {name: row.csv_row()[name] for name in both} == both
    assert moved.rows == 1


def test_an_item_health_file_under_the_old_headings_reads_back_under_the_new_ones(
    tmp_path: Path,
) -> None:
    """`job` and `shard` named the machine until the door took those two words for the writer.

    A file written before the rename reads back with the machine under
    `machine_job` and `machine_shard`, the migration under the door's own `job`
    and `shard`, and the dropped headings nowhere.
    """
    state = tmp_path / "state"
    row = _item(OLD, "ai-01", machine=True)
    retired = {current: old for old, current in MACHINE_CELLS_RENAMED.items()}
    cells = {retired.get(name, name): value for name, value in row.csv_row().items()}
    dropped = dict.fromkeys(sorted(DROPPED_CELLS), "7")
    _csv(state, ITEM, OLD, _writer(OLD, 1, ServerJob.WORK), [cells | dropped])

    _run(state, ITEM)

    assert ledger.load_days(state, ITEM, [OLD], model=ItemHealthRow) == [row]
    found = ledger.compact_file(state, ITEM, Period.DAILY, OLD)
    assert found is not None
    (stored,) = _stored(found)
    assert (stored["machine_job"], stored["machine_shard"]) == (ServerJob.WORK.value, 0)
    assert (stored["job"], stored["shard"]) == (ServerJob.MIGRATE.value, migration.SHARD)
    assert not DROPPED_CELLS & stored.keys()


def test_the_proof_refuses_a_day_that_does_not_read_back(tmp_path: Path) -> None:
    """The oracle bites: a later write of the migration's own unit changes one cell."""
    state = tmp_path / "state"
    rows = [_item(NEW, "ai-03", machine=False, words=120)]
    _csv(state, ITEM, NEW, _writer(NEW, 1, ServerJob.ASSEMBLE), [row.csv_row() for row in rows])
    _run(state, ITEM)
    migration.prove(state, ITEM, NEW, [row.csv_row() for row in rows])

    ledger.persist(
        state,
        [_item(NEW, "ai-03", machine=False, words=121)],
        ledger=ITEM,
        covers=NEW,
        identity=migration._identity(RUN, SEED_COMMIT),
    )

    with pytest.raises(migration.NotProvenError, match="source_words"):
        migration.prove(state, ITEM, NEW, [row.csv_row() for row in rows])


def test_a_day_that_does_not_read_back_leaves_every_csv_of_every_ledger_in_place(
    tmp_path: Path,
) -> None:
    """The bite: the door serves one cell other than the one the migration filed.

    A file already on disk as a later attempt at the migration's own work unit
    holds `cores` differently, and a reader keeps a unit's highest attempt, so
    the host day reads that cell back. Item-health came across whole before it,
    and its CSV stays too: no CSV of any ledger goes until every day is proven.
    """
    state = tmp_path / "state"
    _csv(state, ITEM, OLD, _writer(OLD, 1, ServerJob.WORK), [_item(OLD, "ai-01", machine=True).csv_row()])
    probe = _probe(OLD)
    _csv(state, HOST, OLD, _writer(OLD, 1, ServerJob.WORK), [probe.csv_row()])
    later = migration._identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2})
    ledger.persist(state, [probe.model_copy(update={"cores": 64})], ledger=HOST, covers=OLD, identity=later)
    kept = {path: path.read_bytes() for path in migration.left(state, list(migration.LEDGERS))}

    with pytest.raises(migration.NotProvenError, match=rf"host-fingerprint {OLD} .*cores='64'"):
        _run(state, *migration.LEDGERS)

    assert {path: path.read_bytes() for path in migration.left(state, list(migration.LEDGERS))} == kept
    assert len(kept) == 2


def test_a_row_that_will_not_parse_is_refused_before_anything_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The utility exits 1 naming the ledger, the day, the file and the row, and touches nothing."""
    state = tmp_path / "state"
    _csv(state, ITEM, OLD, _writer(OLD, 1, ServerJob.WORK), [_item(OLD, "ai-01", machine=True).csv_row()])
    name = _writer(OLD, 1, ServerJob.WORK)
    _csv(state, HOST, OLD, name, [_probe(OLD).csv_row() | {"cores": "four"}])
    before = _hashes(tmp_path)

    code = migration.main(["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT])

    assert code == migration.EXIT_NOT_PROVEN
    assert f"nothing deleted: {HOST.value} {OLD}: {name} row 2 " in capsys.readouterr().err
    assert _hashes(tmp_path) == before
