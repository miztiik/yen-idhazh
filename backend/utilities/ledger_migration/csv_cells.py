"""How is one CSV day read through its row contract without losing a filled cell?"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from idhazh import day_shards, ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from utilities.ledger_migration import csv_layouts
from utilities.ledger_migration.refusals import RefusedError


def row_contract(which: LedgerName) -> type[Any]:
    """The door's row contract for this ledger, as the CSV reader takes it.

    The door table pairs a ledger with a `Contract`, and every ledger that was ever
    filed as CSV has one that also reads and writes a CSV row. The types cannot say
    the second of a `Contract` in general, so it is said here, once.
    """
    entry = csv_layouts.require_layout(which)
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


def read_csv_rows(
    state_dir: Path,
    which: LedgerName,
    day: str,
    files: Sequence[Path],
    key: tuple[str, ...],
    model: type[Any],
) -> list[dict[str, str]]:
    """Read one day's CSV rows through its declared layout and row contract.

    A one-file layout holds every day in one file, so only the rows whose declared
    day cell names this day are read.
    """
    layout = csv_layouts.require_layout(which)
    # Read through its module, so a table replaced while running is the one read.
    held = csv_layouts.CSV_LEDGERS[which]
    old_headings = held.old_headings
    if layout.grain is Grain.DAY_TREE:
        # The shard reader uses only from_csv_row and __name__ on this adapter.
        reader = cast("type[ledger.CsvContract]", _CsvReader(model, old_headings))
        return day_shards.settled_day(csv_layouts.csv_root(state_dir, which), day, key, reader)
    if len(files) != 1:
        raise ValueError("a shared day must have exactly one CSV file")
    rows: list[dict[str, str]] = []
    for path in files:
        for number, raw in day_shards.rows_of(path):
            if layout.grain is Grain.FLAT and raw.get(held.day_column or "") != day:
                continue
            try:
                rows.append(
                    cast("ledger.CsvRecord", read_csv_cells(model, raw, old_headings)).csv_row()
                )
            except ValueError as refusal:
                raise ValueError(f"{path.name} row {number}: {refusal}") from refusal
    return rows
