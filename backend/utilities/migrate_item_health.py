"""Rewrite every committed item-health day file into the current column list.

`ledger.require_matching_header` refuses to append to a file whose header is not
the contract's, and that guard is deliberate: a row written under one header and
read under another is a row whose cells have quietly moved. So a column added to
`ItemHealthRow` is a two-part change - the contract, and then every day file
already on disk (`docs/architecture/sources/item-health.md`).

This is the second part. It is idempotent, it reads every migrated row back
through `ItemHealthRow.from_csv_row` before it replaces anything, and it renames
a retired heading in place rather than moving a cell, so a file half-written by a
run that died mid-append is still a file this can finish.

    python backend/utilities/migrate_item_health.py            # report only
    python backend/utilities/migrate_item_health.py --write
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow

COLUMNS = ItemHealthRow.csv_columns()
DEFAULT_ROOT = config.REPO_ROOT / ledger.STATE_DIRNAME / "item-health"


def _widen(path: Path) -> tuple[bytes, int]:
    """The file as this contract would write it, and how many rows it holds."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        # Through the contract, never cell by cell: a rename this misread would
        # otherwise land as a plausible file rather than as a refusal.
        writer.writerow(ItemHealthRow.from_csv_row(row).csv_row())
    return buffer.getvalue().encode("utf-8"), len(rows)


def migrate(root: Path = DEFAULT_ROOT, *, write: bool = False) -> list[tuple[Path, int, bool]]:
    """One entry per day file: the path, its row count, and whether it changed."""
    report: list[tuple[Path, int, bool]] = []
    for path in sorted(root.rglob("*.csv")):
        widened, count = _widen(path)
        changed = widened != path.read_bytes()
        if changed and write:
            spool = path.with_suffix(".csv.tmp")
            spool.write_bytes(widened)
            spool.replace(path)
        report.append((path, count, changed))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    report = migrate(args.root, write=args.write)
    moved = [entry for entry in report if entry[2]]
    for path, count, changed in report:
        if changed:
            print(f"  {path.relative_to(config.REPO_ROOT).as_posix()}: {count} rows")
    verb = "rewrote" if args.write else "would rewrite"
    print(f"{len(COLUMNS)} columns; {verb} {len(moved)} of {len(report)} day files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
