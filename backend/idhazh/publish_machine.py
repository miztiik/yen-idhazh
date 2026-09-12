"""Publish the runtime counters a month at a time.

`state/runtime-counters.csv` is one appended file for the life of the project,
so this is the one published series whose month boundary is drawn here rather
than inherited from a state shard. Every cell on the row is our own server's
counter, our own job clock or the runner's CPU name, so the row is published
whole - `RuntimeCountersRow.FORBIDDEN_COLUMNS` would be empty and the shape says
why in its own module. **Every COLUMN, not every row**: `PUBLISHED_JOB` names
the one job this series is about, and the reason is beside it.

**The source read is unbounded, on purpose, and this is where it says so**
(Guardrail #12, and the third answer in `docs/concepts/growing-reads.md`). The
counters file has no shards and no prune, so a run that wants September's rows
has to walk every row ever appended to find them - no cover in days, no cover in
months and no identity set answers "which rows are September's" more cheaply
than reading them. It costs **one file handle** however many months it holds,
which is the same handle `ledger.load_runtime_counters` already opens to answer
about one run, and this producer opens no second one. What it WRITES is bounded:
a row older than `observability.public_machine_keep_months` is dropped on the
way through rather than written into a file the prune would delete on the next
pass.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Collection
from datetime import date
from pathlib import Path
from typing import Final

from idhazh import ledger, publish_console
from idhazh.contracts.runtime_counters import WORK_JOB, RuntimeCountersRow

PUBLIC_COLUMNS: Final[tuple[str, ...]] = RuntimeCountersRow.csv_columns()
DIRNAME: Final = publish_console.MACHINE_DIRNAME
SUFFIX: Final = ".csv"
#: The one job this series is about. The `visuals` job writes counters rows too
#: from 2026-09-12, and they belong in `state/` rather than here: the Machine
#: page pools a run's tokens over a run's seconds, and the two jobs serve
#: different weights, so one pooled rate over both describes no model. The page
#: also refuses a run whose rows disagree about the shard count, and the visuals
#: job runs one server where a work run runs four.
PUBLISHED_JOB: Final = WORK_JOB

__all__ = [
    "DIRNAME",
    "PUBLIC_COLUMNS",
    "PUBLISHED_JOB",
    "SUFFIX",
    "months_on_file",
    "publish",
    "read_shard",
    "shard_path",
    "shard_relpath",
]


def shard_path(digest_root: Path, month: str) -> Path:
    """The browser's copy of one month of counters."""
    return publish_console.month_path(digest_root, DIRNAME, month, SUFFIX)


def shard_relpath(month: str) -> str:
    """`frontend/public/machine/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return publish_console.relpath(DIRNAME, f"{month}{SUFFIX}")


def months_on_file(
    state_root: Path, *, oldest_month: str
) -> dict[str, list[RuntimeCountersRow]]:
    """Every `work` counters row at or above `oldest_month`, bucketed by its month.

    One pass and one handle over `state/runtime-counters.csv` - see the module
    docstring for why that read is unbounded and why no cover would help. Rows
    below the boundary are dropped here rather than written and then pruned,
    because a file written and deleted in the same run is a diff a reviewer has
    to explain. A row from another job is dropped for the reason `PUBLISHED_JOB`
    gives, and that drop is by name rather than by absence - a row whose `job`
    cell is empty never reaches here, because the contract refuses it.

    A row that no longer validates raises rather than being skipped. The
    counters file is what every Hardware panel stands on, and a run that
    quietly published a shorter month would report the machine as having done
    less work than it did.
    """
    source = ledger.runtime_counters_path(state_root)
    found: dict[str, list[RuntimeCountersRow]] = defaultdict(list)
    if not source.is_file():
        return {}
    with source.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            month = row.get("date", "")[:7]
            if month < oldest_month:
                continue
            counted = RuntimeCountersRow.from_csv_row(row)
            if counted.job != PUBLISHED_JOB:
                continue
            found[month].append(counted)
    return dict(found)


def read_shard(path: Path) -> list[RuntimeCountersRow]:
    """Load a published shard back through the contract that wrote it."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != PUBLIC_COLUMNS:
            raise ValueError(
                f"{path.as_posix()} header is {list(header)}, the contract writes "
                f"{list(PUBLIC_COLUMNS)}"
            )
        return [RuntimeCountersRow.from_csv_row(row) for row in reader]


def publish(
    *,
    state_root: Path,
    digest_root: Path,
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Write a published counters shard for each month that changed."""
    oldest = publish_console.oldest_month_kept(today, keep_months)
    buckets = months_on_file(state_root, oldest_month=oldest)

    def encode(month: str) -> bytes:
        rows = buckets.get(month, [])
        return publish_console.encode_csv(PUBLIC_COLUMNS, (row.csv_row() for row in rows))

    return publish_console.publish_series(
        digest_root=digest_root,
        dirname=DIRNAME,
        suffix=SUFFIX,
        available=sorted(buckets),
        encode=encode,
        keep_months=keep_months,
        today=today,
        months=months,
        ensure_month=ensure_month,
    )
