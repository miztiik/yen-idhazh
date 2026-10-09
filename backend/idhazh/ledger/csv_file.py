"""How one ledger's rows are read out of a CSV file and written back into it.

A row is rendered in exactly one place, so a row a re-file writes and a file
written whole are the same bytes. Written two ways, a file one pass touched
would read as changed line by line the next time anything diffed it.

Nothing here knows which ledger it is reading. The file is handed in, so this
module can be driven by a caller that names a ledger nobody declared here.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol


class CsvRecord(Protocol):
    """A contract that knows how to write itself as one row of a `state/` file.

    Every ledger here takes one of these rather than a `dict[str, str]`. A dict
    is not a contract - anything can build one and nothing validates it - so a
    caller assembling cells by hand could reach a committed file without a model
    having seen them. Declared as a protocol rather than as a base class because
    these contracts share a shape, not an ancestor: `Contract` is the base for
    every persisted document, and most of those are JSON and have no row.
    """

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, keyed by column name."""
        ...


class CsvContract(Protocol):
    """The class side of `CsvRecord`: the columns, and the reader for an old row."""

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The row's columns, in the row's own order."""
        ...

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> CsvRecord:
        """One row read back, under any heading this ledger has ever carried."""
        ...


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(next(csv.reader(handle), []))


def require_matching_header(path: Path, columns: tuple[str, ...]) -> None:
    header = read_header(path)
    if header and header != columns:
        raise ValueError(
            f"{path.name} has {len(header)} columns and the contract has "
            f"{len(columns)}. Migrate the ledger before appending to it."
        )


def _csv_line(columns: tuple[str, ...], payload: dict[str, str]) -> str:
    """One row, written the way `render_file` writes one.

    A re-filed row and a row of a file written whole have to be the same bytes,
    or the file a migration leaves behind is a file the next writer disagrees
    with.
    """
    buffer = io.StringIO()
    csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n").writerow(
        {name: payload[name] for name in columns}
    )
    return buffer.getvalue()


def render_file(columns: tuple[str, ...], rows: Iterable[Mapping[str, str]]) -> str:
    """A whole ledger file as one document: the header, then every row.

    Beside `_csv_line` because a file written whole and a row a re-file writes
    have to be the same bytes. Written two ways, a file one pass touched would
    read as changed line by line the next time anything diffed it.

    Returned rather than written, so the caller owns the temp-file-plus-rename
    and this module keeps its rule that a row is rendered in exactly one place.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for payload in rows:
        writer.writerow({name: payload[name] for name in columns})
    return buffer.getvalue()


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
