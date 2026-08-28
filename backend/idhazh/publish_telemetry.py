"""Publish the browser-safe telemetry projection.

The source ledger lives under `state/item-health/` and carries fields the browser
must never receive. This module writes a narrow monthly projection under
`frontend/public/telemetry/`, which is the only item-health data the console
fetches at runtime.
"""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow

PUBLIC_COLUMNS: Final[tuple[str, ...]] = (
    "date",
    "run_id",
    "item_id",
    "vertical",
    "source_id",
    "stage",
    "outcome",
    "code",
    "source_words",
    "summary_words",
    "source_words_before_cap",
)

FORBIDDEN_COLUMNS: Final[frozenset[str]] = frozenset({"canonical_url", "url_key", "detail"})
DEFAULT_PUBLIC_ROOT: Final = config.REPO_ROOT / "frontend" / "public" / "telemetry"


def _project(row: dict[str, str]) -> dict[str, str]:
    """Keep only the browser-safe cells, in one fixed order."""
    return {name: row.get(name, "") for name in PUBLIC_COLUMNS}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        missing = set(ItemHealthRow.csv_columns()) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path.as_posix()} misses item-health columns: {sorted(missing)}")
        if FORBIDDEN_COLUMNS & set(PUBLIC_COLUMNS):
            raise AssertionError("a forbidden item-health field is in the public projection")
        return [_project(row) for row in reader]


def _write(path: Path, rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PUBLIC_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=config.REPO_ROOT / ledger.STATE_DIRNAME)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC_ROOT)
    parser.add_argument("--ensure-month", help="Write an empty shard when this month has no rows.")
    args = parser.parse_args()
    for path in publish(
        state_root=args.state, public_root=args.public, ensure_month=args.ensure_month
    ):
        size = path.stat().st_size
        gzipped = len(gzip.compress(path.read_bytes()))
        print(f"{path.relative_to(config.REPO_ROOT).as_posix()} {size} bytes {gzipped} gzip bytes")


if __name__ == "__main__":
    main()
