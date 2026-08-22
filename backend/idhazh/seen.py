"""Read and append the two committed sight ledgers.

Both files are append-only and both are read at plan time. The seen store is
sharded by month, so a plan run reads a few small files rather than one file
that grows for the life of the project; the published store is one file,
because one row per published item is a few thousand rows a year.

Neither reader fails on a missing file. A fresh clone has no history, and a run
with no history is a run where nothing was seen before and nothing was
published before - which is exactly what an empty mapping says.

Callers pass the state directory and never the file name. The layout is one
fact, and it lives here.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

from idhazh.contracts.seen import PublishedRow, SeenRow

STATE_DIRNAME: Final = "state"
SEEN_DIRNAME: Final = "seen"
PUBLISHED_FILENAME: Final = "published.csv"


def seen_relpath(date: str) -> str:
    """`state/seen/<YYYY-MM>.csv` - the POSIX form, for a log line or a manifest."""
    return f"{STATE_DIRNAME}/{SEEN_DIRNAME}/{date[:7]}.csv"


def seen_path(state_dir: Path, date: str) -> Path:
    """The month shard a run on this date appends to."""
    return state_dir / SEEN_DIRNAME / f"{date[:7]}.csv"


def published_path(state_dir: Path) -> Path:
    return state_dir / PUBLISHED_FILENAME


def _shards_in_window(today: str, within_days: int) -> list[str]:
    """The month stems a window of days can touch, newest first.

    Walking days rather than subtracting months keeps the arithmetic honest
    across a year boundary and needs no calendar table.
    """
    end = date_type.fromisoformat(today)
    stems: list[str] = []
    for offset in range(within_days + 1):
        stem = (end - timedelta(days=offset)).isoformat()[:7]
        if stem not in stems:
            stems.append(stem)
    return stems


def _append(path: Path, columns: tuple[str, ...], payloads: list[dict[str, str]]) -> int:
    if not payloads:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        if not exists:
            writer.writeheader()
        for payload in payloads:
            writer.writerow({name: payload[name] for name in columns})
    return len(payloads)


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def append_seen(state_dir: Path, date: str, rows: Iterable[SeenRow]) -> int:
    """Append first sights. Returns how many landed, so a caller can log the count."""
    payloads = [row.model_dump(mode="json") for row in rows]
    return _append(seen_path(state_dir, date), SeenRow.csv_columns(), payloads)


def append_published(state_dir: Path, rows: Iterable[PublishedRow]) -> int:
    """Append what a committed digest actually carried."""
    payloads = [row.model_dump(mode="json") for row in rows]
    return _append(published_path(state_dir), PublishedRow.csv_columns(), payloads)


def load_seen(state_dir: Path, *, today: str, within_days: int) -> dict[str, str]:
    """Address -> the timestamp we first saw it, over the window only.

    Older shards stay committed and stay readable; they are simply not
    consulted, because an address first seen four months ago is not evidence
    about today. The earliest sight wins when two shards disagree, which is
    what "first" means.
    """
    first_seen: dict[str, str] = {}
    for stem in _shards_in_window(today, within_days):
        for row in _read_rows(state_dir / SEEN_DIRNAME / f"{stem}.csv"):
            url_key, at = row["url_key"], row["first_seen_at"]
            if url_key not in first_seen or at < first_seen[url_key]:
                first_seen[url_key] = at
    return first_seen


def load_published(state_dir: Path) -> dict[str, str]:
    """Address -> the digest date it ran on. Never windowed: published is forever."""
    published: dict[str, str] = {}
    for row in _read_rows(published_path(state_dir)):
        url_key, on = row["url_key"], row["published_on"]
        if url_key not in published or on < published[url_key]:
            published[url_key] = on
    return published
