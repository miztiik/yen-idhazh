"""Which published column has a heading on every row and a value on none.

**An operator script, never a test.** Answering it means opening every committed
day file of every store, which costs more as the archive grows (CLAUDE.md
Guardrail #12) and which section 13 forbids a test to do. It would put a fuse on
the answer besides: a test asserting a column empty goes red the day that column
first fills, which is a date on the calendar rather than an edit anybody made. So
it lives here, where pytest does not collect it.

Run it from the repository root:

    python backend/utilities/empty_column_census.py

**What it settles.** For each store, which columns of the contract carry a value
somewhere in the committed archive and which carry one nowhere - and, crossed
with the reader maps on the contracts themselves, which columns have neither a
reader nor a writer. That last set is the one to act on: a column nobody draws
and nobody fills is a heading on every row of every run, answering nobody. The
run exits 1 when that set is not empty, so an operator gets a verdict and not
only a table.

**What it does not settle.** Whether an empty column is WRONG. A column that
records a failure nothing has hit yet is empty and correct, and one whose probe
is absent on every runner this project has met is empty and dead. This report
cannot tell the two apart; it says which columns are worth asking about.

**Why the headings are pooled rather than read from the newest file.** A day file
carries the columns the run that wrote it named, so an archive spanning a schema
change holds several widths. Reading one file's header would report every column
added since as missing, and every column dropped before as present.
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final, NamedTuple

from idhazh import day_partition
from idhazh.contracts.host_fingerprint import COLUMN_READERS as HOST_READERS
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.item_health import COLUMN_READERS as ITEM_READERS
from idhazh.contracts.item_health import RETIRED_CELLS, UNREAD_CELLS, ItemHealthRow


class Store(NamedTuple):
    """One day-partitioned ledger, and what it takes to read its headings."""

    #: What the report calls it, in the words a person uses for the thing.
    title: str
    #: Where the day files live, relative to the repository root.
    root: str
    #: The columns the contract names today.
    columns: tuple[str, ...]
    #: Headings an earlier run wrote, and the column each is read into now. A
    #: cell under a retired heading fills the column that replaced it, because
    #: that is what the row's own reader does - a census that skipped them would
    #: call a filled column empty.
    carried: Mapping[str, str]
    #: The columns no surface reads, pooled from the contract's own grouping.
    unread: frozenset[str]


STORES: Final[tuple[Store, ...]] = (
    Store(
        title="item health",
        root="state/item-health",
        columns=tuple(ItemHealthRow.csv_columns()),
        carried=RETIRED_CELLS,
        unread=frozenset(
            name for names in UNREAD_CELLS.values() for name in names
        ),
    ),
    Store(
        title="host fingerprint",
        root="state/host-fingerprint",
        columns=tuple(HostFingerprintRow.csv_columns()),
        carried={},
        unread=frozenset(),
    ),
)

#: Which contract module names the reader of each store's columns, so the report
#: can say where to go and not only what is wrong.
READERS: Final[Mapping[str, Mapping[str, Sequence[str]]]] = {
    "item health": ITEM_READERS,
    "host fingerprint": HOST_READERS,
}


class Census(NamedTuple):
    """What one store's committed archive holds, counted once."""

    filled: frozenset[str]
    headed: frozenset[str]
    rows: int
    files: int


def census(root: Path, store: Store) -> Census:
    """Open every committed day file of one store and pool what it carries.

    **This is the growing read.** A bounded input cannot answer it: the question
    is whether ANY run has ever written the column, and a window answers only
    for the days inside it - so a column retired last year would be reported as
    one nothing was ever wired to write.
    """
    filled: set[str] = set()
    headed: set[str] = set()
    rows = 0
    files = 0
    for path in day_partition.day_files(root / store.root):
        files += 1
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headed.update(
                store.carried.get(name, name) for name in reader.fieldnames or ()
            )
            for row in reader:
                rows += 1
                filled.update(
                    store.carried.get(name, name)
                    for name, cell in row.items()
                    if cell and cell.strip()
                )
    known = frozenset(store.columns)
    return Census(frozenset(filled) & known, frozenset(headed) & known, rows, files)


def reader_of(title: str, column: str) -> str:
    """The surface the contract names as this column's reader, or why there is none."""
    for path, columns in READERS[title].items():
        if column in columns:
            return path
    return "nothing reads it"


def report(root: Path) -> int:
    """Print one block a store, then the verdict. Non-zero means act."""
    orphans: list[str] = []
    for store in STORES:
        found = census(root, store)
        empty = tuple(name for name in store.columns if name not in found.filled)
        missing = tuple(name for name in store.columns if name not in found.headed)
        print(f"\n## {store.title}")
        print(
            f"{found.files} day files, {found.rows} rows, "
            f"{len(store.columns)} columns the contract names, "
            f"{len(found.headed)} of them under a heading somewhere"
        )
        if missing:
            print("\nNever under any heading - no run has written the column at all:")
            for name in missing:
                print(f"  {name:<34} {reader_of(store.title, name)}")
        print(f"\nEmpty on all {found.rows} committed rows ({len(empty)}):")
        for name in empty or ("- none -",):
            print(f"  {name:<34} {reader_of(store.title, name) if empty else ''}")
        both = tuple(name for name in empty if name in store.unread)
        orphans += [f"{store.title}: {name}" for name in both]

    print("\n## Neither a reader nor a writer")
    if not orphans:
        print("None. Every empty column is at least drawn somewhere.")
        return 0
    print(
        "Each of these costs a cell on every row of every run and answers nobody.\n"
        "Draw it, or delete it through DROPPED_CELLS - the contract refuses a\n"
        "silent removal, so the deletion is a migration and not a line edit.\n"
    )
    for orphan in orphans:
        print(f"  {orphan}")
    return 1


def main() -> int:
    return report(Path.cwd())


if __name__ == "__main__":
    sys.exit(main())
