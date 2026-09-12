"""Rewrite every `state/item-health/<YYYY-MM>.csv` onto the wider header.

`ledger.require_matching_header` compares the committed header to the contract's
column list exactly, so a contract that gains a column and this rewrite land in
one commit: without it the next scheduled run refuses its first append and the
day is lost (CLAUDE.md section 11). It has run twice - three columns on
2026-09-08, thirteen on 2026-09-12.

**It reads whatever header the shard carries rather than one written down here.**
The rule it enforces instead is the rule the contract already lives by: a column
is appended and never inserted, so the committed header must be a prefix of
`ItemHealthRow.csv_columns()`. A hand-listed previous header is a second
spelling of the shape that is wrong the day after the next widening, and it
makes each migration a new copy of this file.

Every rewritten row gains **empty** cells, never a value recomputed today: an
older run measured nothing there, and an empty cell is the only honest thing it
can say. A row written before the cost split recorded a total and no per-call
breakdown, and a breakdown invented from the total would be a reading nobody
took.

Committed rather than run by hand, so a fork or a stale branch can reproduce the
exact rewrite this repository ran (CLAUDE.md Guardrail #5). It is safe to re-run:
a shard that already carries the wide header is reported and skipped. That is
what makes it the tool for the merge conflict this change is guaranteed to hit -
`state/*.csv` is `merge=union`, so a merge concatenates two headers instead of
raising, and the repair is to take the upstream file whole
(`git checkout origin/main -- state/item-health`) and run this over it again
(`docs/reference/agent-notes.md`).

Usage: `python backend/utilities/migrate_item_health.py [--state state]`, from
the root of a checkout.
"""

from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from pathlib import Path

from idhazh.assemble import write_atomic
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.ledger import ITEM_HEALTH_DIRNAME

# A migrated row keeps the `version` cell it was written with, for the reason
# `migrate_feed_health` states: restamping would erase the only marker of which
# rows predate the widening and would claim today's writer produced them.


@dataclass(frozen=True, slots=True)
class Migration:
    """The rewritten shard and the numbers a reviewer will ask for."""

    text: str
    rows: int
    bytes_in: int
    bytes_out: int

    @property
    def added(self) -> int:
        return self.bytes_out - self.bytes_in


def _cells(text: str, columns: tuple[str, ...]) -> list[tuple[str, ...]]:
    """Every row as the cells the old header named, in file order."""
    reader = csv.DictReader(io.StringIO(text, newline=""))
    return [tuple(row[name] for name in columns) for row in reader]

def widen(text: str) -> Migration:
    """The wide shard, or a `ValueError` naming what stopped the rewrite."""
    columns = ItemHealthRow.csv_columns()
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = tuple(reader.fieldnames or ())
    if header == columns:
        raise ValueError("already the wide shape, so there is nothing to migrate")
    if header != columns[: len(header)]:
        raise ValueError(
            f"the header must be a prefix of {','.join(columns)} and is {','.join(header)}"
        )
    appended = columns[len(header) :]

    rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(row[name] is None for name in header):
            raise ValueError(f"line {number} does not carry {len(header)} cells")

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in columns})
    widened = out.getvalue()

    # The Oracle, in two halves. Every cell the old header named is still under
    # that name and in that order, so no reader's answer moved; and every
    # rewritten row loads through the contract with the appended cells absent
    # rather than carrying a reading nobody took.
    if _cells(text, header) != _cells(widened, header):
        raise ValueError("the rewrite moved a cell an existing reader opens, so nothing changed")
    for number, row in enumerate(csv.DictReader(io.StringIO(widened, newline="")), start=2):
        parsed = ItemHealthRow.from_csv_row(row)
        if any(getattr(parsed, name) is not None for name in appended):
            raise ValueError(f"line {number} came back with a reading nobody took")

    return Migration(
        text=widened,
        rows=len(rows),
        bytes_in=len(text.encode("utf-8")),
        bytes_out=len(widened.encode("utf-8")),
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

    directory = Path(args.state) / ITEM_HEALTH_DIRNAME
    shards = sorted(directory.glob("*.csv"))
    if not shards:
        raise SystemExit(f"{_relpath(directory)} holds no shard to migrate")

    for path in shards:
        relpath = _relpath(path)
        with path.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        try:
            report = widen(text)
        except ValueError as error:
            print(f"{relpath}: skipped - {error}")
            continue
        write_atomic(path, report.text)
        print(
            f"{relpath}: {report.rows} rows, {report.bytes_in} B before, "
            f"{report.bytes_out} B after, {report.added} B more"
        )


if __name__ == "__main__":
    main()
