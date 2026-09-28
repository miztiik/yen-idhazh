"""Which months one ledger's compaction absorbs, and which month files it drops.

**A month is absorbed whole or not at all**, and only once four things are true:
at least `daily_keep_days` whole days have passed since it ended, the daily
watermark is past its last day, the daily index names every one of its days,
and none of its raw days still holds files. The first two say the month is
done; the third that nothing of it is missing; the fourth that no re-run is
still waiting in it to be compacted. A month that fails the first, second or
fourth waits for a later wake. A month whose days the daily index does not all
name is a hole: it is refused by name, the watermark stays where it is and the
task exits 1, because absorbing it would put the missing day in no period.

**Absorbing is five steps, in this order and no other**: the month file, the
monthly index, the deletion of the daily files it absorbed, the daily index,
and the monthly watermark last. A pass that dies part way leaves the watermark
behind the truth, so the next wake absorbs that month again and loses nothing.
The daily files are joined as they are and never settled across days: a key
with no date cell may repeat on two days, and both rows are facts.

**A month file lives exactly `monthly_window` after its month is absorbed.**
Month M goes at the instant month M plus the window becomes absorbable, so the
period holds exactly that many months at every wake and the ledger reaches back
`daily_keep_days` further. `first_kept_month` is the one place that is worked
out; the daily period's first run asks it too, so it never compacts a day the
window would drop at once.

Every month here is a UTC month, and every rule is whole days after a month's
own end, so every wake of one UTC day gets the same answer (CLAUDE.md section 2).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from idhazh import ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy, DaysWindow, ForeverWindow, Window
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.gardener import schedule
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


def drop(tree: CompactTree, *, first_kept: str | None) -> tuple[Stop, ...]:
    """Every month file the window no longer keeps goes, with its index entry."""
    if first_kept is None:
        return ()
    gone = [month for month in sorted(tree.monthly) if month < first_kept]
    for month in gone:
        found = ledger.compact_file(tree.state_dir, tree.ledger, Period.MONTHLY, month)
        if found is not None:
            tree.delete(found)
        del tree.monthly[month]
    if gone:
        tree.write_index(Period.MONTHLY)
    return ()


def _ready(tree: CompactTree, month: str, *, now: datetime, after_days: int) -> bool:
    """Whether a month is done: old enough, compacted to its end, and no raw day waiting in it."""
    return (
        schedule.is_month_eligible(month, now=now, after_days=after_days)
        and tree.daily_through is not None
        and tree.daily_through > days_of(month)[-1]
        and not any(day.startswith(f"{month}-") for day in tree.raw_days)
    )


def _refused(tree: CompactTree, month: str, why: str) -> tuple[Stop, ...]:
    """A month that cannot be absorbed, said once by name. The watermark stays where it is."""
    logger.error(
        "a month is not absorbed ledger=%s month=%s reason=%s", tree.ledger.value, month, why
    )
    return (Stop(StopReason.FAILED, month),)


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
    elif tree.daily:
        month = min(tree.daily)[:7]
    else:
        return ()
    taken = 0
    while _ready(tree, month, now=now, after_days=policy.daily_keep_days):
        if taken == policy.max_periods_per_run:
            return (Stop(StopReason.CEILING, month),)
        days = days_of(month)
        missing = [day for day in days if day not in tree.daily]
        if missing:
            where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.DAILY)
            return _refused(tree, month, f"{where.name} does not name {', '.join(missing)}")
        files = [
            ledger.compact_file(tree.state_dir, tree.ledger, Period.DAILY, day) for day in days
        ]
        absent = [day for day, found in zip(days, files, strict=True) if found is None]
        if absent:
            return _refused(tree, month, f"no daily file holds {', '.join(absent)}")
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
        tree.write_index(Period.MONTHLY)
        for path in held:
            tree.delete(path)
        for day in days:
            del tree.daily[day]
        tree.write_index(Period.DAILY)
        tree.monthly_through = month
        tree.write_watermark(
            Period.MONTHLY, through=month, advanced_at=stamp, run_id=identity.run_id
        )
        taken += 1
        month = shift(month, 1)
    return ()
