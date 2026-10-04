"""Which CSV files sit in the named UTC months of a ledger's old layout, day by day?"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path

from idhazh import day_shards
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from utilities.ledger_migration.csv_layouts import csv_root, require_layout
from utilities.ledger_migration.inputs import require_root
from utilities.ledger_migration.path_labels import describe_error, label_path
from utilities.ledger_migration.refusals import NotProvenError
from utilities.named_inputs import month_directories


def csv_days(state_dir: Path, which: LedgerName, *, months: Sequence[str]) -> dict[str, list[Path]]:
    """CSV days in the named months, to the files in each, oldest day first.

    The day tree and shared day-file layouts are read. Any other layout, or a
    path either layout cannot place, is refused rather than read as empty.
    """
    sat = require_layout(which).grain
    if sat is Grain.DAY_FILE:
        return _shared_day_files(csv_root(state_dir, which), which, months=months)
    root = csv_root(state_dir, which)
    days: dict[str, list[Path]] = {}
    for folder in _csv_months(root, which, months):
        for path in sorted(folder.iterdir()):
            parsed = date.fromisoformat(f"{folder.parent.name}-{folder.name}-{path.name}")
            if path.is_symlink() or not path.is_dir() or parsed.strftime("%d") != path.name:
                raise ValueError(f"{path.name} is not a DD directory in the day-tree layout")
            day = parsed.isoformat()
            days[day] = day_shards.one_day(root, day)
    return days


def _csv_months(root: Path, which: LedgerName, months: Sequence[str]) -> list[Path]:
    """Only declared month directories, refusing symlinks or a malformed named path."""
    folders = month_directories(root, months)
    found: list[Path] = []
    for folder in folders:
        for named in (root, folder.parent, folder):
            if named.is_symlink() or (named.exists() and not named.is_dir()):
                raise ValueError(f"{named.name} is not a CSV directory")
        if folder.is_dir():
            found.append(folder)
    return found


def _shared_day_files(
    root: Path, which: LedgerName, *, months: Sequence[str]
) -> dict[str, list[Path]]:
    """Shared day files in named months, refusing malformed paths inside those months."""
    days: dict[str, list[Path]] = {}
    for month in _csv_months(root, which, months):
        for path in sorted(month.iterdir()):
            try:
                parsed = date.fromisoformat(f"{month.parent.name}-{month.name}-{path.stem}")
            except ValueError as refusal:
                raise ValueError(
                    f"{path.relative_to(root).as_posix()} is not a "
                    "YYYY/MM/DD.csv file in the shared day-file layout"
                ) from refusal
            if (
                not path.is_file()
                or path.is_symlink()
                or path.suffix != ".csv"
                or parsed.strftime("%d") != path.stem
            ):
                raise ValueError(
                    f"{path.relative_to(root).as_posix()} is not a "
                    "YYYY/MM/DD.csv file in the shared day-file layout"
                )
            days[parsed.isoformat()] = [path]
    return days


def left(state_dir: Path, which: Sequence[LedgerName], *, months: Sequence[str]) -> list[Path]:
    """CSV files remaining in the named months of these ledgers."""
    require_root(state_dir)
    remaining: list[Path] = []
    for name in which:
        try:
            days = csv_days(state_dir, name, months=months)
        except (ValueError, OSError) as refusal:
            raise NotProvenError(
                f"{label_path(state_dir)}: {name.value}: {describe_error(refusal)}"
            ) from refusal
        remaining.extend(path for files in days.values() for path in files)
    return remaining
