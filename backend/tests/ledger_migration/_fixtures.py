"""Which bounded CSV trees, rows, configs and runs do the migration tests build?

Each case builds under `tmp_path`: the per-writer day tree, `YYYY/MM/DD/*.csv`,
or a shared `YYYY/MM/DD.csv` file, filled from committed row fixtures. Nothing
reads committed state (CLAUDE.md section 13).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Final, cast

from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, SEED_COMMIT
from gardener._historical_config import PRE_YEARLY_CONFIG, copy_pre_yearly_config

from idhazh import day_shards, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.ledger import render_file
from utilities.ledger_migration import (
    csv_files,
    csv_layouts,
    phases,
    planning,
)
from utilities.ledger_migration.inputs import MigrationInputs

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


def fixture_text(folder: str, name: str) -> str:
    return (CONTRACT_FIXTURES_DIR / folder / name).read_text(encoding="utf-8")


def item_row(day: str, item: str, *, machine: bool, words: int = 120) -> ItemHealthRow:
    """One item-health row, from the committed fixture, filed for `day`."""
    base = ItemHealthRow.model_validate_json(fixture_text("item-health-row", "published.json"))
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


def feed_row(day: str) -> FeedHealthRow:
    """One feed-health row, from the committed fixture, filed for `day` by the plan job."""
    base = FeedHealthRow.model_validate_json(fixture_text("feed-health-row", "answered.json"))
    return FeedHealthRow.model_validate({**base.model_dump(), "date": day, "run_id": f"{day}-100"})


def seen_row(day: str) -> SeenRow:
    base = SeenRow.model_validate_json(fixture_text("seen-row", "first-sight.json"))
    return SeenRow.model_validate(
        {**base.model_dump(), "first_seen_at": f"{day}T06:00:00Z", "first_seen_run": f"{day}-100"}
    )


def score_row(day: str, number: int, **changed: Any) -> EvalRow:
    """One eval row, from the committed fixture: the `number`th article measured on `day`."""
    base = EvalRow.model_validate_json(fixture_text("eval-row", "high.json"))
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


def filled_cells(row: HostFingerprintRow) -> Cells:
    """The cells a host row fills, less the schema stamp, which a join keeps from one side."""
    return {name: value for name, value in row.csv_row().items() if value and name != "version"}


def clock_row(day: str, job: ServerJob = ServerJob.WORK) -> HostFingerprintRow:
    """The half of a job's host row written at the job's end: its time, and no machine."""
    base = HostFingerprintRow.model_validate_json(
        fixture_text("host-fingerprint-row", "the-clock-a-job-kept.json")
    )
    return HostFingerprintRow.model_validate(
        {**base.model_dump(), "date": day, "run_id": f"{day}-100", "job": job, "shard": 0}
    )


def probe_row(day: str, job: ServerJob = ServerJob.WORK) -> HostFingerprintRow:
    """The half written as the job starts: the machine, with every cell the clock fills empty."""
    base = HostFingerprintRow.model_validate_json(
        fixture_text("host-fingerprint-row", "every-reading-taken.json")
    )
    clock = [name for name in filled_cells(clock_row(day, job)) if name not in ledger.HOST_FINGERPRINT_KEY]
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


def writer_file_name(day: str, attempt: int, job: ServerJob) -> str:
    """A retired writer's file name for one day: `<run_id>-<attempt>-<job>-<shard>.csv`."""
    return ledger.segment_name(run_id=f"{day}-100", attempt=attempt, job=job, shard=0)


def write_csv(
    state: Path,
    which: LedgerName,
    day: str,
    name: str,
    rows: Sequence[Cells],
    *,
    columns: tuple[str, ...] | None = None,
) -> Path:
    """One CSV file of one day, in the layout the retired writers used."""
    folder = csv_layouts.csv_root(state, which) / day[:4] / day[5:7] / day[8:10]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(render_file(columns or tuple(rows[0]), rows), encoding="utf-8", newline="")
    return path


def write_shared_csv(state: Path, which: LedgerName, day: str, rows: Sequence[Cells]) -> Path:
    folder = csv_layouts.csv_root(state, which) / day[:4] / day[5:7]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day[8:10]}.csv"
    columns = tuple(rows[0]) if rows else ROWS[which].csv_columns()
    path.write_text(render_file(columns, rows), encoding="utf-8", newline="")
    return path


def by_key(which: LedgerName, rows: Sequence[Cells]) -> ByKey:
    key = ledger.door_key(which)
    return {tuple(cells[name] for name in key): cells for cells in rows}


def todays_reader(state: Path, which: LedgerName) -> dict[str, ByKey]:
    """Every CSV day of a ledger, as today's CSV reader returns it."""
    root = csv_layouts.csv_root(state, which)
    return {
        day: by_key(
            which,
            day_shards.settled_day(
                root,
                day,
                ledger.door_key(which),
                cast("type[ledger.CsvContract]", ROWS[which]),
            ),
        )
        for day in csv_files.csv_days(state, which, months=MONTHS)
    }


def read_back(state: Path, which: LedgerName, day: str) -> ByKey:
    """One day as the door serves it, from whichever file serves it."""
    rows = ledger.load_days(state, which, [day], model=ROWS[which])
    return by_key(which, [row.csv_row() for row in rows])


def file_hashes(root: Path) -> dict[str, str]:
    """Every file under a tree, by its path relative to the tree, to the digest of its bytes."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def config_beside(state: Path) -> Path:
    """A config folder beside this state tree, holding recorded pre-expiry declarations.

    Only the state tree beside its config folder is packed, so a case that wants
    packing builds one, as a checkout holds one beside `state/`.
    """
    config_dir = copy_pre_yearly_config(state.parent)
    (config_dir / "ledgers.json").write_bytes((CONFIG_DIR / "ledgers.json").read_bytes())
    return config_dir


def entry_back_on_csv(which: LedgerName) -> dict[str, Any]:
    """The registry entry a ledger had before its writers moved to the door."""
    return {
        "name": which.value,
        "grain": Grain.DAY_TREE.value,
        "prefix": [which.value],
        "stem": None,
        "suffix": None,
    }


def registry_back_on_csv(config_dir: Path, which: LedgerName) -> Path:
    """This config folder, its registry filing one ledger the way it was filed before it moved."""
    registry_path = config_dir / "ledgers.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for family in registry["families"]:
        family["ledgers"] = [
            entry_back_on_csv(which) if held["name"] == which.value else held
            for held in family["ledgers"]
        ]
    registry_path.write_text(json.dumps(registry), encoding="ascii")
    return config_dir


def compaction_identity() -> WriterIdentity:
    return WriterIdentity(
        run_id=RUN,
        attempt=1,
        job=ServerJob.RUN_TASKS,
        shard=0,
        producer="gardener.tasks.compaction",
        git_sha=SEED_COMMIT,
    )


def run_migration(state: Path, *which: LedgerName, today: date = TODAY) -> list[planning.Moved]:
    """Migrate these ledgers on `today` with recorded pre-expiry declarations."""
    return [
        report
        for _, report in phases.migrate_roots(
            MigrationInputs(
                state_dirs=[state],
                which=which,
                run_id=RUN,
                git_sha=SEED_COMMIT,
                today=today,
                config_dir=config_beside(state),
                months=MONTHS,
            )
        )
    ]


def plan_named_roots(roots: Sequence[Path], *which: LedgerName) -> list[planning.RootPlan]:
    return planning.plan_roots(
        MigrationInputs(
            state_dirs=roots,
            which=which,
            run_id=RUN,
            git_sha=SEED_COMMIT,
            today=TODAY,
            config_dir=PRE_YEARLY_CONFIG,
            months=MONTHS,
        )
    )
