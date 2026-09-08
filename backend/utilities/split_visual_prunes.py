"""Move every row of `state/visual-prunes.csv` into the day file its own date names.

One-shot, and committed rather than run by hand, so a fork or a stale branch can
reproduce the exact cutover this repository ran (CLAUDE.md Rule #5). It is safe
to leave here afterwards: a checkout with no flat file has nothing to split and
is told so.

The flat file is history. `ledger.append_visual_prunes` files a row under
`state/visual-prunes/YYYY/MM/DD.csv` now, and `ledger.load_visual_prunes` reads
the day tree alone - so this utility moves the rows, verifies, and only then
takes the old file away.

**Rows are copied, never rewritten.** The raw line goes across unchanged, cells,
order and bytes, so the `version` cell travels with the row it was written for
and a reader cannot tell which file a row came from.

**Run it when no scheduled digest is in flight.** `merge=union` is a content
driver and cannot resolve a delete against a modify, so a split racing a running
job conflicts and costs that job its push. Unlike the published cutover, this
ledger has no flat-file fallback to fall back on and never had one: the reader
moved to the day tree in the same commit as this utility. A flat file a merge
brings back is therefore unread, and running this again is what puts its rows
back in reach.

This reads the whole ledger, which is the growing cost Rule #12 is about. It is
allowed here for two reasons and they are both narrow: this is an operator
command a person runs once, not a step of any run; and the read it performs is
the read `load_visual_prunes` already performs on every call, because the
question that ledger answers is about the whole series and carries no window.

Usage: `python backend/utilities/split_visual_prunes.py [--state state]`,
from the root of a checkout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import ledger
from idhazh.assemble import write_atomic
from idhazh.contracts.visual_prune import VisualPruneRow

#: The file this cutover empties and removes. Spelled here rather than asked of
#: `idhazh.ledger` for the reason `split_published_ledger.FLAT_FILENAME` is
#: spelled there: it is history, and no public path helper in the ledger names
#: it any more.
FLAT_FILENAME: Final = "visual-prunes.csv"


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
    return ",".join(VisualPruneRow.csv_columns())


def _text(path: Path) -> str:
    """The file's bytes as text, with the line endings it really holds.

    Rows are copied verbatim, so nothing here may translate a newline on the
    way in - a reader that did would make a carriage return invisible to the
    check in `split` that refuses one.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _cells(line: str, number: int) -> tuple[str, ...]:
    columns = VisualPruneRow.csv_columns()
    rows = list(csv.reader([line]))
    if len(rows) != 1 or len(rows[0]) != len(columns):
        raise ValueError(f"line {number} does not carry {len(columns)} cells")
    return tuple(rows[0])


def _day_of(cells: tuple[str, ...], number: int) -> str:
    """The `date` cell, which is the day the pass was for and the file it belongs in.

    `VISUAL_PRUNE_KEY` opens with this cell, so filing by it is what keeps a
    repeated key inside one file - and a repeat that straddled two files is a
    repeat no settlement pass would ever meet.
    """
    on = cells[VisualPruneRow.csv_columns().index("date")]
    try:
        date_type.fromisoformat(on)
    except ValueError as error:
        raise ValueError(f"line {number} is dated {on!r}, which names no day file") from error
    if len(on) != 10:
        raise ValueError(f"line {number} is dated {on!r}, which names no day file")
    return on


def split(text: str) -> Split:
    """The flat ledger grouped by day, or a `ValueError` naming what stopped it.

    A row nobody can place stops the whole split rather than being skipped. A
    file the reader cannot place is how it starts missing rows, and the same
    holds one level up: a row that lands nowhere is a cleanup pass that stops
    having happened, and this ledger's whole job is to say a pass happened.
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


def digest(rows: Sequence[VisualPruneRow]) -> str:
    """sha256 over every cell of every row, in the order the reader returns them.

    The order is part of what is being preserved: this ledger is read as a
    series, and a series whose rows arrive shuffled answers "is the backlog
    shrinking" differently from one that does not.
    """
    canonical = "".join(",".join(row.csv_row().values()) + "\n" for row in rows)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _flat_rows(report: Split) -> list[VisualPruneRow]:
    """What the flat file's own rows parse to, oldest day first.

    `ledger.load_visual_prunes` reads the day tree alone now, so the flat file's
    own answer is reduced here. A row that does not parse is skipped, which is
    the reader's own rule restated: this ledger is a report, and an old report
    that cannot be read is not a reason to stop.
    """
    rows: list[VisualPruneRow] = []
    for on in sorted(report.lines):
        for number, line in enumerate(report.lines[on], start=2):
            raw = dict(zip(VisualPruneRow.csv_columns(), _cells(line, number), strict=True))
            try:
                rows.append(VisualPruneRow.from_csv_row(raw))
            except (KeyError, ValueError):
                continue
    return rows


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
    passes: int
    digest: str
    paths: list[str]


def run(state_dir: Path) -> Report:
    """Move the rows, verify, and only then remove the flat file.

    The verification is the guarantee itself rather than a proxy for it: what
    the two shapes reported together is taken before anything moves, and the
    flat file is removed only once `ledger.load_visual_prunes` reports the same
    series with the day tree alone answering.

    The flat side is reduced here because the reader no longer opens that file.
    The day side is the reader's own call, so what this checks is what a run
    will really see.
    """
    flat = state_dir / FLAT_FILENAME
    if not flat.is_file():
        raise ValueError(f"{FLAT_FILENAME} does not exist, so there is nothing to split")

    text = _text(flat)
    report = split(text)
    if report.rows_out != report.rows_in:
        raise ValueError(f"{report.rows_in} rows in and {report.rows_out} out, so a row was lost")

    before = ledger.load_visual_prunes(state_dir) + _flat_rows(report)

    for on in sorted(report.lines):
        _write_day(ledger.visual_prunes_path(state_dir, on), report.lines[on])

    both = ledger.load_visual_prunes(state_dir)
    if both != before:
        raise ValueError(
            f"the day files report {len(both)} passes where both shapes reported "
            f"{len(before)}, so the flat file was left alone"
        )

    flat.unlink()
    after = ledger.load_visual_prunes(state_dir)
    if after != before:
        write_atomic(flat, text)
        raise ValueError(
            "the day tree alone does not report what the flat file reported, so the "
            "flat file was put back"
        )

    return Report(
        rows_in=report.rows_in,
        rows_out=report.rows_out,
        days=report.days,
        passes=len(after),
        digest=digest(after),
        paths=[ledger.visual_prunes_relpath(on) for on in sorted(report.lines)],
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
    print(f"load_visual_prunes: {report.passes} passes, digest {report.digest}")
    for relpath in report.paths:
        print(f"  {relpath}")


if __name__ == "__main__":
    main()
