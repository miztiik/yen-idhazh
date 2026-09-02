"""Read and append the committed ledgers under `state/`.

Every file here is written by CI and read by a later run. All but one are
append-only; the exception is named below. They exist because the pipeline has
no memory of its own: every run starts on a fresh machine with a fresh
checkout, so anything one run needs to tell the next has to be committed
(Rule #1).

A ledger shards by month only when the read that consumes it carries a time
window. A window lets `shards_in_window` skip whole files; without one, every
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

`state/telemetry-aggregate/<YYYY-MM>.csv` is what is left of an item-health
month once `observability.keep_months` has passed: one row per (date, stage),
folded by `retention.fold_month`. It shards by month because the shard it
replaces did, so the two file by the same stem and a reader looking for a month
looks in one of two places rather than in a directory and a lookup table. It is
the one file here that is rewritten rather than appended, because every row in
it is derived from the shard it summarises.

`state/feed-retirements.csv` answers "is this address gone for good?" One row
per retired feed endpoint, read whole because a retirement has no time bound -
so it is one file. It is also the smallest: a row is written only when a server
has reported one address permanently gone on five distinct runs.

No reader fails on a missing file. A fresh clone has no history, and a run with
no history is a run where nothing was seen, nothing was published and no feed
has a record yet - which is exactly what an empty result says.

Callers pass the state directory and never the file name. The layout is one
fact, and it lives here.
"""

from __future__ import annotations

import csv
from collections.abc import Collection, Iterable
from datetime import date as date_type
from datetime import timedelta
from pathlib import Path
from typing import Final

from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.item_health import ItemHealthRow, ItemOutcome
from idhazh.contracts.runtime_counters import RuntimeCountersRow
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.telemetry_aggregate import TelemetryAggregateRow

STATE_DIRNAME: Final = "state"
SEEN_DIRNAME: Final = "seen"
HEALTH_DIRNAME: Final = "feed-health"
ITEM_HEALTH_DIRNAME: Final = "item-health"
TELEMETRY_AGGREGATE_DIRNAME: Final = "telemetry-aggregate"
PUBLISHED_FILENAME: Final = "published.csv"
RUNTIME_COUNTERS_FILENAME: Final = "runtime-counters.csv"
FEED_RETIREMENTS_FILENAME: Final = "feed-retirements.csv"

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

#: What makes two retirement rows the same record. The address and nothing else:
#: a retirement is permanent for one endpoint key, so a second row for it says
#: nothing the first did not. `feed_id` is deliberately absent - renaming a feed
#: in curated config must not make its dead address eligible again, and editing
#: that feed's URL already produces a different key.
FEED_RETIREMENT_KEY: Final = ("endpoint_key",)

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


def telemetry_aggregate_relpath(month: str) -> str:
    """`state/telemetry-aggregate/<YYYY-MM>.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{TELEMETRY_AGGREGATE_DIRNAME}/{month}.csv"


def telemetry_aggregate_path(state_dir: Path, month: str) -> Path:
    """Where the folded summary of one item-health month lives.

    Its own directory rather than a second filename inside `item-health/`,
    because `publish_telemetry.publish` globs that directory for month shards
    and reads every file it finds as a full-grain row - the aggregate is a
    different shape and would fail that read.
    """
    return state_dir / TELEMETRY_AGGREGATE_DIRNAME / f"{month}.csv"


def published_path(state_dir: Path) -> Path:
    return state_dir / PUBLISHED_FILENAME


def runtime_counters_relpath() -> str:
    """`state/runtime-counters.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{RUNTIME_COUNTERS_FILENAME}"


def runtime_counters_path(state_dir: Path) -> Path:
    return state_dir / RUNTIME_COUNTERS_FILENAME


def feed_retirements_relpath() -> str:
    """`state/feed-retirements.csv` - the POSIX form, for a log line."""
    return f"{STATE_DIRNAME}/{FEED_RETIREMENTS_FILENAME}"


def feed_retirements_path(state_dir: Path) -> Path:
    return state_dir / FEED_RETIREMENTS_FILENAME


def shards_in_window(today: str, within_days: int) -> list[str]:
    """The month stems a window of days can touch, newest first.

    Public because the pruner keeps exactly what this returns. Deriving the
    keep-set from the reader's own helper is what makes it impossible to delete
    a shard a later read would have opened.

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
      twice under one `run_id`. Two runs cannot compute one any more - a run id
      now carries the identity of the execution that made it (`cli.stage_plan`)
      - but a second attempt of the same execution still can, and this is the
      one caller where the repeat is not free: `discover.resting` counts
      failures to decide a quarantine, so a duplicated failure counts twice.
    - **item-health** - two stages write it, so it cannot rely on a caller's own
      guarantee. `append_item_health` filters against `ITEM_HEALTH_KEY` instead.
    - **runtime-counters** - one writer, but the row is a cumulative total rather
      than an event, so a re-run of a failed shard would make a run-level sum
      count that shard twice. `append_runtime_counters` filters against
      `RUNTIME_COUNTERS_KEY`.

    Both filters read the file the job checked out, which is frozen at the
    commit its run was triggered at, so neither can see a row a second attempt
    pushed afterwards. `drop_repeated_rows` settles that after the merge.
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
    for stem in shards_in_window(today, within_days):
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


def load_settled_failures(state_dir: Path, date: str, *, codes: Collection[str]) -> set[str]:
    """Addresses that failed today for a reason today cannot change.

    The published ledger stops a repeat of a *success*. It cannot stop a repeat
    of a failure, because a failure is never published - so every later run of
    the same day planned the same paywall again and got the same paywall.
    Measured over 2026-08-24 to 2026-08-29, 403 such repeats bought 2 items.

    Only `date` is read, and only the codes the caller names. A rate limit or a
    reset connection is a different answer at 18:20 than it was at 02:20, so
    those codes are left out of the config list and their addresses come back.

    An empty `codes` returns nothing, which is exactly the behaviour this
    replaced - a run configured that way plans a failed address again.
    """
    if not codes:
        return set()
    wanted = set(codes)
    return {
        row["url_key"]
        for row in _read_rows(item_health_path(state_dir, date))
        if row["date"] == date and row["outcome"] != ItemOutcome.OK and row["code"] in wanted
    }


def load_source_counts(state_dir: Path, date: str) -> dict[str, int]:
    """Feed -> how many of today's items it has already put in front of a reader.

    The count a day-wide source ceiling reads. Only rows that reached the
    digest are counted: a feed whose page was behind a paywall spent a slot,
    but it did not fill any of the day, and the ceiling is about what a reader
    sees.

    Keyed on the address rather than the row, because one item settles once but
    can be written by more than one job, and a re-run of the same day writes it
    again. Counting rows would charge a feed twice for one story.
    """
    carried: dict[str, str] = {}
    for row in _read_rows(item_health_path(state_dir, date)):
        if row["date"] != date or row["outcome"] != ItemOutcome.OK:
            continue
        carried[row["url_key"]] = row["source_id"]
    counts: dict[str, int] = {}
    for source_id in carried.values():
        counts[source_id] = counts.get(source_id, 0) + 1
    return counts


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


def keyed_paths(state_dir: Path) -> list[tuple[Path, tuple[str, ...]]]:
    """Every ledger here that says what makes two of its rows the same record.

    `state/seen/` and `state/feed-health/` are deliberately absent. Neither has a
    key: `load_seen` folds a second sight by keeping the earliest, and a feed's
    row is one verdict per feed per run, which two runs are entitled to write
    twice.

    `state/feed-retirements.csv` is listed before anything writes it, because the
    settlement runs over whatever it finds and a missing file settles to nothing.
    Registering it with the shape rather than with its first writer is what stops
    two stale checkouts leaving one address retired twice.
    """
    return [
        (runtime_counters_path(state_dir), RUNTIME_COUNTERS_KEY),
        (feed_retirements_path(state_dir), FEED_RETIREMENT_KEY),
        *(
            (path, ITEM_HEALTH_KEY)
            for path in sorted((state_dir / ITEM_HEALTH_DIRNAME).glob("*.csv"))
        ),
    ]


def drop_repeated_rows(path: Path, key: tuple[str, ...]) -> int:
    """Rewrite the file without any row repeating a key an earlier row holds.

    This is the half of the guarantee `_append`'s filter cannot give. That filter
    reads the committed file the job checked out, and `actions/checkout` pins a
    job to the commit its run was triggered at - so a second execution of the
    same work cannot see rows the first one pushed after that commit. Its append
    lands them again, and `merge=union` then concatenates both sides line by
    line, which is the right answer for two runs writing different rows and
    exactly the wrong one for two attempts writing the same row. Measured on this
    repository 2026-08-31: run `2026-08-29-3` holds six counter rows for four
    shards and 44 repeated `(date, run_id, item_id)` item-health keys.

    So the file has to be settled once more after the merge, which is the only
    moment both sides have ever been in one place. The first row wins, because
    that is the rule `_append`'s callers already state: a re-run's items are
    skipped, so the ledgers stay describing the attempt that got there first.

    Rows are matched and rewritten as whole lines rather than re-serialized, so
    a kept row is byte-identical to the row that was read and a pass that drops
    nothing leaves no diff. Reading by line is safe for the same reason the merge
    is: every free-text cell in these contracts is pinned to printable ASCII on
    one line, so no cell can carry a newline.

    Returns how many rows were dropped, so a caller can log the count.
    """
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        lines = handle.readlines()
    if not lines:
        return 0
    header = next(csv.reader(lines[:1]), [])
    if any(name not in header for name in key):
        # A shard written before the key existed cannot be checked against it,
        # and refusing would cost a run its whole commit over an old file.
        return 0
    columns = [header.index(name) for name in key]
    seen: set[tuple[str, ...]] = set()
    kept = [lines[0]]
    dropped = 0
    for line in lines[1:]:
        cells = next(csv.reader([line]), [])
        if len(cells) <= max(columns):
            kept.append(line)
            continue
        found = tuple(cells[index] for index in columns)
        if found in seen:
            dropped += 1
            continue
        seen.add(found)
        kept.append(line)
    if dropped:
        path.write_text("".join(kept), encoding="utf-8", newline="")
    return dropped


def repeated_keys(path: Path, key: tuple[str, ...]) -> dict[tuple[str, ...], int]:
    """Every key the file holds more than one row for, and how many. Empty is clean."""
    counts: dict[tuple[str, ...], int] = {}
    for row in _read_rows(path):
        if any(name not in row for name in key):
            continue
        found = tuple(row[name] or "" for name in key)
        counts[found] = counts.get(found, 0) + 1
    return {found: count for found, count in counts.items() if count > 1}


def load_item_health_shard(path: Path) -> list[ItemHealthRow]:
    """Every row of one month's full-grain shard. Empty for a month never written."""
    return [ItemHealthRow.from_csv_row(row) for row in _read_rows(path)]


def write_telemetry_aggregate(path: Path, rows: list[TelemetryAggregateRow]) -> int:
    """Write one month's folded summary whole, replacing whatever was there.

    The only writer here that rewrites rather than appends, and the reason is
    that this file is derived: every row is a function of the shard it was folded
    from, so writing it twice writes the same bytes twice. Appending would double
    a month whenever the fold ran again over a shard a lost race had restored,
    and `merge=union` could not tell the copy from the original.

    Returns how many rows landed, so a caller can log the count.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = TelemetryAggregateRow.csv_columns()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.csv_row())
    return len(rows)


def load_telemetry_aggregate(path: Path) -> list[TelemetryAggregateRow]:
    """Every folded row of one month. Empty for a month never folded."""
    return [TelemetryAggregateRow.from_csv_row(row) for row in _read_rows(path)]


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
    for stem in shards_in_window(today, within_days):
        for raw in _read_rows(state_dir / HEALTH_DIRNAME / f"{stem}.csv"):
            try:
                rows.append(FeedHealthRow.from_csv_row(raw))
            except (KeyError, ValueError):
                continue
    rows.sort(key=lambda row: (row.date, _run_n(row.run_id)))
    return rows


def _run_n(run_id: str) -> int:
    """The execution number out of `<date>-<execution>`, so a later run sorts last.

    The trailing field is the GitHub run id on anything CI produced and a small
    ordinal on anything a developer machine did, and both increase with time, so
    the sort is chronological across the change and on either side of it.
    """
    return int(run_id.rsplit("-", 1)[1])
