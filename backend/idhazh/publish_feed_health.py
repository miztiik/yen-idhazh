"""Publish the browser-safe projection of the feed-health ledger.

`state/feed-health/<YYYY-MM>.csv` is the ledger - one row per feed per run - and
it carries the configured feed URL hashed. This module writes the narrow monthly
projection under `frontend/public/feed-health/`, which is the only feed data the
console fetches.

The shape is `PublicFeedRow`. It keeps `detail`, which is our own one-line reason
and never the response body, because a failing feed a reader can see but not
read is a bar with no label; it refuses `endpoint_key`, because an address
hashed is still an address (Rule #11).
"""

from __future__ import annotations

import csv
from collections.abc import Collection
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import ledger, month_partition, publish_console
from idhazh.contracts.public_feed_health import FORBIDDEN_COLUMNS, PublicFeedRow

PUBLIC_COLUMNS: Final[tuple[str, ...]] = PublicFeedRow.csv_columns()
DIRNAME: Final = publish_console.FEED_HEALTH_DIRNAME
SUFFIX: Final = ".csv"

__all__ = [
    "DIRNAME",
    "FORBIDDEN_COLUMNS",
    "PUBLIC_COLUMNS",
    "SUFFIX",
    "project",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(digest_root: Path, month: str) -> Path:
    """The browser's copy of one feed-health month."""
    return publish_console.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/feed-health/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return publish_console.relpath(DIRNAME, f"{month}{SUFFIX}")


def project(source: Path) -> list[PublicFeedRow]:
    """One state shard read through the published shape."""
    if not source.is_file():
        return []
    with source.open("r", encoding="utf-8", newline="") as handle:
        return [PublicFeedRow.from_csv_row(row) for row in csv.DictReader(handle)]


def read_shard(path: Path) -> list[PublicFeedRow]:
    """Load a published shard back through the contract that wrote it."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [PublicFeedRow.from_csv_row(row) for row in reader]


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published feed-health shard for each ledger month that changed."""
    source_dir = state_root / ledger.HEALTH_DIRNAME

    def encode(month: str) -> bytes:
        rows = project(source_dir / f"{month}{SUFFIX}")
        return publish_console.encode_csv(PUBLIC_COLUMNS, (row.csv_row() for row in rows))

    return publish_console.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=[path.stem for path in month_partition.month_files(source_dir, SUFFIX)],
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
