"""Publish the span rollup a month at a time.

`state/span-rollup/` holds one row per shard per span - five span names we
chose, a count and two durations - filed under the day each row names, one file
per writer. Every cell on it is a measurement of our own work, so the row is
published whole rather than projected: a projection field-for-field identical to
its source is two schemas for one row.

The browser's copy stays a month, because its grain follows what a browser
fetches rather than what a writer writes (`docs/concepts/partitions.md`).

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

from idhazh import day_shards, ledger
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.span_rollup import SpanRollupRow
from idhazh.telemetry.publish import series

PUBLIC_COLUMNS: Final[tuple[str, ...]] = SpanRollupRow.csv_columns()
DIRNAME: Final = series.SPAN_ROLLUP_DIRNAME
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
    return series.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/span-rollup/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return series.relpath(DIRNAME, f"{month}{SUFFIX}")


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
    """Write a published span-rollup shard for each ledger month that changed.

    The ledger files by day and one writer, so a month is the days under it and
    each day is settled before it is published: two writers of one day each hold
    their own file, and a reader that took whichever the walk named last would
    publish one shard's spans as the day's.
    """
    source_dir = state_root / ledger.SPAN_ROLLUP_DIRNAME
    days_of: dict[str, list[str]] = {}
    for shard in day_shards.shard_files(source_dir, days=UNBOUNDED_WINDOW):
        recorded = day_shards.date_of(shard)
        held = days_of.setdefault(recorded[:7], [])
        if recorded not in held:
            held.append(recorded)

    def encode(month: str) -> bytes:
        rows = [
            SpanRollupRow.from_csv_row(cells)
            for recorded in sorted(days_of.get(month, ()))
            for cells in day_shards.settled_day(
                source_dir, recorded, ledger.SPAN_ROLLUP_KEY, SpanRollupRow
            )
        ]
        return series.encode_csv(PUBLIC_COLUMNS, (row.csv_row() for row in rows))

    return series.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=sorted(days_of),
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
