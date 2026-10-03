"""Which raw days one ledger's compaction takes into daily files, and which raw listings it drops.

**A day is taken once `compact_after_days` whole days have passed since it
ended**, measured from 00:00 UTC on the day after it, so every wake of one UTC
day finds the same newest day. At one, a wake on the 25th takes days up to the
23rd.

**Days are taken in order, each on its own, at most `max_periods_per_run` a
pass.** For each day: list its raw folder and read every file in it, settle the
rows, and plan the day's listing and its compact file. The pass writes its
final daily index once, then deletes raw files, and advances its watermark
once, last. Before the index lands, raw files survive; after it lands, the
next wake rebuilds from the indexed day and any raw files left.
A file that cannot be read stops its day and is never
deleted; a day holding more than `max_raw_files_per_period` files is refused
the same way. Either one leaves the watermark before that day, so the next
wake retries it rather than stepping past it.

**A day with no raw files still gets a zero-row file and an index entry.** That
is what keeps the newest day the daily index names equal to the watermark, so a
reader can tell a quiet day from a hole without opening the watermark. Two days
missed are two files, never one.

**A day at or below the watermark that has raw files again is taken again.** A
GitHub re-run writes into the day its run first wrote, for up to thirty days.
The day's compact file is rebuilt from its own rows and the new raw files
together, settled once - one file's rows per work unit, the last of its highest
attempt, then the first row per key - so a re-run replaces its first attempt
even when it filed fewer rows.
The watermark stays where it is, and the day counts against the budget, oldest
first. Raw files in a month already absorbed are refused by name and kept:
`daily_keep_days` outlasts GitHub's re-run window, so no re-run can land there
and a person decides what they are. **A day the daily index names whose compact
file is not there is refused too**, as `file-missing`, and its raw files are
kept: rebuilt from the re-run's files alone it would hold only the shards that
ran again, and its index entry would call that smaller day complete.

**A first run starts on the first of a month**: the month of the older of the
oldest raw day and the newest eligible day, or the oldest month the monthly
window keeps if that is later. Every month the daily index holds is then whole,
which keeps the monthly period's check for a missing day exact. Raw days in a
month the window no longer keeps are past the ledger's reach, and are dropped.
**A window that only reports keeps them instead**: it names their files for the
record, and the pass takes those days like any other, a first run starting as if
the window kept every month.

**A listing outlives its day by `raw_index_keep_days`**, counted from the day's
end. It goes only once its day is compacted and its raw folder is empty, so a
day that is waiting to be taken again keeps the listing it will replace. It goes
whether the window reports or not, because its day's rows are in a daily file.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.gardener import named_trees, schedule
from idhazh.gardener.tasks import _index_day
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop

logger = logging.getLogger(__name__)


def drop_listings(
    tree: CompactTree, policy: CompactionPolicy, *, now: datetime
) -> tuple[Stop, ...]:
    """Listings past `raw_index_keep_days` whose day is compacted and holds no raw file."""
    waiting = set(tree.raw_days)
    for day in named_trees.listed_days(tree.listing, tree.state_dir, tree.ledger):
        if tree.daily_through is None or day > tree.daily_through or day in waiting:
            continue
        if schedule.is_eligible(
            date.fromisoformat(day), now=now, after_days=policy.raw_index_keep_days
        ):
            tree.delete(ledger.raw_index_path(tree.state_dir, tree.ledger, day))
    return ()


def _past_the_window(
    tree: CompactTree, *, first_kept: str | None
) -> list[tuple[str, list[Path] | ValueError]]:
    """Every raw day past the window, with its files or why they cannot be read.

    It reads those days and decides nothing, so a window that only reports names
    exactly the files a live one deletes.
    """
    if first_kept is None:
        return []
    past = [day for day in tree.raw_days if day[:7] < first_kept]
    tree.listing.fetch([tree.raw_day_folder(day) for day in past])
    found: list[tuple[str, list[Path] | ValueError]] = []
    for day in past:
        try:
            files = ledger.read_day_files(tree.state_dir, tree.ledger, day)
        except ValueError as refusal:
            found.append((day, refusal))
            continue
        found.append((day, [held.path for held in files]))
    return found


def drop(tree: CompactTree, *, first_kept: str | None) -> tuple[Stop, ...]:
    """Raw days the monthly window no longer keeps go, each with every file it holds."""
    stops: list[Stop] = []
    gone: set[str] = set()
    for day, held in _past_the_window(tree, first_kept=first_kept):
        if isinstance(held, ValueError):
            logger.error(
                "a raw day past the window is kept ledger=%s day=%s reason=%s",
                tree.ledger.value,
                day,
                held,
            )
            stops.append(Stop(StopReason.FAILED, day))
            continue
        for path in held:
            tree.delete(path)
        gone.add(day)
    tree.raw_days = [day for day in tree.raw_days if day not in gone]
    return tuple(stops)


def spare(tree: CompactTree, *, first_kept: str | None) -> tuple[Stop, ...]:
    """Every raw file the monthly window would drop is named and kept, for `compact` to take.

    A day that cannot be read is one a live window keeps too, so it is not named
    here; `compact` refuses it by name when it comes to take it.
    """
    for _day, held in _past_the_window(tree, first_kept=first_kept):
        if not isinstance(held, ValueError):
            for path in held:
                tree.spare(path)
    return ()


def _new_days(tree: CompactTree, *, newest: date, first_kept: str | None) -> list[str]:
    """The days after the watermark up to the newest eligible one, or a first run's days."""
    if tree.daily_through is not None:
        start = date.fromisoformat(tree.daily_through) + timedelta(days=1)
    else:
        oldest = date.fromisoformat(tree.raw_days[0]) if tree.raw_days else newest
        start = min(oldest, newest).replace(day=1)
        if first_kept is not None and start.isoformat()[:7] < first_kept:
            start = date.fromisoformat(f"{first_kept}-01")
    days: list[str] = []
    if tree.months is not None:
        for month in sorted(tree.months):
            year, number = map(int, month.split("-"))
            first = date(year, number, 1)
            last = date(year, number, calendar.monthrange(year, number)[1])
            if last < start:
                continue
            if first > start and start <= newest:
                raise ValueError(
                    f"named months omit {start.isoformat()[:7]} after the daily watermark"
                )
            cursor = max(start, first)
            while cursor <= min(last, newest):
                days.append(cursor.isoformat())
                cursor += timedelta(days=1)
            start = cursor
        return days
    while start <= newest:
        days.append(start.isoformat())
        start += timedelta(days=1)
    return days


def _take[C: Contract](
    tree: CompactTree,
    policy: CompactionPolicy,
    day: str,
    *,
    model: type[C],
    key: tuple[str, ...],
    identity: WriterIdentity,
    stamp: str,
) -> tuple[str, ledger.LedgerFault | None] | None:
    """Compact one day, or say why it cannot be and which fault that is, if any.

    Nothing is decided for a day that fails.
    """
    try:
        files = ledger.read_day_files(tree.state_dir, tree.ledger, day)
    except ValueError as refusal:
        return str(refusal), None
    if len(files) > policy.max_raw_files_per_period:
        return (
            f"it holds {len(files)} raw files and one period is built from at most "
            f"{policy.max_raw_files_per_period}",
            None,
        )
    existing = (
        named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day)
        if day in tree.daily
        else None
    )
    if day in tree.daily and existing is None:
        where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.DAILY)
        return (
            f"{where.name} names the day and its file is not there. Restore the file from "
            "git history, and the next wake takes the re-run in",
            ledger.LedgerFault.FILE_MISSING,
        )
    try:
        rows = [tree.load(existing, model=model)] if existing is not None else []
        for held in files:
            rows.append(tree.load(held.path, model=model))
    except ValueError as refusal:
        return str(refusal), None
    settled = ledger.settle_rows(rows, key)
    built = ledger.render_period(
        tree.state_dir,
        settled,
        model=model,
        ledger=tree.ledger,
        period=Period.DAILY,
        covers=day,
        identity=identity,
        built_from=len(files) + (existing is not None),
    )
    listing = _index_day.listing(files, ledger=tree.ledger, day=day, listed_at=stamp)
    tree.write(
        ledger.raw_index_path(tree.state_dir, tree.ledger, day),
        listing.to_json().encode("ascii"),
    )
    if existing is not None and existing != built.path:
        tree.delete(existing)
    tree.write(built.path, built.data)
    tree.daily[day] = CompactEntry(covers=day, rows=len(settled), bytes=len(built.data))
    tree.mark_index(Period.DAILY)
    for held in files:
        tree.delete(held.path)
    if tree.daily_through is None or day > tree.daily_through:
        tree.daily_through = day
        tree.write_watermark(Period.DAILY, through=day, advanced_at=stamp, run_id=identity.run_id)
    return None


def compact(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    stamp: str,
    identity: WriterIdentity,
    first_kept: str | None,
) -> tuple[Stop, ...]:
    """Take the days waiting to be taken again, then the new ones, oldest first, to the budget."""
    model, key = ledger.door_contract(tree.ledger), ledger.door_key(tree.ledger)
    stops: list[Stop] = []
    again: list[str] = []
    for day in tree.raw_days:
        if tree.daily_through is None or day > tree.daily_through:
            continue
        if tree.monthly_through is not None and day[:7] <= tree.monthly_through:
            logger.error(
                "raw files sit in a month already absorbed, and are kept ledger=%s day=%s",
                tree.ledger.value,
                day,
            )
            stops.append(Stop(StopReason.FAILED, day))
            continue
        again.append(day)
    newest = schedule.newest_eligible(now=now, after_days=policy.compact_after_days)
    days = again + _new_days(tree, newest=newest, first_kept=first_kept)
    # Every day the budget can reach, fetched in one call before the first is read:
    # a day that fails costs nothing, so the ones waiting again may all fail first.
    reached = days[: len(again) + policy.max_periods_per_run]
    tree.listing.fetch(
        [
            *(tree.raw_day_folder(day) for day in reached),
            *sorted({tree.daily_month_folder(day[:7]) for day in reached if day in tree.daily}),
        ]
    )
    taken = 0
    for day in days:
        if taken == policy.max_periods_per_run:
            stops.append(Stop(StopReason.CEILING, day))
            break
        fresh = tree.daily_through is None or day > tree.daily_through
        refused = _take(tree, policy, day, model=model, key=key, identity=identity, stamp=stamp)
        if refused is not None:
            why, fault = refused
            logger.error(
                "a raw day is not compacted, and its files are kept "
                "ledger=%s day=%s fault=%s reason=%s",
                tree.ledger.value,
                day,
                fault or "none",
                why,
            )
            stops.append(Stop(StopReason.FAILED, day))
            if fresh:
                break
            continue
        taken += 1
    return tuple(stops)
