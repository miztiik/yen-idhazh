"""Publish the browser-safe projection of the score ledger.

`state/scores/<YYYY-MM>.csv` is the ledger - one row per scored item per attempt
- and it carries the article's address twice and its fetched headline once. This
module writes the narrow monthly projection under `frontend/public/scores/`,
which is the only score data the console fetches.

The shape is `PublicEvalRow` and the shape owns which cells may cross (Guardrail #3).
What this module owns is *from what* a month is built. Where it sits, when it is
written and how long it survives are `publish_console`'s, and every producer
beside this one obeys the same three rules from the same place.
"""

from __future__ import annotations

import csv
from collections.abc import Collection
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import publish_console
from idhazh.contracts.public_eval import FORBIDDEN_COLUMNS, PublicEvalRow
from idhazh.evals import writer as eval_writer

PUBLIC_COLUMNS: Final[tuple[str, ...]] = PublicEvalRow.csv_columns()
DIRNAME: Final = publish_console.SCORES_DIRNAME
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
    return publish_console.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/scores/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return publish_console.relpath(DIRNAME, f"{month}{SUFFIX}")


def project(source: Path) -> list[PublicEvalRow]:
    """One state shard read through the published shape.

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

    def encode(month: str) -> bytes:
        rows = project(state_root / eval_writer.LEDGER_DIRNAME / f"{month}{SUFFIX}")
        return publish_console.encode_csv(PUBLIC_COLUMNS, (row.csv_row() for row in rows))

    return publish_console.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=[path.stem for path in eval_writer.ledger_shards(state_root)],
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
