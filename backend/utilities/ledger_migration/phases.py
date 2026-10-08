"""In what order do the write, verify, retire and full-chain phases run over a validated plan?"""

from __future__ import annotations

import errno
from collections.abc import Sequence
from pathlib import Path

from idhazh import config, ledger
from idhazh.contracts.ledgers import Grain
from utilities.ledger_migration.csv_files import flat_file_days
from utilities.ledger_migration.csv_layouts import csv_file, csv_root, require_layout
from utilities.ledger_migration.inputs import MigrationInputs
from utilities.ledger_migration.packing import pack, packs_here
from utilities.ledger_migration.path_labels import label_path
from utilities.ledger_migration.planning import Moved, RootPlan, collect_reports, plan_roots
from utilities.ledger_migration.proof import prove
from utilities.ledger_migration.refusals import NotProvenError


def write_roots(plans: Sequence[RootPlan], *, raw_only: bool = False) -> list[tuple[Path, Moved]]:
    """File a plan, optionally leaving production compaction for a later pass."""
    for plan in plans:
        for name, days in plan.planned.items():
            for day, held in days.items():
                if held.changed:
                    ledger.persist(
                        plan.state_dir, held.models, ledger=name, covers=day, identity=plan.identity
                    )
                    plan.reports[name].filed += 1
    if not raw_only:
        for plan in plans:
            if not packs_here(plan.state_dir, plan.inputs.config_dir):
                continue
            first_ledger_year = config.load_gardener(
                plan.inputs.config_dir
            ).config.first_ledger_year
            for name in plan.planned:
                policy = plan.policies[name]
                if policy is None:
                    continue
                packed, written, deleted = pack(
                    plan.state_dir,
                    name,
                    plan.identity,
                    repo_root=plan.inputs.config_dir.parent,
                    policy=policy,
                    today=plan.inputs.today,
                    months=plan.inputs.months,
                    first_ledger_year=first_ledger_year,
                )
                report = plan.reports[name]
                report.packed = packed
                report.compaction_written = written
                report.compaction_deleted = deleted
    return collect_reports(plans)


def verify_roots(plans: Sequence[RootPlan]) -> list[tuple[Path, Moved]]:
    """Prove every planned day, with the CSV's filled cells as independent evidence."""
    _prove_roots(plans)
    return collect_reports(plans)


def _prove_roots(plans: Sequence[RootPlan]) -> None:
    """Prove planned equality first, then independently check each filled source cell."""
    for plan in plans:
        for name, days in plan.planned.items():
            for day, held in days.items():
                prove(
                    plan.state_dir,
                    name,
                    day,
                    held.rows,
                    source_rows=held.source_rows,
                )


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


def _refuse_a_file_holding_unnamed_months(plans: Sequence[RootPlan]) -> None:
    """A one-file layout is deleted only when every month it holds was named and proved.

    The one file holds every day of its ledger, so deleting it after a run that
    named some of its months would delete the rows of the months it did not name,
    which nothing has copied. Asked of every root before any file is deleted.
    """
    for plan in plans:
        for name in plan.planned:
            if require_layout(name).grain is not Grain.FLAT:
                continue
            held = {day[:7] for day in flat_file_days(plan.state_dir, name)}
            unnamed = sorted(held - set(plan.inputs.months))
            if unnamed:
                raise NotProvenError(
                    f"{label_path(plan.state_dir)}: {name.value}: "
                    f"{csv_file(plan.state_dir, name).name} also holds rows of "
                    f"{', '.join(unnamed)}, so it is deleted only once every month it holds "
                    "is named"
                )


def _delete_sources(plans: Sequence[RootPlan]) -> None:
    _refuse_a_file_holding_unnamed_months(plans)
    for plan in plans:
        for name, days in plan.planned.items():
            sources = dict.fromkeys(path for held in days.values() for path in held.files)
            for path in sources:
                path.unlink()
                _drop_empty_parents(path, csv_root(plan.state_dir, name))


def retire_roots(inputs: MigrationInputs) -> list[tuple[Path, Moved]]:
    """Re-read and prove all named roots in this process before deleting any CSV."""
    plans = plan_roots(inputs)
    reports = verify_roots(plans)
    _delete_sources(plans)
    return reports


def migrate_roots(inputs: MigrationInputs) -> list[tuple[Path, Moved]]:
    """The full chain: plan, file, pack and prove every root, then delete."""
    plans = plan_roots(inputs)
    reports = write_roots(plans)
    _prove_roots(plans)
    _delete_sources(plans)
    return reports
