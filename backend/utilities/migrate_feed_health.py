"""Rewrite every `state/feed-health/<YYYY-MM>.csv` onto the wider header.

`FeedHealthRow` gained five columns on 2026-09-02, and
`ledger.require_matching_header` compares the committed header to the contract's
column list exactly. So the contract change and this rewrite land in one commit:
without it the next scheduled run refuses its first append and the day is lost
(CLAUDE.md section 11).

Every rewritten row gains five **empty** cells. Not a zero, and not a value
recomputed from today's `config/sources.json`: the configured URL may have moved
since a row was written, and a guessed endpoint identity would retire the wrong
address later. An empty cell says the older run never looked, which is the only
honest thing it can say.

One-shot, and committed rather than run by hand, so a fork or a stale branch can
reproduce the exact rewrite this repository ran (CLAUDE.md Rule #5). It is safe
to leave here and safe to re-run: a shard that already carries the wide header is
reported and skipped rather than rewritten a second time. That is what makes it
the tool for the merge conflict this change is guaranteed to hit - the upstream
file is taken whole and this is run over it again.

Usage: `python backend/utilities/migrate_feed_health.py [--state state]`, from
the root of a checkout.
"""

from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh.assemble import write_atomic
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.ledger import HEALTH_DIRNAME

#: The shape this migration reads. History rather than a knob, so it is spelled
#: here: the contract no longer describes the files being migrated.
NARROW_COLUMNS: Final[tuple[str, ...]] = (
    "version",
    "run_id",
    "date",
    "feed_id",
    "checked_at",
    "outcome",
    "status",
    "items",
    "detail",
)

# A migrated row keeps the `version` cell it was written with. The base contract
# accepts an older stamp on purpose, so a later read-side migration has
# something to branch on; restamping every row would erase the only marker of
# which rows predate the widening and would claim today's writer produced them.


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
    columns = FeedHealthRow.csv_columns()
    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = tuple(reader.fieldnames or ())
    if header == columns:
        raise ValueError("already the wide shape, so there is nothing to migrate")
    if header != NARROW_COLUMNS:
        raise ValueError(
            f"expected the header {','.join(NARROW_COLUMNS)} and found {','.join(header)}"
        )

    rows = list(reader)
    for number, row in enumerate(rows, start=2):
        if None in row or any(row[name] is None for name in NARROW_COLUMNS):
            raise ValueError(f"line {number} does not carry {len(NARROW_COLUMNS)} cells")

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in columns})
    widened = out.getvalue()

    # The Oracle, in two halves. Every cell the old header named is still under
    # that name and in that order, so no reader's answer moved; and every
    # rewritten row loads through the contract, with the five new cells absent
    # rather than carrying a value nobody measured.
    if _cells(text, NARROW_COLUMNS) != _cells(widened, NARROW_COLUMNS):
        raise ValueError("the rewrite moved a cell an existing reader opens, so nothing changed")
    for number, row in enumerate(csv.DictReader(io.StringIO(widened, newline="")), start=2):
        parsed = FeedHealthRow.from_csv_row(row)
        if parsed.endpoint_key is not None or parsed.robots_outcome is not None:
            raise ValueError(f"line {number} came back with an identity nobody recorded")

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

    directory = Path(args.state) / HEALTH_DIRNAME
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
