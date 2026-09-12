"""Where every console payload sits, and the three rules all of them obey.

`backend/idhazh/contracts/console_payloads.py` says WHICH datasets the console
fetches and what may not cross with each. This module says WHERE each one is
written and HOW: one file per calendar month, written only when its bytes move,
and deleted once it is past its own configured age. Seven producer modules sit
on top of it - `publish_scores`, `publish_feed_health`, `publish_run_days`,
`publish_day_metrics`, `publish_machine`, `publish_span_rollup` and
`publish_console_band` - and none of them spells a path or a prune of its own.

**The root is derived, never spelled.** Every path here hangs off the digest
root the caller hands in, the way `INDEX_ROOT` and `SOURCE_HEALTH_PATH` hang off
`DIGEST_ROOT` in `frontend/src/lib/server/payload.ts`. A hard-coded
`frontend/public/...` would make a canary build read the real archive, and every
canary assertion non-deterministic.

**The three rules.**

1. *One month per run.* The run knows which month it appended to, and every
   other month is frozen. A producer takes that month and reads nothing else -
   unless a target file is missing, which is what makes a fresh clone, a deleted
   file and a first backfill all land (Guardrail #12).
2. *Only on a byte difference.* A re-derived month whose bytes match what is on
   disk is not rewritten. A timestamp says when a file was written, never
   whether its content moved.
3. *Nothing outlives its knob.* Each published directory has an
   `observability.public_*_keep_months` value, so the directory holds at most
   that many files however long the project runs. That is what makes listing it
   a bounded read rather than a growing one - the cover is enforced on the store
   rather than on the read (`docs/concepts/growing-reads.md`).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Final

from idhazh.month_partition import month_files, oldest_month_kept

#: The band, which is one file rather than a month series.
CONSOLE_DIRNAME: Final = "console"
BAND_FILENAME: Final = "band.json"

#: The six month series, each the directory name under `frontend/public/`.
SCORES_DIRNAME: Final = "scores"
FEED_HEALTH_DIRNAME: Final = "feed-health"
RUN_DAYS_DIRNAME: Final = "run-days"
DAY_METRICS_DIRNAME: Final = "day-metrics"
MACHINE_DIRNAME: Final = "machine"
SPAN_ROLLUP_DIRNAME: Final = "span-rollup"

#: Every root this module owns, with the suffix its month files take. The
#: telemetry projection is not here: it predates this module and
#: `publish_telemetry` owns its own path so that the fold which deletes a shard
#: and the publish which writes one cannot spell `<month>.csv` two ways.
MONTH_SERIES: Final[tuple[tuple[str, str], ...]] = (
    (SCORES_DIRNAME, ".csv"),
    (FEED_HEALTH_DIRNAME, ".csv"),
    (RUN_DAYS_DIRNAME, ".json"),
    (DAY_METRICS_DIRNAME, ".json"),
    (MACHINE_DIRNAME, ".csv"),
    (SPAN_ROLLUP_DIRNAME, ".csv"),
)

#: Every directory a fresh checkout must already hold, because
#: `.github/scripts/commit-and-push.sh` runs `git add "$@"` under
#: `set -euo pipefail` and a path that is not there aborts the whole step - and
#: takes every sibling ledger staged in the same call with it.
PUBLISHED_ROOTS: Final[tuple[str, ...]] = (
    CONSOLE_DIRNAME,
    SCORES_DIRNAME,
    FEED_HEALTH_DIRNAME,
    RUN_DAYS_DIRNAME,
    DAY_METRICS_DIRNAME,
    MACHINE_DIRNAME,
    SPAN_ROLLUP_DIRNAME,
)

__all__ = [
    "BAND_FILENAME",
    "CONSOLE_DIRNAME",
    "DAY_METRICS_DIRNAME",
    "FEED_HEALTH_DIRNAME",
    "MACHINE_DIRNAME",
    "MONTH_SERIES",
    "PUBLISHED_ROOTS",
    "RUN_DAYS_DIRNAME",
    "SCORES_DIRNAME",
    "SPAN_ROLLUP_DIRNAME",
    "console_root",
    "encode_csv",
    "month_path",
    "months_to_write",
    "oldest_month_kept",
    "prune_months",
    "publish_series",
    "published_months",
    "relpath",
    "series_root",
    "write_if_changed",
]


def console_root(digest_root: Path) -> Path:
    """`frontend/public/`, derived from the digest root the caller named.

    The one place the relationship is spelled. `payload.ts` derives
    `INDEX_ROOT` and `SOURCE_HEALTH_PATH` off `DIGEST_ROOT` the same way and for
    the same reason: a canary build hands in its own tree and must not be able
    to reach the published one.
    """
    return digest_root.parent


def series_root(digest_root: Path, dirname: str) -> Path:
    """The directory one month series lives in."""
    return console_root(digest_root) / dirname


def month_path(digest_root: Path, dirname: str, month: str, suffix: str = ".csv") -> Path:
    """The file one month of one series lives in."""
    return series_root(digest_root, dirname) / f"{month}{suffix}"


def relpath(dirname: str, name: str) -> str:
    """`frontend/public/<series>/<name>` - the POSIX form, for a log line."""
    return f"frontend/public/{dirname}/{name}"


def published_months(digest_root: Path, dirname: str, suffix: str) -> list[str]:
    """The months already on disk for one series, oldest first.

    One directory listing, and the directory is bounded by its own retention
    knob - so this costs at most `keep_months` entries however long the project
    runs. `month_partition` decides what counts as a month name, so a stem this
    does not recognise is left alone rather than deleted.
    """
    return [path.stem for path in month_files(series_root(digest_root, dirname), suffix)]


def months_to_write(
    available: Iterable[str],
    *,
    digest_root: Path,
    dirname: str,
    suffix: str,
    months: Collection[str] | None,
    oldest_kept: str,
) -> list[str]:
    """Which source months this run actually has to read.

    `months` names what the caller believes changed - the daily caller passes
    the one month it appended to. A month outside it is skipped without being
    read, **unless its published file is missing**, so a fresh clone, a deleted
    file and a first backfill all still land. `None` means read everything,
    which is what a backfill and a migration want.

    `oldest_kept` is what stops the missing-file rule fighting the prune. A
    month below the retention boundary has no file because the prune deleted it,
    so treating it as missing would read it, write it and delete it again -
    every run, for ever, on a month no console window can reach.

    This is `publish_telemetry.publish`'s rule, lifted so five more producers
    obey it rather than each restating it (Guardrail #12, decision 4 of the row).
    """
    wanted: list[str] = []
    for month in available:
        if month < oldest_kept:
            continue
        if months is None or month in months:
            wanted.append(month)
        elif not month_path(digest_root, dirname, month, suffix).exists():
            wanted.append(month)
    return wanted


def write_if_changed(path: Path, payload: bytes) -> bool:
    """Write the file only when its bytes would change; report whether they did.

    Content, never a timestamp. A re-derived month can carry identical bytes and
    a new mtime, and a fresh checkout can carry a new mtime and identical bytes,
    so a timestamp answers wrongly in both directions.
    """
    if path.exists() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return True


def prune_months(
    digest_root: Path,
    dirname: str,
    suffix: str,
    *,
    keep_months: int,
    today: date,
) -> tuple[str, ...]:
    """Delete every published month past its own configured age.

    Without this a producer is the growing cost Guardrail #12 refuses: a directory
    that gains a file every month and loses none. With it the directory holds at
    most `keep_months` files, which is what makes every later listing of it
    bounded.

    `keep_months` counts the month being written as one of them, so 14 on any
    day of September 2026 keeps `2025-08` through `2026-09`. The floor is
    fourteen and the config contract holds it there: `console.max_window_days`
    is 366, a 367-day inclusive read can touch fourteen month files, and a file
    deleted while a window preset can still reach it blanks that panel silently -
    a month with no file reads exactly like a month with no runs.
    """
    boundary = oldest_month_kept(today, keep_months)
    root = series_root(digest_root, dirname)
    deleted: list[str] = []
    for path in month_files(root, suffix):
        if path.stem >= boundary:
            continue
        path.unlink()
        deleted.append(path.stem)
    return tuple(deleted)


def encode_csv(columns: Sequence[str], rows: Iterable[Mapping[str, str]]) -> bytes:
    """The exact bytes a published shard holds, so a write can be skipped.

    `\\n` line endings whatever the platform is: a shard written on Windows and
    a shard written on the runner have to compare equal, or rule 2 above never
    skips a write and every month is rewritten on every run.
    """
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def publish_series(
    *,
    digest_root: Path,
    dirname: str,
    suffix: str,
    available: Iterable[str],
    encode: Callable[[str], bytes],
    keep_months: int,
    today: date,
    months: Collection[str] | None = None,
    ensure_month: str | None = None,
) -> list[Path]:
    """Run the three rules over one month series, and hand back what was written.

    Four producers reach this with a month-sharded source and two with a source
    of their own shape, so the differences stay in the caller: `available` is
    the months the source can offer and `encode` turns one of them into the
    bytes its published file holds. Everything below that - which months are
    read, whether a write happens, and what is deleted - is the same for all six
    and is here rather than restated six times.

    `ensure_month` writes an empty file for a month the source has no rows in.
    Not cosmetic: a directory named in `git add` has to exist in a fresh
    checkout, and a console asking for a month that never published needs an
    empty answer rather than a 404 it cannot tell from a broken deploy.
    """
    written: list[Path] = []
    oldest = oldest_month_kept(today, keep_months)
    wanted = months_to_write(
        available,
        digest_root=digest_root,
        dirname=dirname,
        suffix=suffix,
        months=months,
        oldest_kept=oldest,
    )
    for month in wanted:
        target = month_path(digest_root, dirname, month, suffix)
        if write_if_changed(target, encode(month)):
            written.append(target)
    if ensure_month is not None:
        target = month_path(digest_root, dirname, ensure_month, suffix)
        if not target.exists():
            write_if_changed(target, encode(ensure_month))
            written.append(target)
    prune_months(digest_root, dirname, suffix, keep_months=keep_months, today=today)
    return written
