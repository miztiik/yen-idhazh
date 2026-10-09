"""How a contract writes its rows as one CSV document, and how a CSV file's header is checked.

No ledger in the registry is CSV. Two kinds of CSV file are left: the files
one job of a workflow hands the next, and the label file a person appends to
(`evals/labels.py`). A row is rendered here in exactly one place, so two
callers that write the same rows write the same bytes.

Nothing here knows which file it is writing. The columns and the rows are
handed in, so this module can be driven by a caller that names a file nobody
declared here.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol


class CsvRecord(Protocol):
    """A contract that knows how to write itself as one row of a CSV file.

    A caller takes one of these rather than a `dict[str, str]`. A dict is not a
    contract - anything can build one and nothing validates it - so a caller
    assembling cells by hand could write a file without a model having seen
    them. Declared as a protocol rather than as a base class because these
    contracts share a shape, not an ancestor: `Contract` is the base for every
    persisted document, and most of those are JSON and have no row.
    """

    def csv_row(self) -> dict[str, str]:
        """Every cell a string, keyed by column name."""
        ...


class CsvContract(Protocol):
    """The class side of `CsvRecord`: the columns, and the reader for one row."""

    @classmethod
    def csv_columns(cls) -> tuple[str, ...]:
        """The row's columns, in the row's own order."""
        ...

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> CsvRecord:
        """One row read back, under any heading this row has ever carried."""
        ...


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(next(csv.reader(handle), []))


def require_matching_header(path: Path, columns: tuple[str, ...]) -> None:
    header = read_header(path)
    if header and header != columns:
        raise ValueError(
            f"{path.name} has {len(header)} columns and the contract has "
            f"{len(columns)}. Migrate the file before appending to it."
        )


def render_file(columns: tuple[str, ...], rows: Iterable[Mapping[str, str]]) -> str:
    """A whole CSV file as one document: the header, then every row.

    Returned rather than written, so the caller owns the temp-file-plus-rename
    and this module keeps its rule that a row is rendered in exactly one place.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for payload in rows:
        writer.writerow({name: payload[name] for name in columns})
    return buffer.getvalue()