"""Read and append the committed ledgers under `state/`.

Three files, all append-only, all written by CI and read by a later run. They
exist because the pipeline has no memory of its own: every run starts on a
fresh machine with a fresh checkout, so anything one run needs to tell the next
has to be committed (Holy Law #1).

`state/seen/<YYYY-MM>.csv` answers "how old is this?" for an article whose feed
carried no date. Sharded by month, so a plan run reads a few small files rather
than one file that grows for the life of the project.

`state/published.csv` answers "have we already run this?" One file, because one
row per published item is a few thousand rows a year.

`state/feed-health/<YYYY-MM>.csv` answers "is this source still working?" One
row per feed per run, sharded like the seen store for the same reason: it is
the fastest-growing of the three.

No reader fails on a missing file. A fresh clone has no history, and a run with
no history is a run where nothing was seen, nothing was published and no feed
has a record yet - which is exactly what an empty result says.

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

from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.seen import PublishedRow, SeenRow

STATE_DIRNAME: Final = "state"
SEEN_DIRNAME: Final = "seen"
HEALTH_DIRNAME: Final = "feed-health"
PUBLISHED_FILENAME: Final = "published.csv"


def seen_relpath(date: str) -> str:
    """`state/seen/<YYYY-MM>.csv` - the POSIX form, for a log line or a manifest."""
    return f"{STATE_DIRNAME}/{SEEN_DIRNAME}/{date[:7]}.csv"


def seen_path(state_dir: Path, date: str) -> Path:
    """The month shard a run on this date appends to."""
    return state_dir / SEEN_DIRNAME / f"{date[:7]}.csv"


def health_relpath(date: str) -> str:
    """`state/feed-health/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{HEALTH_DIRNAME}/{date[:7]}.csv"


def health_path(state_dir: Path, date: str) -> Path:
    return state_dir / HEALTH_DIRNAME / f"{date[:7]}.csv"


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


def append_health(state_dir: Path, date: str, rows: Iterable[FeedHealthRow]) -> int:
    """Append this run's verdict on every feed it tried."""
    payloads = [row.csv_row() for row in rows]
    return _append(health_path(state_dir, date), FeedHealthRow.csv_columns(), payloads)


def load_health(state_dir: Path, *, today: str, within_days: int) -> list[FeedHealthRow]:
    """Every health row in the window, oldest run first.

    Sorted by run rather than by file order so a caller can talk about "the last
    N runs" without knowing that the file is append-ordered - which it is today,
    and which a rebased CI push could stop being tomorrow.

    A row that no longer parses is skipped rather than fatal. This ledger is
    diagnostic: losing a stale row costs a quarantine decision some evidence,
    and refusing to start costs the reader the whole day.
    """
    rows: list[FeedHealthRow] = []
    for stem in _shards_in_window(today, within_days):
        for raw in _read_rows(state_dir / HEALTH_DIRNAME / f"{stem}.csv"):
            try:
                rows.append(FeedHealthRow.from_csv_row(raw))
            except (KeyError, ValueError):
                continue
    rows.sort(key=lambda row: (row.date, _run_n(row.run_id)))
    return rows


def _run_n(run_id: str) -> int:
    """The run number out of `<date>-<n>`, so run 10 sorts after run 9."""
    return int(run_id.rsplit("-", 1)[1])
