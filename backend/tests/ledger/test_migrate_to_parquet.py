"""Does the migration move every CSV row through the door, and nothing it may not?

Each case builds bounded CSV layouts under `tmp_path`: the per-writer tree,
`YYYY/MM/DD/*.csv`, or a shared `YYYY/MM/DD.csv` file. It reads the same rows
the old reader or row contract returns, proves each day through the door, and
checks that CSV is deleted only after the proof. Nothing reads committed state
(CLAUDE.md section 13).

"Nothing it may not" is the refusals and the table. A ledger the registry still
files as CSV, one with no compaction, and one whose compaction keeps less than
its CSV was kept are refused before a file is written; a root other than the
state tree beside `config/` is filed raw and never packed. The table of where
each ledger's CSV sat is held against the committed registry and declarations,
which those two cases read rather than build, so a pull request that changes
either is checked against it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, Final, cast

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, SEED_COMMIT
from gardener._garden import a_config
from gardener.tasks._task import declared as task_declarations

from idhazh import config, day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.counterfactual_score import CounterfactualScoreRow
from idhazh.contracts.eval_row import DROPPED_CELLS as DROPPED_EVAL_CELLS
from idhazh.contracts.eval_row import RENAMED_CELLS, EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import DROPPED_CELLS, MACHINE_CELLS_RENAMED, ItemHealthRow
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, Watermark
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.gardener import schedule
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import compaction
from idhazh.ledger import json_lines, parquet, paths, render_file
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
MONTHS: Final = ("2026-09",)
MONTH_ARGS: Final = ("--month", MONTHS[0])
ITEM: Final = LedgerName.ITEM_HEALTH
EVALS: Final = LedgerName.SUMMARY_QUALITY_EVALS
HOST: Final = LedgerName.HOST_FINGERPRINT
#: The ledgers these cases build CSV trees for, each filed through the door.
MOVED: Final = (ITEM, EVALS, HOST)
#: Each one's row contract, the one the door table pairs it with.
ROWS: Final[dict[LedgerName, type[Any]]] = {
    ITEM: ItemHealthRow,
    EVALS: EvalRow,
    HOST: HostFingerprintRow,
    LedgerName.SEEN: SeenRow,
    LedgerName.PUBLISHED: PublishedRow,
}
#: The ledger the two cases about a ledger still on CSV put back there, filed the
#: way the registry filed it before it moved. Every ledger in the table is on the
#: door now, so no committed registry holds that case any more.
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


def _feed(day: str) -> FeedHealthRow:
    """One feed-health row, from the committed fixture, filed for `day` by the plan job."""
    base = FeedHealthRow.model_validate_json(_fixture("feed-health-row", "answered.json"))
    return FeedHealthRow.model_validate({**base.model_dump(), "date": day, "run_id": f"{day}-100"})


def _seen(day: str) -> SeenRow:
    base = SeenRow.model_validate_json(_fixture("seen-row", "first-sight.json"))
    return SeenRow.model_validate(
        {**base.model_dump(), "first_seen_at": f"{day}T06:00:00Z", "first_seen_run": f"{day}-100"}
    )


def _published(day: str) -> PublishedRow:
    base = PublishedRow.model_validate_json(_fixture("published-row", "one-item.json"))
    return PublishedRow.model_validate({**base.model_dump(), "published_on": day})


def _counterfactual(day: str) -> CounterfactualScoreRow:
    return CounterfactualScoreRow(
        version=CounterfactualScoreRow.schema_version(),
        date=day,
        run_id=f"{day}-100",
        vertical="technology",
        url_key=hashlib.sha256(day.encode()).hexdigest(),
        taken=False,
        lens_id="",
        lens_bonus=0.0,
        lens_multiplier=1.0,
        score_committed=0.0,
        score_counterfactual=0.0,
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


def _shared_csv(state: Path, which: LedgerName, day: str, rows: Sequence[Cells]) -> Path:
    folder = migration.csv_root(state, which) / day[:4] / day[5:7]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day[8:10]}.csv"
    columns = tuple(rows[0]) if rows else ROWS[which].csv_columns()
    path.write_text(render_file(columns, rows), encoding="utf-8", newline="")
    return path


def _by_key(which: LedgerName, rows: Sequence[Cells]) -> ByKey:
    key = ledger.door_key(which)
    return {tuple(cells[name] for name in key): cells for cells in rows}


def _todays_reader(state: Path, which: LedgerName) -> dict[str, ByKey]:
    """Every CSV day of a ledger, as today's CSV reader returns it."""
    root = migration.csv_root(state, which)
    return {
        day: _by_key(
            which,
            day_shards.settled_day(
                root,
                day,
                ledger.door_key(which),
                cast("type[ledger.CsvContract]", ROWS[which]),
            ),
        )
        for day in migration.csv_days(state, which, months=MONTHS)
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
    config_dir = a_config(state.parent, CONFIG_DIR / "gardener")
    (config_dir / "ledgers.json").write_bytes((CONFIG_DIR / "ledgers.json").read_bytes())
    return config_dir


def _back_on_csv(which: LedgerName) -> dict[str, Any]:
    """The registry entry a ledger had before its writers moved to the door."""
    return {
        "name": which.value,
        "grain": Grain.DAY_TREE.value,
        "prefix": [which.value],
        "stem": None,
        "suffix": None,
    }


def _day_file_config(state: Path, which: Sequence[LedgerName]) -> Path:
    """A real temporary registry and compaction declaration for shared-day migration cases."""
    config_dir = _beside(state)
    registry_path = config_dir / "ledgers.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for family in registry["families"]:
        for entry in family["ledgers"]:
            if LedgerName(entry["name"]) in which:
                entry.update(
                    grain=Grain.RAW_AND_COMPACT.value,
                    prefix=[entry["name"]],
                    stem=None,
                    suffix=None,
                )
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="ascii", newline="")
    source = config_dir / "gardener" / f"compact-{EVALS.value}.json"
    declared = json.loads(source.read_text(encoding="utf-8"))
    for name in which:
        policy = declared | {
            "ledger": name.value,
            "owns": [f"state/raw/{name.value}", f"state/compact/{name.value}"],
        }
        target = config_dir / "gardener" / f"compact-{name.value}.json"
        target.write_text(json.dumps(policy, indent=2) + "\n", encoding="ascii", newline="")
        knobs_path = config_dir / "idhazh_gardener.json"
        knobs = json.loads(knobs_path.read_text(encoding="ascii"))
        task = f"compact-{name.value}"
        if task not in knobs["task_names"]:
            knobs["task_names"].append(task)
        knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
    return config_dir


def _compaction_identity() -> WriterIdentity:
    return WriterIdentity(
        run_id=RUN,
        attempt=1,
        job=ServerJob.RUN_TASKS,
        shard=0,
        producer="gardener.tasks.compaction",
        git_sha=SEED_COMMIT,
    )


def _monthly_history(
    state: Path,
    which: LedgerName,
    model: type[Any],
    months: dict[str, list[tuple[str, Any]]],
    *,
    today: date,
    daily_through: str | None = None,
) -> None:
    """Build real monthly door files and indexes for a bounded compaction fixture."""
    scratch = state.parent / f"{which.value}-raw-source"
    entries: list[CompactEntry] = []
    identity = _compaction_identity()
    for month, dated_rows in sorted(months.items()):
        raw = [
            path
            for day, row in dated_rows
            for path in ledger.persist(
                scratch,
                [row],
                ledger=which,
                covers=day,
                identity=migration._identity(RUN, SEED_COMMIT),
            )
        ]
        period = ledger.persist_period(
            state,
            ledger.load_stored(raw, model=model),
            model=model,
            ledger=which,
            period=Period.MONTHLY,
            covers=month,
            identity=identity,
            built_from=len(raw),
        )
        entries.append(
            CompactEntry(covers=month, rows=len(dated_rows), bytes=period.stat().st_size)
        )
    monthly_index = ledger.compact_index_path(state, which, Period.MONTHLY)
    monthly_index.parent.mkdir(parents=True, exist_ok=True)
    monthly_index.write_bytes(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=which,
            period=Period.MONTHLY,
            entries=entries,
        )
        .to_json()
        .encode("ascii")
    )
    latest_month = max(months)
    monthly_mark = ledger.watermark_path(state, which, Period.MONTHLY)
    monthly_mark.parent.mkdir(parents=True, exist_ok=True)
    monthly_mark.write_bytes(
        Watermark(
            version=Watermark.schema_version(),
            ledger=which,
            period=Period.MONTHLY,
            through=latest_month,
            advanced_at="2027-03-20T00:41:00Z",
            run_id=RUN,
        )
        .to_json()
        .encode("ascii")
    )
    daily_index = ledger.compact_index_path(state, which, Period.DAILY)
    daily_index.parent.mkdir(parents=True, exist_ok=True)
    daily_index.write_bytes(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=which,
            period=Period.DAILY,
            entries=[],
        )
        .to_json()
        .encode("ascii")
    )
    through = (
        daily_through
        or schedule.newest_eligible(
            now=datetime.combine(today, time.min, tzinfo=UTC), after_days=1
        ).isoformat()
    )
    daily_mark = ledger.watermark_path(state, which, Period.DAILY)
    daily_mark.parent.mkdir(parents=True, exist_ok=True)
    daily_mark.write_bytes(
        Watermark(
            version=Watermark.schema_version(),
            ledger=which,
            period=Period.DAILY,
            through=through,
            advanced_at="2027-03-20T00:41:00Z",
            run_id=RUN,
        )
        .to_json()
        .encode("ascii")
    )


def _run(state: Path, *which: LedgerName, today: date = TODAY) -> list[migration.Moved]:
    """The migration of these ledgers, run on the wake `today` with the committed declarations."""
    return migration.migrate(
        state,
        which,
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=today,
        config_dir=_beside(state),
        months=MONTHS,
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
    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    _csv(
        state,
        ITEM,
        NEW,
        ledger.BEFORE_PARTITION_NAME,
        [_item(NEW, "ai-03", machine=True).csv_row()],
    )
    assembled = [_item(NEW, "ai-03", machine=False), _item(NEW, "ai-04", machine=False)]
    _csv(
        state, ITEM, NEW, _writer(NEW, 1, ServerJob.ASSEMBLE), [row.csv_row() for row in assembled]
    )
    _csv(state, EVALS, OLD, day_shards.SETTLED_NAME, [_score(OLD, 1).csv_row()])
    _csv(
        state, EVALS, OLD, _writer(OLD, 1, ServerJob.WORK), [_score(OLD, 2, score_ms=100).csv_row()]
    )
    _csv(
        state, EVALS, OLD, _writer(OLD, 2, ServerJob.WORK), [_score(OLD, 2, score_ms=200).csv_row()]
    )
    _csv(state, EVALS, NEW, _writer(NEW, 1, ServerJob.WORK), [_under_old_headings(_score(NEW, 3))])
    _csv(state, HOST, FIRST, day_shards.SETTLED_NAME, [], columns=HostFingerprintRow.csv_columns())
    halves = [_probe(OLD).csv_row(), _clock(OLD).csv_row()]
    _csv(state, HOST, OLD, _writer(OLD, 1, ServerJob.WORK), halves)
    halves = [_probe(NEW, ServerJob.PLAN).csv_row(), _clock(NEW, ServerJob.PLAN).csv_row()]
    _csv(state, HOST, NEW, _writer(NEW, 1, ServerJob.PLAN), halves)
    wanted = {which: _todays_reader(state, which) for which in MOVED}
    lines = {
        which: sum(
            1
            for path in migration.left(state, [which], months=MONTHS)
            for _ in day_shards.rows_of(path)
        )
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
    assert not migration.left(state, list(MOVED), months=MONTHS)
    item_key = (OLD, f"{OLD}-100", "ai-01")
    assert _read_back(state, ITEM, OLD)[item_key]["machine_job"] == ServerJob.WORK.value
    assert {cells["score_ms"] for cells in _read_back(state, EVALS, OLD).values()} == {"0", "200"}
    assert (lines[EVALS], moved[EVALS].rows) == (4, 3), "a re-run's first attempt is no row"
    assert list(_read_back(state, EVALS, NEW).values()) == [_score(NEW, 3).csv_row()]
    assert [len(wanted[HOST][day]) for day in (FIRST, OLD, NEW)] == [0, 1, 1]


def test_a_second_run_changes_no_byte(tmp_path: Path) -> None:
    """At the same wake, every period admitted by the compaction is already packed."""
    state = tmp_path / "state"
    _csv(
        state,
        ITEM,
        NEW,
        _writer(NEW, 1, ServerJob.ASSEMBLE),
        [_item(NEW, "ai-03", machine=False).csv_row()],
    )
    _csv(state, EVALS, NEW, _writer(NEW, 1, ServerJob.WORK), [_score(NEW, 1).csv_row()])
    _csv(
        state,
        HOST,
        NEW,
        _writer(NEW, 1, ServerJob.WORK),
        [_probe(NEW).csv_row(), _clock(NEW).csv_row()],
    )
    _run(state, *MOVED)
    before = _hashes(tmp_path)
    waiting = [ledger.raw_days(state, which) for which in MOVED]

    again = _run(state, *MOVED)
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]

    assert [(each.days, each.filed, each.packed) for each in again] == [(0, 0, [])] * 3
    assert migration.main([*MONTH_ARGS, *argv]) == migration.EXIT_MIGRATED
    assert _hashes(tmp_path) == before
    assert waiting == [[NEW]] * 3, "the day the second run could have packed is still raw"


def test_check_says_whether_a_csv_is_left_and_writes_nothing(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _csv(
        state,
        ITEM,
        NEW,
        _writer(NEW, 1, ServerJob.ASSEMBLE),
        [_item(NEW, "ai-03", machine=False).csv_row()],
    )
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT, "--check"]
    before = _hashes(tmp_path)

    assert migration.main([*MONTH_ARGS, *argv]) == migration.EXIT_NOT_PROVEN
    assert (
        migration.main([*MONTH_ARGS, *[*argv, "--ledger", EVALS.value]]) == migration.EXIT_MIGRATED
    )
    assert _hashes(tmp_path) == before, "a check writes nothing"
    _run(state, ITEM)
    assert migration.main([*MONTH_ARGS, *argv]) == migration.EXIT_MIGRATED


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


def test_every_unmoved_table_entry_is_the_registry_entry() -> None:
    """A ledger still on CSV sits where the registry files it, so its move changes neither.

    Read off the committed `config/ledgers.json`: a change that files a ledger's
    CSV somewhere else, and leaves its table entry behind, fails here.
    """
    door = set(migration.door_ledgers())
    unmoved = [name for name in migration.CSV_LEDGERS if name not in door]

    assert {name: migration.CSV_LEDGERS[name].old_entry for name in unmoved} == {
        name: ledger.entry(name) for name in unmoved
    }


def test_every_moved_ledger_keeps_its_old_window() -> None:
    """A moved ledger's committed compaction keeps every day a task kept of its CSV.

    Read off the committed declarations, so a change that shortens one fails
    here rather than at the first live pass that deletes those days.
    """
    tasks = task_declarations()
    moved = migration.door_ledgers()
    short: list[str] = []
    for name in moved:
        policy = tasks[f"compact-{name.value}"]
        assert isinstance(policy, CompactionPolicy), name
        if not config.compaction_reaches(policy, migration.CSV_LEDGERS[name].old_window):
            short.append(name.value)

    assert moved, "no ledger in the table has moved, so nothing is checked"
    assert short == []


def test_a_ledger_still_on_csv_is_refused(tmp_path: Path) -> None:
    """A run naming a ledger the registry still files as CSV is refused and writes nothing.

    Its writers still write CSV, so a door copy of its rows is one no reader
    opens. A door ledger named beside it does not move either: the whole run is
    refused before its first file is read. The registry beside this tree files
    one ledger the way it was filed before it moved, without its compaction.
    """
    state = tmp_path / "state"
    _csv(state, ON_CSV, OLD, _writer(OLD, 1, ServerJob.PLAN), [_feed(OLD).csv_row()])
    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    config_dir = _beside(state)
    registry_path = config_dir / "ledgers.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for family in registry["families"]:
        family["ledgers"] = [
            _back_on_csv(ON_CSV) if held["name"] == ON_CSV.value else held
            for held in family["ledgers"]
        ]
    registry_path.write_text(json.dumps(registry), encoding="ascii")
    (config_dir / "gardener" / f"compact-{ON_CSV.value}.json").unlink()
    knobs_path = config_dir / "idhazh_gardener.json"
    knobs = json.loads(knobs_path.read_text(encoding="ascii"))
    knobs["task_names"].remove(f"compact-{ON_CSV.value}")
    knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
    before = _hashes(tmp_path)

    with pytest.raises(
        migration.RefusedError,
        match=f"config/ledgers.json files {ON_CSV.value} as {Grain.DAY_TREE.value},",
    ):
        migration.migrate(
            state,
            [ITEM, ON_CSV],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=config_dir,
            months=MONTHS,
        )

    assert _hashes(tmp_path) == before


@pytest.mark.parametrize(
    ("change", "refusal"),
    [
        (None, "compact-summary-quality-evals.json does not declare a compaction"),
        (
            {"monthly_window": {"unit": "months", "value": 13}, "monthly_keep_days": None},
            "does not reach the window of forever that kept summary-quality-evals on CSV",
        ),
    ],
    ids=["no-compaction", "short-of-the-csv"],
)
def test_a_door_ledger_whose_compaction_cannot_hold_its_csv_is_refused(
    tmp_path: Path, change: dict[str, Any] | None, refusal: str
) -> None:
    """Refused before a file is read: nothing says which days to pack, or a pass deletes them.

    No task ever deleted an eval row, so a compaction keeping thirteen months
    would delete, at its first live pass, days its CSV still held.
    """
    state = tmp_path / "state"
    _csv(state, EVALS, NEW, _writer(NEW, 1, ServerJob.WORK), [_score(NEW, 1).csv_row()])
    config_dir = _beside(state)
    declaration = config_dir / "gardener" / f"compact-{EVALS.value}.json"
    if change is None:
        declaration.unlink()
        knobs_path = config_dir / "idhazh_gardener.json"
        knobs = json.loads(knobs_path.read_text(encoding="ascii"))
        knobs["task_names"].remove(declaration.stem)
        knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")
    else:
        declared = json.loads(declaration.read_text(encoding="utf-8"))
        declaration.write_text(json.dumps(declared | change), encoding="ascii")
    before = _hashes(tmp_path)

    with pytest.raises(migration.RefusedError, match=refusal):
        migration.migrate(
            state,
            [EVALS],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=config_dir,
            months=MONTHS,
        )

    assert _hashes(tmp_path) == before


def test_check_reads_moved_ledgers_unless_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no `--ledger`, a check reads the table ledgers the registry files through the door.

    A ledger still on CSV writes a CSV file on every run, so a check that read
    it unasked could never pass: handed a registry entry that files one ledger
    the way it was filed before it moved, the check leaves that ledger's file
    alone. Named, it is read, and `--ledger` repeats.
    """
    state = tmp_path / "state"
    feed = _csv(state, ON_CSV, OLD, _writer(OLD, 1, ServerJob.PLAN), [_feed(OLD).csv_row()])
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT, "--check"]

    assert migration.main([*MONTH_ARGS, *argv]) == migration.EXIT_NOT_PROVEN
    assert capsys.readouterr().out.splitlines() == [
        f"{migration._shown(state, feed)} is still a CSV",
        "1 CSV file(s) left",
    ]

    with monkeypatch.context() as patched:
        patched.setitem(paths._REGISTRY, ON_CSV, LedgerEntry.model_validate(_back_on_csv(ON_CSV)))
        assert migration.main([*MONTH_ARGS, *argv]) == migration.EXIT_MIGRATED
    assert capsys.readouterr().out.splitlines() == ["0 CSV file(s) left"]

    item = _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    named = [*argv, "--ledger", ITEM.value, "--ledger", ON_CSV.value]

    assert migration.main([*MONTH_ARGS, *named]) == migration.EXIT_NOT_PROVEN
    assert capsys.readouterr().out.splitlines() == [
        f"{migration._shown(state, item)} is still a CSV",
        f"{migration._shown(state, feed)} is still a CSV",
        "2 CSV file(s) left",
    ]


def test_a_layout_this_does_not_read_is_refused_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed shared-day layout is named and refused, never skipped.

    A check that read nothing there would pass over every file it holds.
    """
    state = tmp_path / "state"
    malformed = migration.csv_root(state, LedgerName.SEEN) / "2026" / "09" / "not-a-day.csv"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("version,url_key,first_seen_at,first_seen_run\n", encoding="ascii")
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]

    code = migration.main([*MONTH_ARGS, *[*argv, "--check", "--ledger", LedgerName.SEEN.value]])

    assert code == migration.EXIT_NOT_PROVEN
    assert "not-a-day.csv is not a YYYY/MM/DD.csv file" in capsys.readouterr().err


def test_a_shared_day_file_moves_cell_for_cell(tmp_path: Path) -> None:
    """The YYYY/MM/DD.csv layout reads through each row contract before its file is deleted."""
    state = tmp_path / "state"
    day = TODAY.isoformat()
    expected = {
        LedgerName.SEEN: {day: [_seen(day).csv_row()]},
        LedgerName.PUBLISHED: {day: [_published(day).csv_row()]},
    }
    source_files = {
        (which, day): _shared_csv(state, which, day, rows)
        for which, days in expected.items()
        for day, rows in days.items()
    }

    config_dir = _day_file_config(state, (LedgerName.SEEN, LedgerName.PUBLISHED))
    moved = {
        each.which: each
        for _, each in migration.migrate_roots(
            [state],
            [LedgerName.SEEN, LedgerName.PUBLISHED],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=config_dir,
            months=MONTHS,
        )
    }

    for which, days in expected.items():
        assert moved[which].rows == sum(len(rows) for rows in days.values())
        for day, rows in days.items():
            assert _read_back(state, which, day) == _by_key(which, rows)
            assert not source_files[which, day].exists()
        assert not migration.csv_root(state, which).exists()
        assert not migration.left(state, [which], months=MONTHS)


def test_a_shared_day_file_with_a_refused_layout_preserves_every_csv(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    valid = _shared_csv(state, LedgerName.SEEN, OLD, [_seen(OLD).csv_row()])
    refused = migration.csv_root(state, LedgerName.SEEN) / "2026/09/not-a-day.csv"
    refused.write_text("version,url_key,first_seen_at,first_seen_run\n", encoding="ascii")
    before = {valid: valid.read_bytes(), refused: refused.read_bytes()}
    config_dir = _day_file_config(state, (LedgerName.SEEN,))

    with pytest.raises(migration.NotProvenError, match=r"not a YYYY/MM/DD\.csv file"):
        migration.migrate(
            state,
            [LedgerName.SEEN],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=config_dir,
            months=MONTHS,
        )

    assert {path: path.read_bytes() for path in before} == before


def test_a_root_beside_no_config_is_filed_raw_and_never_packed(tmp_path: Path) -> None:
    """Only the state tree beside `config/` is packed; a trial run's tree inside it is filed raw.

    Nothing reads a packed trial root, and the trials task empties it, so its
    day files and indexes would be files nobody opens. Its days are still read
    back cell for cell before its CSV goes.
    """
    state = tmp_path / "state"
    trial = state / "pipeline-tests"
    _csv(
        trial,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    wanted = _todays_reader(trial, ITEM)

    (moved,) = migration.migrate(
        trial,
        [ITEM],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=TODAY,
        config_dir=_beside(state),
        months=MONTHS,
    )

    assert (moved.days, moved.filed, moved.packed) == (1, 1, [])
    assert ledger.raw_days(trial, ITEM) == [OLD], "a day the rule admits stays raw here"
    assert not ledger.compact_index_path(trial, ITEM, Period.DAILY).exists()
    assert _read_back(trial, ITEM, OLD) == wanted[OLD]
    assert not migration.left(trial, [ITEM], months=MONTHS)
    assert migration.packs_here(REPO_ROOT / ledger.STATE_DIRNAME, CONFIG_DIR)
    assert not migration.packs_here(REPO_ROOT / ledger.STATE_DIRNAME / "pipeline-tests", CONFIG_DIR)


def test_cli_migrates_each_repeated_trial_root_raw_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = tmp_path / "state"
    trials = [
        state / "pipeline-tests",
        state / "pipeline-tests-no-visual-plan",
        state / "pipeline-tests-production-settings",
    ]
    source_files: dict[Path, tuple[Path, LedgerName, str]] = {}
    wanted: dict[tuple[Path, LedgerName], dict[str, ByKey]] = {}
    for number, trial in enumerate(trials):
        day = OLD if number < 2 else NEW
        item = _item(day, f"ai-{number + 1:02d}", machine=True)
        host = [_probe(day).csv_row(), _clock(day).csv_row()]
        for which, rows in ((ITEM, [item.csv_row()]), (HOST, host)):
            path = _csv(trial, which, day, _writer(day, 1, ServerJob.WORK), rows)
            source_files[path] = (trial, which, day)
            wanted[trial, which] = _todays_reader(trial, which)
    args = [part for trial in trials for part in ("--state-dir", str(trial))]
    args.extend(
        [
            *MONTH_ARGS,
            "--run-id",
            RUN,
            "--git-sha",
            SEED_COMMIT,
            "--ledger",
            ITEM.value,
            "--ledger",
            HOST.value,
        ]
    )

    assert migration.main([*MONTH_ARGS, *args]) == migration.EXIT_MIGRATED
    output = capsys.readouterr().out
    assert "every day is filed raw" in output
    for path, (trial, which, day) in source_files.items():
        assert not path.exists()
        assert _read_back(trial, which, day) == wanted[trial, which][day]
        assert not ledger.compact_index_path(trial, which, Period.DAILY).exists()
    check = [*args, "--check"]
    assert migration.main([*MONTH_ARGS, *check]) == migration.EXIT_MIGRATED


def test_repeated_roots_prove_every_day_before_deleting_any_csv(tmp_path: Path) -> None:
    state = tmp_path / "state"
    trials = [
        state / "pipeline-tests",
        state / "pipeline-tests-no-visual-plan",
        state / "pipeline-tests-production-settings",
    ]
    _csv(
        trials[0],
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    _csv(
        trials[1],
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-02", machine=True).csv_row()],
    )
    probe = _probe(NEW)
    source = _csv(trials[2], HOST, NEW, _writer(NEW, 1, ServerJob.WORK), [probe.csv_row()])
    later = migration._identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2})
    ledger.persist(
        trials[2],
        [probe.model_copy(update={"cores": 64})],
        ledger=HOST,
        covers=NEW,
        identity=later,
    )
    csv_before = {
        path: path.read_bytes()
        for trial in trials
        for which in (ITEM, HOST)
        for path in migration.left(trial, [which], months=MONTHS)
    }

    with pytest.raises(migration.NotProvenError, match="cores='64'"):
        migration.migrate_roots(
            trials,
            [ITEM, HOST],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            months=MONTHS,
        )

    assert {
        path: path.read_bytes()
        for trial in trials
        for which in (ITEM, HOST)
        for path in migration.left(trial, [which], months=MONTHS)
    } == csv_before
    assert source.exists()
    assert not ledger.compact_index_path(trials[0], ITEM, Period.DAILY).exists()
    assert not ledger.compact_index_path(trials[1], ITEM, Period.DAILY).exists()
    assert not ledger.compact_index_path(trials[2], HOST, Period.DAILY).exists()


def test_finite_monthly_window_reports_without_losing_migrated_rows(tmp_path: Path) -> None:
    state = tmp_path / "state"
    which = LedgerName.COUNTERFACTUAL_SCORES
    day = "2026-08-15"
    month = day[:7]
    today = date(2026, 10, 20)
    row = _counterfactual(day)
    _monthly_history(
        state,
        which,
        CounterfactualScoreRow,
        {month: [(day, row)]},
        today=today,
        daily_through="2026-08-31",
    )

    config_dir = _beside(state)
    (moved,) = migration.migrate(
        state,
        [which],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=today,
        config_dir=config_dir,
        months=[month],
    )

    month_file = ledger.compact_file(state, which, Period.MONTHLY, month)
    assert month_file is not None and month_file.exists()
    assert ledger.load_days(state, which, [day], model=CounterfactualScoreRow) == [row]
    assert not any(
        f"/monthly/{month.replace('-', '/')}.parquet" == path for path in moved.compaction_deleted
    )


def test_migration_packs_a_finished_year_for_a_forever_ledger(tmp_path: Path) -> None:
    state = tmp_path / "state"
    days = [f"{year}-{month:02d}-15" for year in (2026, 2027) for month in range(1, 13)] + [
        "2028-01-15"
    ]
    expected = {day: _score(day, number) for number, day in enumerate(days)}
    months = {day[:7]: [(day, expected[day])] for day in days}
    _monthly_history(state, EVALS, EvalRow, months, today=date(2028, 4, 4))
    config_dir = _beside(state)
    declaration = config_dir / "gardener" / f"compact-{EVALS.value}.json"
    policy = json.loads(declaration.read_text(encoding="utf-8"))
    declaration.write_text(
        json.dumps(policy | {"max_periods_per_run": 1}, indent=2) + "\n",
        encoding="ascii",
        newline="",
    )

    (moved,) = migration.migrate(
        state,
        [EVALS],
        run_id=RUN,
        git_sha=SEED_COMMIT,
        today=date(2028, 4, 4),
        config_dir=config_dir,
        months=tuple(months),
    )

    for year in ("2026", "2027"):
        packed = ledger.compact_file(state, EVALS, Period.YEARLY, year)
        assert packed is not None
    assert [ledger.load_days(state, EVALS, [day], model=EvalRow)[0] for day in days] == [
        expected[day] for day in days
    ]
    packed_years = sorted(
        path.rsplit("/", 1)[-1].removesuffix(".parquet")
        for path in moved.compaction_written
        if "/yearly/" in path and path.endswith(".parquet")
    )
    assert packed_years == ["2026", "2027"]


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
    model, key = ROWS[ITEM], ledger.door_key(ITEM)
    identity = migration._identity(RUN, SEED_COMMIT)
    for day in days:
        cells = day_shards.settled_day(
            migration.csv_root(live / "state", ITEM),
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
    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    (first,) = _run(state, ITEM)
    (again,) = _run(state, ITEM)

    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 2, ServerJob.WORK),
        [_item(OLD, "ai-04", machine=True).csv_row()],
    )
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
    assert not migration.left(state, [ITEM], months=MONTHS)


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
    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    probe = _probe(OLD)
    _csv(state, HOST, OLD, _writer(OLD, 1, ServerJob.WORK), [probe.csv_row()])
    later = migration._identity(RUN, SEED_COMMIT).model_copy(update={"attempt": 2})
    ledger.persist(
        state, [probe.model_copy(update={"cores": 64})], ledger=HOST, covers=OLD, identity=later
    )
    kept = {path: path.read_bytes() for path in migration.left(state, list(MOVED), months=MONTHS)}

    with pytest.raises(migration.NotProvenError, match=rf"host-fingerprint {OLD} .*cores='64'"):
        _run(state, *MOVED)

    assert {
        path: path.read_bytes() for path in migration.left(state, list(MOVED), months=MONTHS)
    } == kept
    assert len(kept) == 2


def test_a_row_that_will_not_parse_is_refused_before_anything_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The utility exits 1 naming the ledger, the day, the file and the row, and touches nothing."""
    state = tmp_path / "state"
    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    name = _writer(OLD, 1, ServerJob.WORK)
    _csv(state, HOST, OLD, name, [_probe(OLD).csv_row() | {"cores": "four"}])
    before = _hashes(tmp_path)

    code = migration.main(
        [*MONTH_ARGS, *["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT]]
    )

    assert code == migration.EXIT_NOT_PROVEN
    assert f"nothing deleted: {HOST.value} {OLD}: {name} row 2 " in capsys.readouterr().err
    assert _hashes(tmp_path) == before


def test_named_month_migration_ignores_other_csv_and_raw_months(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _csv(
        state,
        ITEM,
        OLD,
        _writer(OLD, 1, ServerJob.WORK),
        [_item(OLD, "ai-01", machine=True).csv_row()],
    )
    other_csv = migration.csv_root(state, ITEM) / "2026/10/not-a-day.csv"
    other_raw = ledger.raw_root(state, ITEM) / "2026/10/01/invalid.parquet"
    for path in (other_csv, other_raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff")

    _run(state, ITEM)

    assert migration.left(state, [ITEM], months=MONTHS) == []
    assert other_csv.read_bytes() == other_raw.read_bytes() == b"\xff"
    assert len(ledger.load_days(state, ITEM, [OLD], model=ItemHealthRow)) == 1


def test_scoped_packing_keeps_an_unnamed_indexed_month(tmp_path: Path) -> None:
    state = tmp_path / "state"
    old_day = "2026-08-15"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {"2026-08": [(old_day, _score(old_day, 1))]},
        today=date(2026, 11, 20),
        daily_through="2026-08-31",
    )
    old_file = ledger.compact_file(state, EVALS, Period.MONTHLY, "2026-08")
    assert old_file is not None
    before = old_file.read_bytes()
    _csv(state, EVALS, OLD, _writer(OLD, 1, ServerJob.WORK), [_score(OLD, 2).csv_row()])

    _run(state, EVALS, today=date(2026, 11, 20))

    assert old_file.read_bytes() == before
    assert ledger.compact_file(state, EVALS, Period.MONTHLY, MONTHS[0]) is not None
    assert len(ledger.load_days(state, EVALS, [OLD], model=EvalRow)) == 1


@pytest.mark.parametrize("month", ["202609", "2026-13", "0000-01", "../2026-09"])
def test_migration_cli_refuses_invalid_months(tmp_path: Path, month: str) -> None:
    with pytest.raises(SystemExit) as refused:
        migration.main(
            [
                "--state-dir",
                str(tmp_path),
                "--run-id",
                RUN,
                "--git-sha",
                SEED_COMMIT,
                "--month",
                month,
            ]
        )
    assert refused.value.code == 2


def test_migration_cli_requires_a_month(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as refused:
        migration.main(["--state-dir", str(tmp_path), "--run-id", RUN, "--git-sha", SEED_COMMIT])
    assert refused.value.code == 2


def test_named_months_cannot_skip_the_daily_watermark_gap(tmp_path: Path) -> None:
    state = tmp_path / "state"
    old_day = "2026-08-15"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {"2026-08": [(old_day, _score(old_day, 1))]},
        today=date(2026, 12, 20),
        daily_through="2026-08-31",
    )
    day = "2026-10-01"
    _csv(state, EVALS, day, _writer(day, 1, ServerJob.WORK), [_score(day, 2).csv_row()])

    with pytest.raises(migration.NotProvenError, match="named months omit 2026-09"):
        migration.migrate(
            state,
            [EVALS],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=date(2026, 12, 20),
            config_dir=_beside(state),
            months=["2026-10"],
        )

    assert len(migration.left(state, [EVALS], months=["2026-10"])) == 1


def test_scoped_packing_cannot_skip_an_unabsorbed_month(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {"2026-08": [("2026-08-15", _score("2026-08-15", 1))]},
        today=date(2026, 12, 20),
        daily_through="2026-09-30",
    )
    day = "2026-09-15"
    raw = ledger.persist(
        tmp_path / "source",
        [_score(day, 2)],
        ledger=EVALS,
        covers=day,
        identity=migration._identity(RUN, SEED_COMMIT),
    )
    daily = ledger.persist_period(
        state,
        ledger.load_stored(raw, model=EvalRow),
        model=EvalRow,
        ledger=EVALS,
        period=Period.DAILY,
        covers=day,
        identity=_compaction_identity(),
        built_from=len(raw),
    )
    ledger.compact_index_path(state, EVALS, Period.DAILY).write_bytes(
        CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=EVALS,
            period=Period.DAILY,
            entries=[CompactEntry(covers=day, rows=1, bytes=daily.stat().st_size)],
        )
        .to_json()
        .encode("ascii")
    )
    before = daily.read_bytes()
    selected = "2026-10-01"
    _csv(
        state,
        EVALS,
        selected,
        _writer(selected, 1, ServerJob.WORK),
        [_score(selected, 3).csv_row()],
    )

    with pytest.raises(migration.NotProvenError, match="compaction refused"):
        migration.migrate(
            state,
            [EVALS],
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=date(2026, 12, 20),
            config_dir=_beside(state),
            months=["2026-10"],
        )

    assert daily.read_bytes() == before
    assert Watermark.read(ledger.watermark_path(state, EVALS, Period.MONTHLY)).through == "2026-08"
    assert len(migration.left(state, [EVALS], months=["2026-10"])) == 1


def test_scoped_packing_cannot_skip_an_unabsorbed_year(tmp_path: Path) -> None:
    state = tmp_path / "state"
    _monthly_history(
        state,
        EVALS,
        EvalRow,
        {
            "2025-08": [("2025-08-15", _score("2025-08-15", 1))],
            "2026-12": [("2026-12-15", _score("2026-12-15", 2))],
        },
        today=date(2028, 4, 4),
        daily_through="2026-12-31",
    )
    old_file = ledger.compact_file(state, EVALS, Period.MONTHLY, "2025-08")
    assert old_file is not None
    before = old_file.read_bytes()
    months = tuple(f"2026-{number:02d}" for number in range(1, 13))
    policy = migration._declared([EVALS], _beside(state))[EVALS]

    with pytest.raises(migration.NotProvenError, match="compaction refused"):
        migration._pack(
            state,
            EVALS,
            migration._identity(RUN, SEED_COMMIT),
            policy=policy,
            today=date(2028, 4, 4),
            months=months,
        )

    assert old_file.read_bytes() == before
    assert not ledger.watermark_path(state, EVALS, Period.YEARLY).exists()
