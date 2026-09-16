"""Publish the browser-safe projection of the score ledger.

`state/scores/<YYYY>/<MM>/<DD>.csv` is the ledger - one row per scored item per
attempt - and it carries the article's address twice and its fetched headline
once. This module writes the narrow monthly projection under
`frontend/public/scores/`, which is the only score data the console fetches.

**The two grains differ and this module is the bridge.** The ledger files by day,
because a run writes one day; the mirror files by month, because its grain
follows what a browser fetches and the console prices a window in files
(`docs/concepts/partitions.md`). A published month is folded from that month's
day files, which is at most 31 opens.

The shape is `PublicEvalRow` and the shape owns which cells may cross (Guardrail #3).
What this module owns is *from what* a month is built. Where it sits, when it is
written and how long it survives are `series`'s, and every producer
beside this one obeys the same three rules from the same place.
"""

from __future__ import annotations

import csv
from collections.abc import Collection
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import day_partition
from idhazh.contracts.public_eval import FORBIDDEN_COLUMNS, PublicEvalRow
from idhazh.evals import writer as eval_writer
from idhazh.telemetry.publish import series

PUBLIC_COLUMNS: Final[tuple[str, ...]] = PublicEvalRow.csv_columns()
DIRNAME: Final = series.SCORES_DIRNAME
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
    """The browser's copy of one score month."""
    return series.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/scores/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return series.relpath(DIRNAME, f"{month}{SUFFIX}")


def project(source: Path) -> list[PublicEvalRow]:
    """One state day file read through the published shape.

    `from_csv_row` takes only the columns the projection declares, so a cell on
    the ledger that this shape does not name cannot arrive by accident - the
    refusal is the shape's, not a filter written here.
    """
    if not source.is_file():
        return []
    with source.open("r", encoding="utf-8", newline="") as handle:
        return [PublicEvalRow.from_csv_row(row) for row in csv.DictReader(handle)]


def read_shard(path: Path) -> list[PublicEvalRow]:
    """Load a published shard back through the contract that wrote it.

    The header is checked by position, because the console reads it that way: a
    column inserted rather than appended shifts every panel one place left, and
    a header that no longer matches is a shard nothing can safely draw.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [PublicEvalRow.from_csv_row(row) for row in reader]


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published score shard for each ledger month that changed."""
    by_month = day_partition.days_by_month(state_root / eval_writer.LEDGER_DIRNAME)

    def encode(month: str) -> bytes:
        rows = [row for day in by_month.get(month, ()) for row in project(day)]
        return series.encode_csv(PUBLIC_COLUMNS, (row.csv_row() for row in rows))

    return series.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=sorted(by_month),
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
