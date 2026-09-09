"""Publish the span rollup a month at a time.

`state/span-rollup/<YYYY-MM>.csv` holds one row per shard per span - five span
names we chose, a count and two durations. Every cell on it is a measurement of
our own work, so the row is published whole rather than projected: a projection
field-for-field identical to its source is two schemas for one row.

The shape is `SpanRollupRow`, and `FORBIDDEN_COLUMNS` on it is empty for that
structural reason rather than by omission - no cell here can hold anything
fetched.
"""

from __future__ import annotations

import csv
from collections.abc import Collection
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import ledger, month_partition, publish_console
from idhazh.contracts.span_rollup import SpanRollupRow

PUBLIC_COLUMNS: Final[tuple[str, ...]] = SpanRollupRow.csv_columns()
DIRNAME: Final = publish_console.SPAN_ROLLUP_DIRNAME
SUFFIX: Final = ".csv"

__all__ = [
    "DIRNAME",
    "PUBLIC_COLUMNS",
    "SUFFIX",
    "project",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(digest_root: Path, month: str) -> Path:
    """The browser's copy of one span-rollup month."""
    return publish_console.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/span-rollup/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return publish_console.relpath(DIRNAME, f"{month}{SUFFIX}")


def project(source: Path) -> list[SpanRollupRow]:
    """One state shard read through its own contract.

    Read through the model rather than copied byte-for-byte: a copy would
    publish whatever the file holds, and this way a row that no longer validates
    stops here instead of reaching a browser that cannot upgrade.
    """
    if not source.is_file():
        return []
    with source.open("r", encoding="utf-8", newline="") as handle:
        return [SpanRollupRow.from_csv_row(row) for row in csv.DictReader(handle)]


def read_shard(path: Path) -> list[SpanRollupRow]:
    """Load a published shard back through the contract that wrote it."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [SpanRollupRow.from_csv_row(row) for row in reader]


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published span-rollup shard for each ledger month that changed."""
    source_dir = state_root / ledger.SPAN_ROLLUP_DIRNAME

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
