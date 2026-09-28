"""Which raw days one ledger's compaction takes into daily files, and which raw listings it drops.

**A day is taken once `compact_after_days` whole days have passed since it
ended**, measured from 00:00 UTC on the day after it, so every wake of one UTC
day finds the same newest day. At the default of one, a wake on the 25th takes
days up to the 23rd.

**Days are taken in order, each on its own, at most `max_periods_per_run` a
pass.** For each day: list its raw folder and read every file in it, settle the
rows, write the day's listing and its compact file, rewrite the daily index,
delete the raw files, and advance the watermark last. A pass that dies part
way leaves the watermark behind the truth, so the next wake takes that one day
again and loses nothing. A file that cannot be read stops its day and is never
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
and a person decides what they are.

**A first run starts on the first of a month**: the month of the older of the
oldest raw day and the newest eligible day, or the oldest month the monthly
window keeps if that is later. Every month the daily index holds is then whole,
which keeps the monthly period's check for a missing day exact. Raw days in a
month the window no longer keeps are past the ledger's reach, and are dropped.

**A listing outlives its day by `raw_index_keep_days`**, counted from the day's
end. It goes only once its day is compacted and its raw folder is empty, so a
day that is waiting to be taken again keeps the listing it will replace.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.gardener import schedule
from idhazh.gardener.tasks import _index_day
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop

logger = logging.getLogger(__name__)


def drop(
    tree: CompactTree, policy: CompactionPolicy, *, now: datetime, first_kept: str | None
) -> tuple[Stop, ...]:
    """Listings past `raw_index_keep_days`, and raw days the monthly window no longer keeps."""
    waiting = set(tree.raw_days)
    for day in ledger.listed_days(tree.state_dir, tree.ledger):
        if tree.daily_through is None or day > tree.daily_through or day in waiting:
            continue
        if schedule.is_eligible(
            date.fromisoformat(day), now=now, after_days=policy.raw_index_keep_days
        ):
            tree.delete(ledger.raw_index_path(tree.state_dir, tree.ledger, day))
    if first_kept is None:
        return ()
    stops: list[Stop] = []
    kept: list[str] = []
    for day in tree.raw_days:
        if day[:7] >= first_kept:
            kept.append(day)
            continue
        try:
            files = ledger.read_day_files(tree.state_dir, tree.ledger, day)
        except ValueError as refusal:
            logger.error(
                "a raw day past the window is kept ledger=%s day=%s reason=%s",
                tree.ledger.value,
                day,
                refusal,
            )
            stops.append(Stop(StopReason.FAILED, day))
            kept.append(day)
            continue
        for held in files:
            tree.delete(held.path)
    tree.raw_days = kept
    return tuple(stops)


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
) -> str | None:
    """Compact one day, or say why it cannot be. Nothing is decided for a day that fails."""
    try:
        files = ledger.read_day_files(tree.state_dir, tree.ledger, day)
    except ValueError as refusal:
        return str(refusal)
    if len(files) > policy.max_raw_files_per_period:
        return (
            f"it holds {len(files)} raw files and one period is built from at most "
            f"{policy.max_raw_files_per_period}"
        )
    existing = (
        ledger.compact_file(tree.state_dir, tree.ledger, Period.DAILY, day)
        if day in tree.daily
        else None
    )
    try:
        rows = [tree.load(existing, model=model)] if existing is not None else []
        for held in files:
            rows.append(tree.load(held.path, model=model))
    except ValueError as refusal:
        return str(refusal)
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
    tree.write_index(Period.DAILY)
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
    taken = 0
    for day in again + _new_days(tree, newest=newest, first_kept=first_kept):
        if taken == policy.max_periods_per_run:
            stops.append(Stop(StopReason.CEILING, day))
            break
        fresh = tree.daily_through is None or day > tree.daily_through
        why = _take(tree, policy, day, model=model, key=key, identity=identity, stamp=stamp)
        if why is not None:
            logger.error(
                "a raw day is not compacted, and its files are kept ledger=%s day=%s reason=%s",
                tree.ledger.value,
                day,
                why,
            )
            stops.append(Stop(StopReason.FAILED, day))
            if fresh:
                break
            continue
        taken += 1
    return tuple(stops)
