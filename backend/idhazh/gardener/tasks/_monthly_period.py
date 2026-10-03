"""Which months one ledger's compaction absorbs, and which month files it drops.

**A month is absorbed whole or not at all**, and only once four things are true:
at least `daily_keep_days` whole days have passed since it ended, the daily
watermark is past its last day, the daily index names every one of its days,
and none of its raw days still holds files. The first two say the month is
done; the third that nothing of it is missing; the fourth that no re-run is
still waiting in it to be compacted. A month that fails the first, second or
fourth waits for a later wake. A month whose days the daily index does not all
name is a hole: it is refused by name, the watermark stays where it is and the
task exits 1, because absorbing it would put the missing day in no period. The
refusal names the fault the query door gives the same gap - `day-missing` for
a day the index does not name, `file-missing` for a day file that is not there -
so one search finds it in the gardener's log and in the browser's console.

**The pass writes all month files, then the final monthly and daily indexes
once, then deletes absorbed daily files, then advances the monthly watermark
once, last.** Before the monthly index lands, daily files survive. After it
lands, the next wake keeps the indexed month, removes remaining daily files
by their calendar dates, and advances the watermark without rebuilding.
The daily files are joined as they are and never settled across days: a key
with no date cell may repeat on two days, and both rows are facts.

**A month file lives exactly `monthly_window` after its month is absorbed.**
Month M goes at the instant month M plus the window becomes absorbable, so the
period holds exactly that many months at every wake and the ledger reaches back
`daily_keep_days` further. `first_kept_month` is the one place that is worked
out; the daily period's first run asks it too, so it never compacts a day the
window would drop at once. A declaration that packs years keeps the window
forever, and its month files leave only by being packed into their year
(`_yearly_period`).

**A window that only reports names the month files it would drop and keeps
them**, with their index entries, so the record counts what turning it live
would take while packing goes on. `drop` and `spare` read the same list.

Every month here is a UTC month, and every rule is whole days after a month's
own end, so every wake of one UTC day gets the same answer (CLAUDE.md section 2).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy, DaysWindow, ForeverWindow, Window
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.gardener import named_trees, schedule
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop

logger = logging.getLogger(__name__)


def shift(month: str, count: int) -> str:
    """The `YYYY-MM` month `count` months after this one, or before it when negative."""
    total = int(month[:4]) * 12 + int(month[5:7]) - 1 + count
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def days_of(month: str) -> list[str]:
    """Every UTC day of a `YYYY-MM` month, in order."""
    first = date.fromisoformat(f"{month}-01")
    after = date.fromisoformat(f"{shift(month, 1)}-01")
    return [(first + timedelta(days=offset)).isoformat() for offset in range((after - first).days)]


def first_kept_month(*, now: datetime, daily_keep_days: int, window: Window) -> str | None:
    """The oldest month whose file the window still keeps at `now`, or None when it keeps all.

    A month is absorbable once `daily_keep_days` whole days have passed since
    it ended, so the newest absorbable month is the one before the month
    `daily_keep_days` back. A window of months keeps that many months up to it;
    a window of days drops a month once the window and `daily_keep_days` have
    both passed since it ended.
    """
    if isinstance(window, ForeverWindow):
        return None
    if isinstance(window, DaysWindow):
        return (now - timedelta(days=window.value + daily_keep_days)).strftime("%Y-%m")
    newest_absorbable = shift((now - timedelta(days=daily_keep_days)).strftime("%Y-%m"), -1)
    return shift(newest_absorbable, 1 - window.value)


def _past_the_window(tree: CompactTree, *, first_kept: str | None) -> list[tuple[str, Path | None]]:
    """Every month the window no longer keeps, oldest first, beside its file or None.

    It reads the listing and decides nothing, so a window that only reports names
    exactly the files a live one deletes.
    """
    if first_kept is None:
        return []
    return [
        (
            month,
            named_trees.compact_file(
                tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
            ),
        )
        for month in sorted(tree.monthly)
        if month < first_kept and (tree.months is None or month in tree.months)
    ]


def drop(tree: CompactTree, *, first_kept: str | None) -> tuple[Stop, ...]:
    """Every month file the window no longer keeps goes, with its index entry."""
    gone = _past_the_window(tree, first_kept=first_kept)
    for month, found in gone:
        if found is not None:
            tree.delete(found)
        else:
            logger.warning(
                "a month the window drops has no file left to delete ledger=%s month=%s fault=%s",
                tree.ledger.value,
                month,
                ledger.LedgerFault.FILE_MISSING,
            )
        del tree.monthly[month]
    if gone:
        tree.mark_index(Period.MONTHLY)
    return ()


def spare(tree: CompactTree, *, first_kept: str | None) -> tuple[Stop, ...]:
    """Every month file the window would drop is named and kept, with its index entry."""
    for _month, found in _past_the_window(tree, first_kept=first_kept):
        if found is not None:
            tree.spare(found)
    return ()


def _ready(tree: CompactTree, month: str, *, now: datetime, after_days: int) -> bool:
    """Whether a month is done: old enough, compacted to its end, and no raw day waiting in it."""
    return (
        (tree.months is None or month in tree.months)
        and schedule.is_month_eligible(month, now=now, after_days=after_days)
        and tree.daily_through is not None
        and (
            tree.daily_through >= days_of(month)[-1]
            if tree.months is not None
            else tree.daily_through > days_of(month)[-1]
        )
        and not any(day.startswith(f"{month}-") for day in tree.raw_days)
    )


def _refused(
    tree: CompactTree, month: str, why: str, fault: ledger.LedgerFault | None = None
) -> tuple[Stop, ...]:
    """A month that cannot be absorbed, said once by name. The watermark stays where it is."""
    logger.error(
        "a month is not absorbed ledger=%s month=%s fault=%s reason=%s",
        tree.ledger.value,
        month,
        fault or "none",
        why,
    )
    return (Stop(StopReason.FAILED, month),)


def _finish(tree: CompactTree, month: str) -> tuple[Stop, ...]:
    """Finish an indexed month without rebuilding it from its remaining daily files."""
    found = named_trees.compact_file(
        tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
    )
    if found is None:
        return _refused(
            tree,
            month,
            "the monthly index names it and no monthly file holds it",
            ledger.LedgerFault.FILE_MISSING,
        )
    tree.listing.fetch([tree.daily_month_folder(month)])
    for day in days_of(month):
        held = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
        )
        if held is not None:
            tree.delete(held)
        tree.daily.pop(day, None)
    tree.mark_index(Period.DAILY)
    return ()


def absorb(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    stamp: str,
    identity: WriterIdentity,
) -> tuple[Stop, ...]:
    """Absorb every month that is done, oldest first, at most `max_periods_per_run` of them.

    With no monthly watermark the first month is the one holding the oldest day
    the daily index names.
    """
    model = ledger.door_contract(tree.ledger)
    if tree.monthly_through is not None:
        month = shift(tree.monthly_through, 1)
    elif tree.monthly:
        month = min(tree.monthly)
    elif tree.daily:
        month = min(tree.daily)[:7]
    else:
        return ()
    if tree.months is not None:
        candidates = [
            named
            for named in sorted(tree.months)
            if tree.monthly_through is None
            or named > tree.monthly_through
            or any(day.startswith(f"{named}-") for day in tree.daily)
        ]
        if not candidates:
            return ()
        month = candidates[0]
        pending = sorted(
            {
                day[:7]
                for day in tree.daily
                if day[:7] < month
                and day[:7] not in tree.monthly
                and day[:4] not in tree.yearly
                and (tree.monthly_through is None or day[:7] > tree.monthly_through)
            }
        )
        if pending:
            return _refused(
                tree,
                month,
                f"name pending months before advancing the monthly watermark: {pending}",
            )
    ready: list[str] = []
    while len(ready) < policy.max_periods_per_run and _ready(
        tree, shift(month, len(ready)), now=now, after_days=policy.daily_keep_days
    ):
        ready.append(shift(month, len(ready)))
    tree.listing.fetch([tree.daily_month_folder(held) for held in ready])
    taken = 0
    while _ready(tree, month, now=now, after_days=policy.daily_keep_days):
        if taken == policy.max_periods_per_run:
            return (Stop(StopReason.CEILING, month),)
        if month in tree.monthly:
            stops = _finish(tree, month)
            if stops:
                return stops
            tree.monthly_through = max(month, tree.monthly_through or month)
            tree.write_watermark(
                Period.MONTHLY,
                through=tree.monthly_through,
                advanced_at=stamp,
                run_id=identity.run_id,
            )
            taken += 1
            month = shift(month, 1)
            continue
        days = days_of(month)
        missing = [day for day in days if day not in tree.daily]
        if missing:
            where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.DAILY)
            return _refused(
                tree,
                month,
                f"{where.name} does not name {', '.join(missing)}. Re-pack each such day from "
                "its raw files, or from git history if they are gone",
                ledger.LedgerFault.DAY_MISSING,
            )
        files = [
            named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day)
            for day in days
        ]
        absent = [day for day, found in zip(days, files, strict=True) if found is None]
        if absent:
            return _refused(
                tree,
                month,
                f"no daily file holds {', '.join(absent)}. Restore each from git history, "
                "and the next wake absorbs the month",
                ledger.LedgerFault.FILE_MISSING,
            )
        held = [found for found in files if found is not None]
        try:
            rows = [row for path in held for row in tree.load(path, model=model)]
        except ValueError as refusal:
            return _refused(tree, month, str(refusal))
        built = ledger.render_period(
            tree.state_dir,
            rows,
            model=model,
            ledger=tree.ledger,
            period=Period.MONTHLY,
            covers=month,
            identity=identity,
            built_from=len(held),
        )
        tree.write(built.path, built.data)
        tree.monthly[month] = CompactEntry(covers=month, rows=len(rows), bytes=len(built.data))
        tree.mark_index(Period.MONTHLY)
        for path in held:
            tree.delete(path)
        for day in days:
            del tree.daily[day]
        tree.mark_index(Period.DAILY)
        tree.monthly_through = max(month, tree.monthly_through or month)
        tree.write_watermark(
            Period.MONTHLY, through=tree.monthly_through, advanced_at=stamp, run_id=identity.run_id
        )
        taken += 1
        month = shift(month, 1)
    return ()
