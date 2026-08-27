"""Rewrite `state/published.csv` without its `canonical_url` column.

One-shot, and committed rather than run by hand, so a fork or a stale branch
can reproduce the exact rewrite this repository ran (CLAUDE.md Rule #5). It is
safe to leave here after it has run: a ledger that already has the narrow shape
is refused rather than rewritten a second time.

The address is not lost with the column. `item_id` and `published_on` join to
that day's committed payload, where the address is published as `source_url`.
`docs/architecture/sources/freshness.md` holds the worked recovery.

Usage: `python backend/utilities/migrate_published_ledger.py [--state state]`,
from the root of a checkout.
"""

from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.assemble import write_atomic
from idhazh.contracts.seen import PublishedRow
from idhazh.ledger import published_path

#: The shape this migration reads. It is history rather than a knob, so it is
#: spelled here: the contract no longer describes the file being migrated.
WIDE_COLUMNS: Final[tuple[str, ...]] = (
    "version",
    "url_key",
    "canonical_url",
    "published_on",
    "item_id",
)

#: The two cells `ledger.load_published` opens. The rewrite has to leave every
#: one of them exactly where it was, or a published address becomes plannable.
READ_COLUMNS: Final[tuple[str, ...]] = ("url_key", "published_on")

# A migrated row keeps the `version` cell it was written with. The base contract
# accepts an older stamp on purpose, so a later read-side migration has
# something to branch on; restamping every row would erase the only marker of
# which rows predate the narrowing and would claim today's writer produced them.


@dataclass(frozen=True, slots=True)
class Migration:
    """The rewritten file and the numbers a reviewer will ask for."""

    text: str
    rows_in: int
    rows_out: int
    bytes_in: int
    bytes_out: int

    @property
    def saved(self) -> int:
        return self.bytes_in - self.bytes_out

    @property
    def saved_share(self) -> float:
        return self.saved / self.bytes_in if self.bytes_in else 0.0


def _pairs(text: str) -> list[tuple[str, ...]]:
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return [tuple(row[name] for name in READ_COLUMNS) for row in reader]


def narrow(text: str) -> Migration:
    """The four-column ledger, or a `ValueError` naming what stopped the rewrite."""
    columns = PublishedRow.csv_columns()
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = tuple(reader.fieldnames or ())
    if header == columns:
        raise ValueError("already the narrow shape, so there is nothing to migrate")
    if header != WIDE_COLUMNS:
        raise ValueError(
            f"expected the header {','.join(WIDE_COLUMNS)} and found {','.join(header)}"
        )

    rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(row[name] is None for name in WIDE_COLUMNS):
            raise ValueError(f"line {number} does not carry {len(WIDE_COLUMNS)} cells")

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row[name] for name in columns})
    narrowed = out.getvalue()

    # The Oracle. Same count, same pairs, same order - so nothing that was
    # skipped before this rewrite is plannable after it.
    if _pairs(text) != _pairs(narrowed):
        raise ValueError("the rewrite moved a pair the skip read uses, so nothing was written")

    return Migration(
        text=narrowed,
        rows_in=len(rows),
        rows_out=narrowed.count("\n") - 1,
        bytes_in=len(text.encode("utf-8")),
        bytes_out=len(narrowed.encode("utf-8")),
    )


def _relpath(path: Path) -> str:
    """POSIX and relative, because this string leaves the process (CLAUDE.md section 2)."""
    try:
        return path.resolve().relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="state", help="the state directory to migrate")
    args = parser.parse_args()

    path = published_path(Path(args.state))
    relpath = _relpath(path)
    if not path.is_file():
        raise SystemExit(f"{relpath} does not exist")

    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    try:
        report = narrow(text)
    except ValueError as error:
        raise SystemExit(f"{relpath}: {error}") from error

    write_atomic(path, report.text)
    print(f"{relpath}: {report.rows_in} rows in, {report.rows_out} rows out")
    print(
        f"{relpath}: {report.bytes_in} B before, {report.bytes_out} B after, "
        f"{report.saved} B less, {report.saved_share:.1%} of the file"
    )


if __name__ == "__main__":
    main()
