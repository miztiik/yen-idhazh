"""Move every row of `state/published.csv` into the day file its own date names.

One-shot, and committed rather than run by hand, so a fork or a stale branch can
reproduce the exact cutover this repository ran (CLAUDE.md Rule #5). It is safe
to leave here afterwards: a checkout with no flat file has nothing to split and
is told so.

The flat file is history. `ledger.append_published` files a row under
`state/published/YYYY/MM/DD.csv` now, and `ledger.load_published` reads both
shapes - so this utility only has to move the rows and take the old file away.

**Rows are copied, never rewritten.** The raw line goes across unchanged, cells,
order and bytes, so the `version` cell travels with the row it was written for
and a reader cannot tell which file a row came from.

**Run it when no scheduled digest is in flight.** `merge=union` is a content
driver and cannot resolve a delete against a modify, so a split racing a running
job conflicts and costs that job its push. The failure mode is redundancy rather
than loss - `load_published` reads both shapes, so a flat file a merge brings
back still answers and the next split removes it again.

This reads the whole ledger, which is the growing cost Rule #12 is about. It is
allowed here for two reasons and they are both narrow: this is an operator
command a person runs once, not a step of any run; and the read it performs is
the read `load_published` already performs on every run.

Usage: `python backend/utilities/split_published_ledger.py [--state state]`,
from the root of a checkout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.assemble import write_atomic
from idhazh.contracts.seen import PublishedRow

#: The file this cutover empties and removes. Spelled here rather than asked of
#: `idhazh.ledger` for the reason `migrate_published_ledger.WIDE_COLUMNS` is
#: spelled there: it is history, and no public path helper in the ledger names
#: it any more.
FLAT_FILENAME: Final = "published.csv"


@dataclass(frozen=True, slots=True)
class Split:
    """The day files the flat ledger becomes, and the numbers a reviewer asks for."""

    #: Digest date -> the raw data lines of the flat file that belong to it, in
    #: the order the flat file held them.
    lines: dict[str, list[str]]
    rows_in: int

    @property
    def rows_out(self) -> int:
        return sum(len(lines) for lines in self.lines.values())

    @property
    def days(self) -> int:
        return len(self.lines)


def _header_line() -> str:
    return ",".join(PublishedRow.csv_columns())


def _text(path: Path) -> str:
    """The file's bytes as text, with the line endings it really holds.

    Rows are copied verbatim, so nothing here may translate a newline on the
    way in - a reader that did would make a carriage return invisible to the
    check in `split` that refuses one.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _cells(line: str, number: int) -> tuple[str, ...]:
    columns = PublishedRow.csv_columns()
    rows = list(csv.reader([line]))
    if len(rows) != 1 or len(rows[0]) != len(columns):
        raise ValueError(f"line {number} does not carry {len(columns)} cells")
    return tuple(rows[0])


def _day_of(cells: tuple[str, ...], number: int) -> str:
    on = cells[PublishedRow.csv_columns().index("published_on")]
    try:
        date_type.fromisoformat(on)
    except ValueError as error:
        raise ValueError(f"line {number} publishes on {on!r}, which names no day file") from error
    if len(on) != 10:
        raise ValueError(f"line {number} publishes on {on!r}, which names no day file")
    return on


def split(text: str) -> Split:
    """The flat ledger grouped by day, or a `ValueError` naming what stopped it.

    A row nobody can place stops the whole split rather than being skipped. A
    file the reader cannot place is how it starts missing rows, and the same
    holds one level up: a row that lands nowhere is a published address that
    becomes plannable again.
    """
    if "\r" in text:
        raise ValueError("the ledger holds a carriage return, and rows are copied verbatim")
    parts = text.split("\n")
    if parts[-1] != "":
        raise ValueError("the ledger does not end with a newline")
    header, *rows = parts[:-1]
    if header != _header_line():
        raise ValueError(f"expected the header {_header_line()} and found {header}")

    lines: dict[str, list[str]] = {}
    for number, line in enumerate(rows, start=2):
        lines.setdefault(_day_of(_cells(line, number), number), []).append(line)
    return Split(lines=lines, rows_in=len(rows))


def digest(mapping: Mapping[str, str]) -> str:
    """sha256 over `url_key,published_on` per address, sorted. The reconciliation."""
    canonical = "".join(f"{key},{mapping[key]}\n" for key in sorted(mapping))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_day(path: Path, lines: list[str]) -> None:
    """Append this day's rows to its file, keeping whatever the file already holds.

    A day file can already exist: a run after the writer moved to the day layout
    files today's rows there while the flat file still holds an earlier run of
    the same day. Overwriting would lose that run, so the existing text is kept
    and the moved rows follow it.
    """
    head = _header_line() + "\n"
    existing = ""
    if path.is_file():
        existing = _text(path)
        if not existing.startswith(head):
            raise ValueError(f"{path.name} does not start with the header the contract writes")
    write_atomic(path, (existing or head) + "".join(f"{line}\n" for line in lines))


@dataclass(frozen=True, slots=True)
class Report:
    """What the split did, for the person who has to believe it."""

    rows_in: int
    rows_out: int
    days: int
    addresses: int
    digest: str
    paths: list[str]


def run(state_dir: Path) -> Report:
    """Move the rows, verify, and only then remove the flat file.

    The verification is the guarantee itself rather than a proxy for it: the
    mapping `load_published` returns is taken before anything moves, and the
    flat file is removed only once the same call returns it with the day tree
    alone answering.
    """
    flat = state_dir / FLAT_FILENAME
    if not flat.is_file():
        raise ValueError(f"{FLAT_FILENAME} does not exist, so there is nothing to split")

    text = _text(flat)
    before = ledger.load_published(state_dir)
    report = split(text)
    if report.rows_out != report.rows_in:
        raise ValueError(f"{report.rows_in} rows in and {report.rows_out} out, so a row was lost")

    for date in sorted(report.lines):
        _write_day(ledger.published_path(state_dir, date), report.lines[date])

    both = ledger.load_published(state_dir)
    if both != before:
        raise ValueError(
            f"the day files answer for {len(both)} addresses where the flat file "
            f"answered for {len(before)}, so the flat file was left alone"
        )

    flat.unlink()
    after = ledger.load_published(state_dir)
    if after != before:
        write_atomic(flat, text)
        raise ValueError(
            "the day tree alone does not answer what the flat file answered, so the "
            "flat file was put back"
        )

    return Report(
        rows_in=report.rows_in,
        rows_out=report.rows_out,
        days=report.days,
        addresses=len(after),
        digest=digest(after),
        paths=[ledger.published_relpath(date) for date in sorted(report.lines)],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="state", help="the state directory to split")
    args = parser.parse_args()

    state_dir = Path(args.state)
    try:
        report = run(state_dir)
    except ValueError as error:
        raise SystemExit(f"{state_dir.as_posix()}/{FLAT_FILENAME}: {error}") from error

    flat = f"{state_dir.as_posix()}/{FLAT_FILENAME}"
    print(f"{flat}: {report.rows_in} rows in, {report.rows_out} rows out")
    print(f"{flat}: removed, {report.days} day files written")
    print(f"load_published: {report.addresses} addresses, digest {report.digest}")
    for relpath in report.paths:
        print(f"  {relpath}")


if __name__ == "__main__":
    main()
