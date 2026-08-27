"""Read and append the committed ledgers under `state/`.

Five files, all append-only, all written by CI and read by a later run. They
exist because the pipeline has no memory of its own: every run starts on a
fresh machine with a fresh checkout, so anything one run needs to tell the next
has to be committed (Rule #1).

A ledger shards by month only when the read that consumes it carries a time
window. A window lets `_shards_in_window` skip whole files; without one, every
shard is opened anyway and splitting the file buys nothing. The rule is in
`docs/architecture/contracts/schemas.md`.

`state/seen/<YYYY-MM>.csv` answers "how old is this?" for an article whose feed
carried no date. Read through `collect.seen_window_days`, so it shards.

`state/published.csv` answers "have we already run this?" Read whole, because
published is forever and the question has no time bound - so it is one file.
Size it from the ceiling, not from today: a run plans at most
`run.safety_ceiling_per_run` items and the schedule fires five times a day, so
a day writes at most 1000 rows and a year at most about 365,000. At the
measured 214.9 B a row that is 78.4 MB on disk, and `load_published` peaks
around 261 MB reading it - in the one job that loads no model, on a 16 GB
runner. See `docs/reference/measurements.md`.

`state/feed-health/<YYYY-MM>.csv` answers "is this source still working?" One
row per feed per run, read through `HEALTH_WINDOW_DAYS`, so it shards.

`state/item-health/<YYYY-MM>.csv` answers "what did every planned item do?" One
row per planned item per run - the fastest-growing of the four. The console
reads it a month at a time through the published projection, so it shards.

`state/runtime-counters.csv` answers "what did the model server itself count?"
One row per work shard per run, read one run at a time by an audit that carries
no time window - so it is one file. It is also the slowest-growing: eight shards
times five runs a day is 40 rows, and a year is 14,600.

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
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow

STATE_DIRNAME: Final = "state"
SEEN_DIRNAME: Final = "seen"
HEALTH_DIRNAME: Final = "feed-health"
ITEM_HEALTH_DIRNAME: Final = "item-health"
PUBLISHED_FILENAME: Final = "published.csv"
RUNTIME_COUNTERS_FILENAME: Final = "runtime-counters.csv"

#: What makes two item-health rows the same record. One row per planned item per
#: run, which is what the ledger has always meant - written down here because two
#: stages now write it. The worker commits a row as soon as its item settles, and
#: assemble writes the whole day's census afterwards, so both see the same item
#: under the same run and the second one has nothing new to say.
ITEM_HEALTH_KEY: Final = ("date", "run_id", "item_id")

#: What makes two runtime-counter rows the same record. One work shard, one run.
#: The counters are cumulative for a server process, so a re-run of a failed job
#: would append a second row for the same shard and a run-level sum would count
#: that shard twice. The first row wins, which matches `ITEM_HEALTH_KEY`: a
#: re-run's items are skipped there too, so the two files stay describing the
#: same attempt.
RUNTIME_COUNTERS_KEY: Final = ("date", "run_id", "shard")

#: How far back a health read looks. Not a policy - just enough history to reach
#: into last month's shard, so a quarantine decided on the first of the month can
#: still see the failures that caused it.
HEALTH_WINDOW_DAYS: Final = 31


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


def item_health_relpath(date: str) -> str:
    """`state/item-health/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{ITEM_HEALTH_DIRNAME}/{date[:7]}.csv"


def item_health_path(state_dir: Path, date: str) -> Path:
    return state_dir / ITEM_HEALTH_DIRNAME / f"{date[:7]}.csv"


def published_path(state_dir: Path) -> Path:
    return state_dir / PUBLISHED_FILENAME


def runtime_counters_relpath() -> str:
    """`state/runtime-counters.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{RUNTIME_COUNTERS_FILENAME}"


def runtime_counters_path(state_dir: Path) -> Path:
    return state_dir / RUNTIME_COUNTERS_FILENAME


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


def read_header(path: Path) -> tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(next(csv.reader(handle), []))


def require_matching_header(path: Path, columns: tuple[str, ...]) -> None:
    header = read_header(path)
    if header and header != columns:
        raise ValueError(
            f"{path.name} has {len(header)} columns and the contract has "
            f"{len(columns)}. Migrate the ledger before appending to it."
        )


def _append(path: Path, columns: tuple[str, ...], payloads: list[dict[str, str]]) -> int:
    """Write every row it is handed. This path does not deduplicate, on purpose.

    `evals.writer.append` does, against its `OBSERVATION_KEY`, and the reason the
    two differ is what a row means. There a row is a measurement, so re-measuring
    an item nothing changed about has nothing new to say. Here a row is a fact
    about a run - this feed answered at this hour, this item finished - and a run
    that runs twice did happen twice. Collapsing those would turn a count of runs
    into a count of days.

    So each caller owns its own repeats, and each one is named here because the
    guarantee does not live in this file:

    - **seen** - `cli.stage_plan` builds its rows from `_first_sights`, which
      subtracts what `load_seen` already holds. A sight older than the window is
      outside that subtraction, and `load_seen` keeps the earliest of two, so the
      repeat costs bytes and never moves an age.
    - **published** - `cli._published_rows` joins the day against this run's plan,
      and `rank.plan_vertical` has already dropped every address `load_published`
      returned. Measured on this checkout 2026-08-27: 2,097 rows and 2,097
      distinct addresses. `load_published` keeps the earliest date, so a repeat
      costs bytes and never moves a publication date.
    - **feed-health** - one row per feed per run. A repeat needs a run to run
      twice under one `run_id`, which `cli._next_run_n` reads off the committed
      manifest to prevent. It is the one caller where a repeat is not free:
      `discover.resting` counts failures to decide a quarantine, so a duplicated
      failure counts twice.
    - **item-health** - two stages write it, so it cannot rely on a caller's own
      guarantee. `append_item_health` filters against `ITEM_HEALTH_KEY` instead.
    - **runtime-counters** - one writer, but the row is a cumulative total rather
      than an event, so a re-run of a failed shard would make a run-level sum
      count that shard twice. `append_runtime_counters` filters against
      `RUNTIME_COUNTERS_KEY`.
    """
    if not payloads:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    if exists:
        require_matching_header(path, columns)
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


def append_item_health(state_dir: Path, date: str, rows: Iterable[ItemHealthRow]) -> int:
    """Append this run's verdict on every planned item it has not already recorded.

    The only ledger here that filters, because it is the only one with two
    writers. The `work` job commits a row the moment its item settles, so the
    rows survive a run that dies before it publishes; `stage_assemble` then
    writes the whole day's census, which covers the same items again. A repeat is
    not free: `publish_telemetry` copies every row into the file the console
    reads, so one duplicated row is one item counted twice on the dashboard.

    `merge=union` on the shard cannot help - it keeps the lines from both sides,
    which is right for two runs appending different rows and exactly wrong for
    two writers appending the same one. The filter runs before the write, on the
    committed file each writer can see.

    Returns how many landed, so a caller can log the count.
    """
    already = recorded_item_health(item_health_path(state_dir, date))
    payloads = []
    for row in rows:
        payload = row.csv_row()
        key = tuple(payload[name] for name in ITEM_HEALTH_KEY)
        if key in already:
            continue
        already.add(key)
        payloads.append(payload)
    return _append(item_health_path(state_dir, date), ItemHealthRow.csv_columns(), payloads)


def recorded_item_health(path: Path) -> set[tuple[str, ...]]:
    """Every planned item this month's shard already has a verdict for.

    A missing file is a shard with no history, which is what the first run of a
    month has.
    """
    return {tuple(row[name] for name in ITEM_HEALTH_KEY) for row in _read_rows(path)}


def append_runtime_counters(state_dir: Path, rows: Iterable[RuntimeCountersRow]) -> int:
    """Append what each work shard's model server counted. Never windowed.

    Filters against `RUNTIME_COUNTERS_KEY` because the cells are cumulative
    totals rather than events: a second row for a shard is not a second fact, it
    is the same shard's tokens added to themselves by whatever pools the run.

    Returns how many landed, so a caller can log the count.
    """
    path = runtime_counters_path(state_dir)
    already = recorded_runtime_counters(path)
    payloads = []
    for row in rows:
        payload = row.csv_row()
        key = tuple(payload[name] for name in RUNTIME_COUNTERS_KEY)
        if key in already:
            continue
        already.add(key)
        payloads.append(payload)
    return _append(path, RuntimeCountersRow.csv_columns(), payloads)


def recorded_runtime_counters(path: Path) -> set[tuple[str, ...]]:
    """Every shard the file already carries a snapshot for."""
    return {tuple(row[name] for name in RUNTIME_COUNTERS_KEY) for row in _read_rows(path)}


def load_runtime_counters(state_dir: Path, *, run_id: str) -> list[RuntimeCountersRow]:
    """Every shard's snapshot for one run, in shard order.

    One run at a time, because the question this file answers is about one run.
    A caller that wants a trend reads several runs and says so.
    """
    rows = [
        RuntimeCountersRow.from_csv_row(row)
        for row in _read_rows(runtime_counters_path(state_dir))
        if row["run_id"] == run_id
    ]
    return sorted(rows, key=lambda row: row.shard)


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
