"""What will each named root's door hold once its CSV days fold on, before anything is written?"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName
from utilities.ledger_migration.csv_cells import read_csv_cells, read_csv_rows, row_contract
from utilities.ledger_migration.csv_files import csv_days
from utilities.ledger_migration.fold import folded
from utilities.ledger_migration.identity import writer_identity
from utilities.ledger_migration.inputs import MigrationInputs, require_root
from utilities.ledger_migration.packing import policies_for_roots
from utilities.ledger_migration.path_labels import describe_error, label_path
from utilities.ledger_migration.readback import check_output, door_rows, migration_rows
from utilities.ledger_migration.refusals import NotProvenError
from utilities.named_inputs import month_directories


@dataclass(slots=True)
class PlannedDay:
    """Expected reader rows and migration-owned writes for one ledger day."""

    files: list[Path]
    #: The expected total after the arriving CSV rows fold onto the reader.
    rows: list[dict[str, str]]
    #: Migration-owned rows only, including its earlier rows absent from this CSV.
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


type Planned = dict[LedgerName, dict[str, PlannedDay]]


@dataclass(slots=True)
class RootPlan:
    """The validated named inputs and in-memory rows of one migration root."""

    state_dir: Path
    planned: Planned
    reports: dict[LedgerName, Moved]
    policies: dict[LedgerName, CompactionPolicy | None]
    identity: WriterIdentity
    inputs: MigrationInputs


def _plan(
    state_dir: Path,
    which: LedgerName,
    months: Sequence[str],
    identity: WriterIdentity,
) -> dict[str, PlannedDay]:
    """Every CSV day of this ledger, folded onto what the door holds for it. Nothing written.

    Everything that can refuse a day's rows refuses here, before the first
    write. Reader expectations include every current writer; the write set
    includes only this migration's prior rows and the arriving CSV rows.
    """
    model, key = row_contract(which), ledger.door_key(which)
    planned: dict[str, PlannedDay] = {}
    label = f"{label_path(state_dir)}: {which.value}"
    try:
        days = csv_days(state_dir, which, months=months)
    except (ValueError, OSError) as refusal:
        raise NotProvenError(f"{label}: {describe_error(refusal)}") from refusal
    for day, files in days.items():
        context = f"{label} {day}"
        try:
            arriving = read_csv_rows(state_dir, which, day, files, key, model)
        except (ValueError, OSError) as refusal:
            raise NotProvenError(f"{context}: {describe_error(refusal)}") from refusal
        stray = sorted({cells["date"] for cells in arriving if cells.get("date")} - {day})
        if stray:
            raise NotProvenError(
                f"{context}: the CSV day holds rows dated {stray}, and the door "
                "files a row under its own date, so this day would not read back"
            )
        try:
            owned = migration_rows(state_dir, which, day, identity)
            check_output(state_dir, which, day, required=False)
            held = door_rows(state_dir, which, day)
        except (ValueError, OSError) as refusal:
            raise NotProvenError(f"{context}: {describe_error(refusal)}") from refusal
        rows = folded(held, arriving, key)
        owned_rows = folded(owned, arriving, key)
        changed = owned_rows != owned
        try:
            models = [read_csv_cells(model, cells) for cells in owned_rows] if changed else []
        except ValueError as refusal:
            raise NotProvenError(
                f"{context}: a migration row is not a {model.__name__} the door can file: "
                f"{refusal}"
            ) from refusal
        planned[day] = PlannedDay(
            files=files, rows=rows, models=models, changed=changed, source_rows=arriving
        )
    return planned


def plan_roots(inputs: MigrationInputs) -> list[RootPlan]:
    """Validate and preview every named input without writing or deleting files."""
    for root in inputs.state_dirs:
        require_root(root)
    identity = writer_identity(inputs.run_id, inputs.git_sha)
    month_directories(Path(), inputs.months)
    policies = policies_for_roots(inputs.which, inputs.state_dirs, inputs.config_dir)
    plans: list[RootPlan] = []
    for root in inputs.state_dirs:
        planned = {
            name: _plan(root, name, inputs.months, identity) for name in inputs.which
        }
        reports = {name: Moved(which=name, days=len(days)) for name, days in planned.items()}
        for name, days in planned.items():
            for held in days.values():
                report = reports[name]
                report.csv_files += len(held.files)
                report.csv_bytes += sum(path.stat().st_size for path in held.files)
                report.rows += len(held.rows)
        plans.append(RootPlan(root, planned, reports, policies[root], identity, inputs))
    return plans


def collect_reports(plans: Sequence[RootPlan]) -> list[tuple[Path, Moved]]:
    """Each named root with each of its ledgers' reports, root by root."""
    return [(plan.state_dir, report) for plan in plans for report in plan.reports.values()]
