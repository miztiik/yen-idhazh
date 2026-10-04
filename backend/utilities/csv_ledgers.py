"""Which named CSV day files and retention windows did each supported ledger use?"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from os.path import relpath
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, NamedTuple, cast

from idhazh import config, day_shards, ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.eval_row import RENAMED_CELLS
from idhazh.contracts.item_health import RETIRED_CELLS
from idhazh.contracts.knobs.gardener import DaysWindow, ForeverWindow, MonthsWindow, Window
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry
from utilities.named_inputs import month_directories


class CsvLedger(NamedTuple):
    """How one ledger was filed before it moved to the door, and how long it was kept."""

    old_entry: LedgerEntry
    old_window: Window
    old_headings: Mapping[str, str | None] = MappingProxyType({})


def _tree(name: LedgerName, folder: str | None = None) -> LedgerEntry:
    """A CSV day tree, one file a writer a day, under its own name unless it sat elsewhere."""
    return LedgerEntry(name=name, grain=Grain.DAY_TREE, prefix=(folder or name.value,))


def _day_file(name: LedgerName) -> LedgerEntry:
    """One shared CSV file a day, under the ledger's own name."""
    return LedgerEntry(name=name, grain=Grain.DAY_FILE, prefix=(name.value,), suffix=".csv")


CSV_LEDGERS: Final[Mapping[LedgerName, CsvLedger]] = MappingProxyType(
    {
        # The full-grain series of the telemetry-aggregate task deleted it.
        LedgerName.ITEM_HEALTH: CsvLedger(
            _tree(LedgerName.ITEM_HEALTH), MonthsWindow(unit="months", value=14),
            RETIRED_CELLS,
        ),
        # Filed under `scores/`, its name before it was renamed. No eval row is deleted.
        LedgerName.SUMMARY_QUALITY_EVALS: CsvLedger(
            _tree(LedgerName.SUMMARY_QUALITY_EVALS, "scores"), ForeverWindow(unit="forever"),
            RENAMED_CELLS,
        ),
        # The host-fingerprint retention task deleted it, until its compaction took over.
        LedgerName.HOST_FINGERPRINT: CsvLedger(
            _tree(LedgerName.HOST_FINGERPRINT), MonthsWindow(unit="months", value=14)
        ),
        LedgerName.COUNTERFACTUAL_SCORES: CsvLedger(
            _tree(LedgerName.COUNTERFACTUAL_SCORES), DaysWindow(unit="days", value=30)
        ),
        # Nothing deletes a candidate's verdict.
        LedgerName.CANDIDATE_MODELS: CsvLedger(
            _tree(LedgerName.CANDIDATE_MODELS), ForeverWindow(unit="forever")
        ),
        LedgerName.FEED_HEALTH: CsvLedger(
            _tree(LedgerName.FEED_HEALTH), MonthsWindow(unit="months", value=14)
        ),
        LedgerName.SEEN: CsvLedger(_day_file(LedgerName.SEEN), DaysWindow(unit="days", value=90)),
        # Nothing deletes a published record: forgetting one republishes it.
        LedgerName.PUBLISHED: CsvLedger(
            _day_file(LedgerName.PUBLISHED), ForeverWindow(unit="forever")
        ),
    }
)
# Removal condition: delete the table and migration modules when no program-written CSV remains.


class NotProvenError(Exception):
    """A day would not read, or did not come across whole, so nothing is deleted. Exit 1."""


class RefusedError(Exception):
    """A ledger the run names cannot move yet, so nothing is read or written. Exit 1."""


def csv_root(state_dir: Path, which: LedgerName) -> Path:
    """Where this ledger's CSV sat under a state root: the prefix its old entry names."""
    return state_dir.joinpath(*_require_layout(which).prefix)


def label_path(path: Path) -> str:
    """Render a checkout-relative POSIX path, or its folder name on another drive."""
    try:
        return Path(relpath(path.resolve(), config.DEFAULT_CONFIG_DIR.parent)).as_posix()
    except ValueError:
        return path.name


def describe_error(error: ValueError | OSError) -> str:
    """Render filesystem failures without absolute paths or platform separators."""
    if not isinstance(error, OSError):
        return str(error)
    paths = [
        label_path(Path(name)) for name in (error.filename, error.filename2) if name is not None
    ]
    return ": ".join([error.strerror or "filesystem operation failed", *paths])


def require_root(state_dir: Path) -> None:
    """Refuse a named root that is not an existing directory."""
    try:
        exists = state_dir.is_dir()
    except OSError as refusal:
        raise NotProvenError(f"{label_path(state_dir)}: {describe_error(refusal)}") from refusal
    if not exists:
        raise NotProvenError(f"{label_path(state_dir)}: not an existing directory")


def _require_layout(which: LedgerName) -> LedgerEntry:
    if which not in CSV_LEDGERS:
        raise RefusedError(f"{which.value}: no supported CSV layout in CSV_LEDGERS")
    entry = CSV_LEDGERS[which].old_entry
    if len(entry.prefix) != 1 or entry.grain not in (Grain.DAY_TREE, Grain.DAY_FILE):
        raise RefusedError(
            f"{which.value}: unsupported CSV layout {entry.grain.value} "
            f"under {'/'.join(entry.prefix)}"
        )
    return entry


def door_ledgers() -> list[LedgerName]:
    """Every ledger in the table that `config/ledgers.json` files through the door now."""
    return [name for name in CSV_LEDGERS if ledger.entry(name).grain is Grain.RAW_AND_COMPACT]


def row_contract(which: LedgerName) -> type[Any]:
    """The door's row contract for this ledger, as the CSV reader takes it.

    The door table pairs a ledger with a `Contract`, and every ledger that was ever
    filed as CSV has one that also reads and writes a CSV row. The types cannot say
    the second of a `Contract` in general, so it is said here, once.
    """
    entry = _require_layout(which)
    model = ledger.door_contract(which)
    if not callable(getattr(model, "csv_row", None)):
        raise RefusedError(f"{which.value}: {model.__name__} has no csv_row()")
    if entry.grain is Grain.DAY_TREE and not callable(getattr(model, "from_csv_row", None)):
        raise RefusedError(f"{which.value}: a CSV day tree needs {model.__name__}.from_csv_row()")
    return cast("type[Any]", model)


def read_csv_cells(
    model: type[Any],
    cells: dict[str, str],
    old_headings: Mapping[str, str | None] = MappingProxyType({}),
) -> Contract:
    """Refuse undeclared cell loss, then decode the declared fields and old headings."""
    if None in cells:
        raise ValueError("a CSV value has no heading")
    for heading, value in cells.items():
        if heading in old_headings:
            target = old_headings[heading]
            if target is not None and value and cells.get(target) and cells[target] != value:
                raise ValueError(f"heading {heading!r} conflicts with filled heading {target!r}")
        elif heading not in model.model_fields and value:
            raise ValueError(f"filled heading {heading!r} is not declared")
    cells = {
        heading: value
        for heading, value in cells.items()
        if (
            old_headings[heading] is not None
            if heading in old_headings else heading in model.model_fields
        )
    }
    from_csv_row = getattr(model, "from_csv_row", None)
    return cast(
        "Contract",
        from_csv_row(cells) if callable(from_csv_row) else model.model_validate(cells),
    )


class _CsvReader:
    """Adapt the common cell reader to the existing day-shard settlement interface."""

    def __init__(self, model: type[Any], old_headings: Mapping[str, str | None]) -> None:
        self.model = model
        self.old_headings = old_headings
        self.__name__ = model.__name__

    def from_csv_row(self, cells: dict[str, str]) -> ledger.CsvRecord:
        return cast("ledger.CsvRecord", read_csv_cells(self.model, cells, self.old_headings))


def csv_days(state_dir: Path, which: LedgerName, *, months: Sequence[str]) -> dict[str, list[Path]]:
    """CSV days in the named months, to the files in each, oldest day first.

    The day tree and shared day-file layouts are read. Any other layout, or a
    path either layout cannot place, is refused rather than read as empty.
    """
    sat = _require_layout(which).grain
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


def read_csv_rows(
    state_dir: Path,
    which: LedgerName,
    day: str,
    files: Sequence[Path],
    key: tuple[str, ...],
    model: type[Any],
) -> list[dict[str, str]]:
    """Read one day's CSV rows through its declared layout and row contract."""
    layout = _require_layout(which)
    old_headings = CSV_LEDGERS[which].old_headings
    if layout.grain is Grain.DAY_TREE:
        # The shard reader uses only from_csv_row and __name__ on this adapter.
        reader = cast("type[ledger.CsvContract]", _CsvReader(model, old_headings))
        return day_shards.settled_day(csv_root(state_dir, which), day, key, reader)
    if len(files) != 1:
        raise ValueError("a shared day must have exactly one CSV file")
    rows: list[dict[str, str]] = []
    for path in files:
        for number, raw in day_shards.rows_of(path):
            try:
                rows.append(
                    cast("ledger.CsvRecord", read_csv_cells(model, raw, old_headings)).csv_row()
                )
            except ValueError as refusal:
                raise ValueError(f"{path.name} row {number}: {refusal}") from refusal
    return rows


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
