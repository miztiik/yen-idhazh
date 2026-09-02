"""Publish the browser-safe telemetry projection.

The source ledger lives under `state/item-health/` and carries fields the browser
must never receive. This module writes a narrow monthly projection under
`frontend/public/telemetry/`, which is the only item-health data the console
fetches at runtime.

The projection's shape is `PublicTelemetryRow`, not a list of names here. This
module owns *when* a shard is written and *from what*; the contract owns which
cells may cross and what each one may hold (Rule #3).
"""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.public_telemetry import FORBIDDEN_COLUMNS, PublicTelemetryRow

PUBLIC_COLUMNS: Final[tuple[str, ...]] = PublicTelemetryRow.csv_columns()
DEFAULT_PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / "telemetry"

__all__ = [
    "DEFAULT_PUBLIC_ROOT",
    "FORBIDDEN_COLUMNS",
    "PUBLIC_COLUMNS",
    "migrate",
    "publish",
    "read_shard",
]


def _read(path: Path) -> list[PublicTelemetryRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        missing = set(ItemHealthRow.csv_columns()) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path.as_posix()} misses item-health columns: {sorted(missing)}")
        return [PublicTelemetryRow.from_csv_row(row) for row in reader]


def read_shard(path: Path) -> list[PublicTelemetryRow]:
    """Load a published shard back through the contract that wrote it.

    A published shard is the one artifact here nobody can re-derive once its
    source month has been folded away, so reading it back is what says it still
    loads rather than merely still parses.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [PublicTelemetryRow.from_csv_row(row) for row in reader]


def _write(path: Path, rows: list[PublicTelemetryRow]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLIC_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(row.csv_row() for row in rows)
    return len(rows)


def publish(
    *,
    state_root: Path = config.REPO_ROOT / ledger.STATE_DIRNAME,
    public_root: Path = DEFAULT_PUBLIC_ROOT,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write one public telemetry shard for each item-health month."""
    source_dir = state_root / ledger.ITEM_HEALTH_DIRNAME
    public_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if source_dir.exists():
        for source in sorted(source_dir.glob("*.csv")):
            target = public_root / source.name
            _write(target, _read(source))
            written.append(target)
    if ensure_month is not None and all(path.stem != ensure_month for path in written):
        target = public_root / f"{ensure_month}.csv"
        _write(target, [])
        written.append(target)
    return written


def migrate(public_root: Path = DEFAULT_PUBLIC_ROOT) -> list[tuple[Path, int, bool]]:
    """Rewrite every committed shard through the contract, and read it back.

    The publisher's own round trip rather than a utility of its own, because the
    pair that has to hold is the writer and the reader a run already uses. It
    never reads `state/`: a shard whose source month has been folded away still
    has to load.
    """
    results: list[tuple[Path, int, bool]] = []
    for path in sorted(public_root.glob("*.csv")):
        before = path.read_bytes()
        rows = read_shard(path)
        _write(path, rows)
        if read_shard(path) != rows:
            raise ValueError(f"{path.as_posix()} did not read back as it was written")
        results.append((path, len(rows), path.read_bytes() == before))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=config.REPO_ROOT / ledger.STATE_DIRNAME)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument("--ensure-month", help="Write an empty shard when this month has no rows.")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Rewrite the committed shards through the contract instead of publishing.",
    )
    args = parser.parse_args()
    if args.migrate:
        for path, rows, unchanged in migrate(args.public):
            state = "unchanged" if unchanged else "REWRITTEN"
            name = path.relative_to(config.REPO_ROOT).as_posix()
            print(f"{name} {rows} rows {path.stat().st_size} bytes {state}")
        return
    for path in publish(
        state_root=args.state, public_root=args.public, ensure_month=args.ensure_month
    ):
        size = path.stat().st_size
        gzipped = len(gzip.compress(path.read_bytes()))
        print(f"{path.relative_to(config.REPO_ROOT).as_posix()} {size} bytes {gzipped} gzip bytes")


if __name__ == "__main__":
    main()
