"""How are named CSV inputs planned, filed, proven and retired without losing source cells?"""

from __future__ import annotations

import calendar
import errno
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final, cast

from idhazh import config, day_shards, ledger
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy, ForeverWindow, Window
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig
from idhazh.gardener.context import TaskContext
from idhazh.gardener.file_listing import FileListing
from idhazh.gardener.tasks import compaction
from idhazh.ledger.stored_output import check_compact_period, check_raw_day
from utilities.csv_ledgers import (
    CSV_LEDGERS,
    NotProvenError,
    RefusedError,
    csv_days,
    csv_root,
    read_csv_cells,
    read_csv_rows,
    root_label,
    row_contract,
)
from utilities.named_inputs import month_directories

# Writer identity remains unchanged when the implementation moves modules.
PRODUCER: Final = "utilities.migrate_to_parquet"
ATTEMPT: Final = 1
SHARD: Final = 0


def _key_of(cells: dict[str, str], key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(cells[name] for name in key)


def folded(
    held: Sequence[dict[str, str]], arriving: Sequence[dict[str, str]], key: tuple[str, ...]
) -> list[dict[str, str]]:
    """The rows the door holds for a day, with the CSV's rows for it folded on.

    The fold today's reader applies to a settled file and a writer's file beside
    it: the door's rows stand where the settled file stood, and the CSV's rows
    arrive after them, so a cell only one side filled is joined and a cell both
    filled goes to the later side unless the key declares a preference.
    """
    prefers = ledger.preference_for(key)
    records: dict[tuple[str, ...], day_shards.Held] = {}
    for cells in held:
        records[_key_of(cells, key)] = day_shards.Held(0, dict(cells))
    for number, cells in enumerate(arriving):
        record = _key_of(cells, key)
        if record not in records:
            records[record] = day_shards.Held(1, dict(cells))
            continue
        version = records[record].cells[day_shards.VERSION_CELL]
        day_shards.settle(
            records[record], day_shards.Waiting(Path(), 1, number, dict(cells)), key, prefers
        )
        records[record].cells[day_shards.VERSION_CELL] = max(
            version, cells[day_shards.VERSION_CELL]
        )
    return [entry.cells for entry in records.values()]


@dataclass(slots=True)
class PlannedDay:
    """One day of one ledger: what the door will hold, and the CSV files it came from."""

    files: list[Path]
    rows: list[dict[str, str]]
    #: The same rows read by the contract, for a day that files anything new; else empty.
    models: list[Contract]
    changed: bool
    source_rows: list[dict[str, str]]


@dataclass(slots=True)
class Moved:
    """What one ledger's migration did, in the numbers a reviewer asks for."""

    which: LedgerName
    csv_files: int = 0
    csv_bytes: int = 0
    days: int = 0
    rows: int = 0
    filed: int = 0
    packed: list[str] = field(default_factory=list)
    compaction_written: list[str] = field(default_factory=list)
    compaction_deleted: list[str] = field(default_factory=list)


def _door_rows(state_dir: Path, which: LedgerName, day: str) -> list[dict[str, str]]:
    rows = ledger.load_days(state_dir, which, [day], model=ledger.door_contract(which))
    return [cast("ledger.CsvRecord", row).csv_row() for row in rows]


def _check_output(state_dir: Path, which: LedgerName, day: str, *, required: bool) -> None:
    raw = check_raw_day(state_dir, which, day)
    compact = [
        check_compact_period(state_dir, which, period, covers)
        for period, covers in (
            (Period.DAILY, day),
            (Period.MONTHLY, day[:7]),
            (Period.YEARLY, day[:4]),
        )
    ]
    if required and any(compact):
        for period in Period:
            path = ledger.compact_index_path(state_dir, which, period)
            if not path.is_file():
                raise ValueError(f"missing compact index {path.name}")
    if required and not raw and not any(compact):
        raise ValueError("migrated output is missing")


def _plan(state_dir: Path, which: LedgerName, months: Sequence[str]) -> dict[str, PlannedDay]:
    """Every CSV day of this ledger, folded onto what the door holds for it. Nothing written.

    Everything that can refuse a day's rows refuses here, before the first
    write: a row that will not parse, a row dated another day, and a folded row
    the contract will not take. A fold joins cells from two files, and nothing
    checks the joined row until the door files it.
    """
    model, key = row_contract(which), ledger.door_key(which)
    planned: dict[str, PlannedDay] = {}
    label = f"{root_label(state_dir)}: {which.value}"
    try:
        days = csv_days(state_dir, which, months=months)
    except (ValueError, OSError) as refusal:
        raise NotProvenError(f"{label}: {refusal}") from refusal
    for day, files in days.items():
        context = f"{label} {day}"
        try:
            arriving = read_csv_rows(state_dir, which, day, files, key, model)
        except (ValueError, OSError) as refusal:
            raise NotProvenError(f"{context}: {refusal}") from refusal
        stray = sorted({cells["date"] for cells in arriving if cells.get("date")} - {day})
        if stray:
            raise NotProvenError(
                f"{context}: the CSV day holds rows dated {stray}, and the door "
                "files a row under its own date, so this day would not read back"
            )
        try:
            _check_output(state_dir, which, day, required=False)
            held = _door_rows(state_dir, which, day)
        except (ValueError, OSError) as refusal:
            raise NotProvenError(f"{context}: {refusal}") from refusal
        rows = folded(held, arriving, key)
        changed = rows != held
        try:
            models = [read_csv_cells(model, cells) for cells in rows] if changed else []
        except ValueError as refusal:
            raise NotProvenError(
                f"{context}: a settled row is not a {model.__name__} the door can file: {refusal}"
            ) from refusal
        planned[day] = PlannedDay(
            files=files, rows=rows, models=models, changed=changed, source_rows=arriving
        )
    return planned


def _spelled(window: Window) -> str:
    """A window as a refusal quotes it."""
    return "forever" if isinstance(window, ForeverWindow) else f"{window.value} {window.unit}"


def _declared(which: Sequence[LedgerName], config_dir: Path) -> dict[LedgerName, CompactionPolicy]:
    """Each ledger's compaction, taken live and unbounded for this one pass, or a refusal.

    Asked before anything is read or written. A ledger `config/ledgers.json` still
    files as CSV has no door to move into; one with no compaction has nothing to
    say which days are packed; and a compaction that keeps less than the CSV was
    kept would delete, at its first live pass, days the CSV still held.
    """
    registry = LedgersConfig.from_json((config_dir / "ledgers.json").read_text(encoding="utf-8"))
    entries = {entry.name: entry for family in registry.families for entry in family.ledgers}
    tasks = config.load_gardener(config_dir).tasks
    declared: dict[LedgerName, CompactionPolicy] = {}
    for name in which:
        if name not in CSV_LEDGERS:
            raise RefusedError(f"{name.value}: no supported CSV layout in CSV_LEDGERS")
        row_contract(name)
        grain = entries[name].grain
        if grain is not Grain.RAW_AND_COMPACT:
            raise RefusedError(
                f"config/ledgers.json files {name.value} as {grain.value}, so it has no door "
                f"to move into yet: its entry becomes {Grain.RAW_AND_COMPACT.value} in the "
                "change that moves its writers and readers"
            )
        task = f"compact-{name.value}"
        policy = tasks.get(task)
        if not isinstance(policy, CompactionPolicy):
            raise RefusedError(
                f"config/gardener/{task}.json does not declare a compaction, so nothing can "
                "say which days the packing rule admits"
            )
        kept = CSV_LEDGERS[name].old_window
        if not config.compaction_reaches(policy, kept):
            raise RefusedError(
                f"config/gardener/{task}.json keeps daily_keep_days {policy.daily_keep_days} "
                f"and monthly_window {_spelled(policy.monthly_window)}, which does not reach "
                f"the window of {_spelled(kept)} that kept {name.value} on CSV, so its first "
                "live pass would delete days the CSV still held"
            )
        declared[name] = policy.model_copy(
            update={"dry_run": False, "monthly_window_dry_run": True}
        )
    return declared


def packs_here(state_dir: Path, config_dir: Path) -> bool:
    """Whether this root is the state tree the declarations in `config_dir` govern.

    Only `state/` beside `config/` is packed. Any other root - a trial run's tree
    inside it - is filed raw: nothing reads a packed trial root, and the trials
    task empties it.
    """
    return state_dir.resolve() == (config_dir.parent / ledger.STATE_DIRNAME).resolve()


def _pack(
    state_dir: Path,
    which: LedgerName,
    identity: WriterIdentity,
    *,
    policy: CompactionPolicy,
    today: date,
    months: Sequence[str],
) -> tuple[list[str], list[str], list[str]]:
    """Pack only the named months until a pass writes and deletes no selected period."""
    repo_root = state_dir.parent
    context = f"{root_label(state_dir)}: {which.value}"
    folders = tuple(policy.owns or ())
    written: list[str] = []
    deleted: list[str] = []
    packed: set[str] = set()
    while True:
        try:
            outcome = compaction.run(
                TaskContext(
                    state_dir=state_dir,
                    repo_root=repo_root,
                    today=today,
                    policy=policy,
                    run_id=identity.run_id,
                    attempt=identity.attempt,
                    job=ServerJob.RUN_TASKS,
                    shard=identity.shard,
                    git_sha=identity.git_sha,
                    owned_folders=folders,
                    listing=FileListing.from_paths(
                        repo_root, _packing_paths(state_dir, which, months), folders=folders
                    ),
                ),
                months=frozenset(months),
            )
        except ValueError as refusal:
            raise NotProvenError(f"{context}: packing refused: {refusal}") from refusal
        written.extend(outcome.written)
        deleted.extend(outcome.taken)
        for path in outcome.written:
            parts = path.split("/")
            if "daily" in parts:
                index = parts.index("daily")
                if len(parts) > index + 3 and parts[-1].endswith(".parquet"):
                    day_parts = (
                        *parts[index + 1 : index + 3],
                        parts[index + 3].removesuffix(".parquet"),
                    )
                    packed.add(date.fromisoformat("-".join(day_parts)).isoformat())
        if outcome.stopped_because is StopReason.FAILED:
            raise NotProvenError(
                f"{context}: the compaction refused at {outcome.resume_from}; CSV files are kept"
            )
        if outcome.written or outcome.taken:
            continue
        if outcome.stopped_because is not StopReason.EXHAUSTED:
            raise NotProvenError(
                f"{context}: the compaction stopped at {outcome.resume_from} without "
                "writing or deleting a period; CSV files are kept"
            )
        return sorted(packed), list(dict.fromkeys(written)), list(dict.fromkeys(deleted))


def _packing_paths(state_dir: Path, which: LedgerName, months: Sequence[str]) -> list[Path]:
    """Files in named raw and daily months, plus named periods' files and index metadata."""
    paths: set[Path] = set()
    for folder in month_directories(ledger.raw_root(state_dir, which), months):
        if folder.is_dir():
            paths.update(path for path in folder.rglob("*") if path.is_file())
    for folder in month_directories(
        ledger.compact_path(state_dir, which, Period.DAILY, f"{months[0]}-01").parents[2],
        months,
    ):
        if folder.is_dir():
            paths.update(path for path in folder.iterdir() if path.is_file())
    for month in sorted(set(months)):
        year, number = map(int, month.split("-"))
        for day in range(1, calendar.monthrange(year, number)[1] + 1):
            index = ledger.raw_index_path(state_dir, which, f"{month}-{day:02d}")
            if index.is_file():
                paths.add(index)
        for period, covers in ((Period.MONTHLY, month), (Period.YEARLY, month[:4])):
            for fmt in Format:
                path = ledger.compact_path(state_dir, which, period, covers, fmt=fmt)
                if path.is_file():
                    paths.add(path)
    for period in Period:
        for path in (
            ledger.compact_index_path(state_dir, which, period),
            ledger.watermark_path(state_dir, which, period),
        ):
            if path.is_file():
                paths.add(path)
    return sorted(paths)


def _drop_empty_parents(path: Path, root: Path) -> None:
    """Remove named empty parents without listing their siblings."""
    folder = path.parent
    while folder == root or root in folder.parents:
        try:
            folder.rmdir()
        except OSError as refusal:
            if refusal.errno in (errno.ENOTEMPTY, errno.EEXIST):
                return
            raise
        if folder == root:
            return
        folder = folder.parent


def prove(
    state_dir: Path,
    which: LedgerName,
    day: str,
    rows: Sequence[dict[str, str]],
    *,
    output_required: bool = False,
    source_rows: Sequence[dict[str, str]] = (),
) -> None:
    """The day reads back through the door as exactly these rows, cell for cell, or a refusal."""
    context = f"{root_label(state_dir)}: {which.value} {day}"
    try:
        _check_output(state_dir, which, day, required=output_required or bool(rows))
        readback = _door_rows(state_dir, which, day)
    except (ValueError, OSError) as refusal:
        raise NotProvenError(f"{context}: {refusal}") from refusal
    key = ledger.door_key(which)
    back = {_key_of(cells, key): cells for cells in readback}
    wanted = {_key_of(cells, key): cells for cells in rows}
    if back.keys() != wanted.keys():
        raise NotProvenError(
            f"{context} reads back {len(back)} rows where {len(wanted)} were filed; "
            f"missing {sorted(wanted.keys() - back.keys())[:3]}, "
            f"invented {sorted(back.keys() - wanted.keys())[:3]}"
        )
    for record, cells in wanted.items():
        for column, cell in cells.items():
            if back[record].get(column) != cell:
                raise NotProvenError(
                    f"{context} row {','.join(record)} reads back "
                    f"{column}={back[record].get(column)!r} where {cell!r} was filed"
                )
    for cells in folded([], source_rows, key):
        record = _key_of(cells, key)
        if record not in back:
            raise NotProvenError(f"{context}: missing CSV source key {','.join(record)}")
        for column, cell in cells.items():
            if column != day_shards.VERSION_CELL and cell and back[record].get(column) != cell:
                raise NotProvenError(
                    f"{context} row {','.join(record)} reads back "
                    f"{column}={back[record].get(column)!r} where the CSV supplies {cell!r}"
                )


def _identity(run_id: str, git_sha: str) -> WriterIdentity:
    return WriterIdentity(
        run_id=run_id,
        attempt=ATTEMPT,
        job=ServerJob.MIGRATE,
        shard=SHARD,
        producer=PRODUCER,
        git_sha=git_sha,
    )


def migrate(
    state_dir: Path,
    which: Sequence[LedgerName],
    *,
    run_id: str,
    git_sha: str,
    today: date,
    config_dir: Path = config.DEFAULT_CONFIG_DIR,
    months: Sequence[str],
) -> list[Moved]:
    """Move these ledgers' CSV days onto the door, pack what the rule admits, prove, then delete.

    Each step covers every ledger before the next starts, so a refusal deletes
    no CSV of any ledger. Raises `RefusedError` before anything is read when a
    ledger cannot move yet, and `NotProvenError` naming the first day that did not
    come across. Only the state tree beside `config_dir` is packed.
    """
    return [
        report
        for _, report in migrate_roots(
            MigrationInputs(
                state_dirs=(state_dir,),
                which=which,
                run_id=run_id,
                git_sha=git_sha,
                today=today,
                config_dir=config_dir,
                months=months,
            )
        )
    ]


type Planned = dict[LedgerName, dict[str, PlannedDay]]


@dataclass(frozen=True, slots=True, kw_only=True)
class MigrationInputs:
    """The immutable named roots, ledgers, months and writer inputs of one migration."""

    state_dirs: Sequence[Path]
    which: Sequence[LedgerName]
    run_id: str
    git_sha: str
    today: date
    config_dir: Path = config.DEFAULT_CONFIG_DIR
    months: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "state_dirs", tuple(dict.fromkeys(path.resolve() for path in self.state_dirs))
        )
        object.__setattr__(self, "which", tuple(dict.fromkeys(self.which)))
        object.__setattr__(self, "months", tuple(self.months))


@dataclass(slots=True)
class RootPlan:
    """The validated named inputs and in-memory rows of one migration root."""

    state_dir: Path
    planned: Planned
    reports: dict[LedgerName, Moved]
    policies: dict[LedgerName, CompactionPolicy]
    identity: WriterIdentity
    inputs: MigrationInputs


def plan_roots(inputs: MigrationInputs) -> list[RootPlan]:
    """Validate and preview every named input without writing or deleting files."""
    identity = _identity(inputs.run_id, inputs.git_sha)
    month_directories(Path(), inputs.months)
    policies = _declared(inputs.which, inputs.config_dir)
    plans: list[RootPlan] = []
    for root in inputs.state_dirs:
        planned = {name: _plan(root, name, inputs.months) for name in inputs.which}
        reports = {name: Moved(which=name, days=len(days)) for name, days in planned.items()}
        for name, days in planned.items():
            for held in days.values():
                report = reports[name]
                report.csv_files += len(held.files)
                report.csv_bytes += sum(path.stat().st_size for path in held.files)
                report.rows += len(held.rows)
        plans.append(RootPlan(root, planned, reports, policies, identity, inputs))
    return plans


def write_roots(plans: Sequence[RootPlan]) -> list[tuple[Path, Moved]]:
    """File and pack a complete plan, never deleting its CSV sources."""
    for plan in plans:
        for name, days in plan.planned.items():
            for day, held in days.items():
                if held.changed:
                    ledger.persist(
                        plan.state_dir, held.models, ledger=name, covers=day, identity=plan.identity
                    )
                    plan.reports[name].filed += 1
    for plan in plans:
        if not packs_here(plan.state_dir, plan.inputs.config_dir):
            continue
        for name in plan.planned:
            packed, written, deleted = _pack(
                plan.state_dir,
                name,
                plan.identity,
                policy=plan.policies[name],
                today=plan.inputs.today,
                months=plan.inputs.months,
            )
            report = plan.reports[name]
            report.packed = packed
            report.compaction_written = written
            report.compaction_deleted = deleted
    return collect_reports(plans)


def verify_roots(plans: Sequence[RootPlan]) -> list[tuple[Path, Moved]]:
    """Prove every planned day, with the CSV's filled cells as independent evidence."""
    _prove_roots(plans, output_required=True)
    return collect_reports(plans)


def _prove_roots(plans: Sequence[RootPlan], *, output_required: bool) -> None:
    """Prove planned equality first, then independently check each filled source cell."""
    for plan in plans:
        for name, days in plan.planned.items():
            for day, held in days.items():
                prove(
                    plan.state_dir,
                    name,
                    day,
                    held.rows,
                    output_required=output_required,
                    source_rows=held.source_rows,
                )


def collect_reports(plans: Sequence[RootPlan]) -> list[tuple[Path, Moved]]:
    return [(plan.state_dir, report) for plan in plans for report in plan.reports.values()]


def _delete_sources(plans: Sequence[RootPlan]) -> None:
    for plan in plans:
        for name, days in plan.planned.items():
            for held in days.values():
                for path in held.files:
                    path.unlink()
                    _drop_empty_parents(path, csv_root(plan.state_dir, name))


def retire_roots(inputs: MigrationInputs) -> list[tuple[Path, Moved]]:
    """Re-read and prove all named roots in this process before deleting any CSV."""
    plans = plan_roots(inputs)
    reports = verify_roots(plans)
    _delete_sources(plans)
    return reports


def migrate_roots(inputs: MigrationInputs) -> list[tuple[Path, Moved]]:
    """Keep the full migration API: plan, file, pack, prove all roots, then delete."""
    plans = plan_roots(inputs)
    reports = write_roots(plans)
    _prove_roots(plans, output_required=False)
    _delete_sources(plans)
    return reports
