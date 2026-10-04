"""Which months one ledger's compaction absorbs, and which month files it drops.

**The months are the ones chosen for this wake** (`_compaction_periods`):
consecutive months after the monthly mark, each old enough and each whose last
day the daily mark has reached. The step names what it reads of them, then
closes them oldest first, each whole or not at all. A month a raw day still
waits in is held for the day step to pack that day, and the months after it
wait with it.

**A month accounts for every day from its 1st, or from the ledger's first day
when the ledger began inside it.** A day with a `packed` entry gives its file's
rows; an `empty` day gives none; a `lost` day goes into the month's
`lost_days`. A day with no entry is a hole. When its own packed file is at its
named path, the file is adopted (`index-rebuilt`); otherwise the day is
recorded lost (`recorded-lost`), and the pass goes on. A hole whose raw files
are still there holds its month instead: its own file, if any, is adopted
first, so the day step rebuilds the day from it and the raw files together, and
the month closes at the next wake. A month whose days give no row is an `empty`
entry with no file, its lost days listed on it. Only a day is ever `lost`.

**A month's own file, at its path while no entry names it, is adopted.** It
gives the month its rows and no lost day. A month whose days still hold files
beside such a file is refused, because nothing is written over a packed file
no entry names. A day whose entry says `packed` while its file is not there is
refused as `file-missing` (the name the query door gives the same gap), and the
month waits.

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

from idhazh import ledger, month_partition
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import DaysWindow, ForeverWindow, Window
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.gardener import ledger_marks, named_trees, schedule
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
    newest_absorbable = schedule.newest_eligible_month(now=now, after_days=daily_keep_days)
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


def _counted(tree: CompactTree, month: str) -> list[str]:
    """The days of a month its record accounts for: every one, or those from the ledger's first.

    The ledger began inside the month when nothing coarser is packed or marked
    and the oldest day its daily index names falls in it.
    """
    days = days_of(month)
    coarser = tree.monthly or tree.yearly or tree.monthly_through or tree.yearly_through
    if coarser or not tree.daily:
        return days
    first = min(tree.daily)
    return [day for day in days if day >= first]


def _waiting(tree: CompactTree, month: str) -> bool:
    """Whether a raw day still waits in a month for the day step to pack it."""
    return any(day.startswith(f"{month}-") for day in tree.raw_days)


def _recovered(tree: CompactTree, note: RecoveryNote, covers: str) -> None:
    """Say once what the pass recovered instead of stopping, and the period it is about."""
    logger.warning(
        "a period was recovered ledger=%s period=%s note=%s", tree.ledger.value, covers, note
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


def _forget_days(tree: CompactTree, month: str) -> None:
    """Take every day of a closed month out of the daily index, whatever its entry says."""
    for day in days_of(month):
        tree.daily.pop(day, None)
    tree.mark_index(Period.DAILY)


def _adopt(tree: CompactTree, days: list[str]) -> dict[str, ledger_marks.Adopted]:
    """Each of these days' own file, for each day that has one, with the entry it earns."""
    found: dict[str, ledger_marks.Adopted] = {}
    for day in days:
        held = ledger_marks.adopt(tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day)
        if held is not None:
            found[day] = held
    return found


def _keep(tree: CompactTree, adopted: dict[str, ledger_marks.Adopted]) -> None:
    """Index each adopted day as `packed`, and say so once a day."""
    for day, held in adopted.items():
        tree.daily[day] = held.entry
        _recovered(tree, RecoveryNote.INDEX_REBUILT, day)
    if adopted:
        tree.mark_index(Period.DAILY)

def _hold(tree: CompactTree, month: str) -> tuple[Stop, ...]:
    """Hold a month a raw day still waits in, adopting first each hole's own file.

    The day step rebuilds a day from its indexed file and its raw files
    together, so a hole's file is adopted before the day step comes to it, or
    the rebuild would hold the raw rows alone.
    """
    holes = [day for day in _counted(tree, month) if day not in tree.daily]
    try:
        adopted = _adopt(tree, holes)
    except ValueError as refusal:
        return _refused(tree, month, str(refusal))
    _keep(tree, adopted)
    logger.info(
        "a month waits for its raw days to be packed ledger=%s month=%s", tree.ledger.value, month
    )
    return ()


def _finish(tree: CompactTree, month: str) -> tuple[Stop, ...]:
    """Finish an indexed month without rebuilding it: its entry stands, its days' leftovers go.

    An `empty` month has no file to look for, and a `packed` one whose file is
    not there is refused as `file-missing`.
    """
    if (
        tree.monthly[month].names_file
        and named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
        )
        is None
    ):
        return _refused(
            tree,
            month,
            "the monthly index names it and no monthly file holds it",
            ledger.LedgerFault.FILE_MISSING,
        )
    for day in days_of(month):
        held = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
        )
        if held is not None:
            tree.delete(held)
    _forget_days(tree, month)
    return ()


def _close[C: Contract](
    tree: CompactTree, month: str, *, model: type[C], identity: WriterIdentity
) -> tuple[Stop, ...]:
    """Close one month no entry names yet, from its days or from its own file.

    A month's own file at its path, which no entry names, is the month's record
    when its days give no row, and is kept when it holds exactly the rows its
    days hold - what a pass that stopped before its indexes leaves. When the two
    differ the month is refused: nothing is written over a packed file no entry
    names. Nothing is recorded or logged until every refusal is behind it, so a
    month that waits leaves no day half recorded.
    """
    try:
        own = ledger_marks.adopt(tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month)
    except ValueError as refusal:
        return _refused(tree, month, str(refusal))
    days = _counted(tree, month)
    packed: dict[str, Path] = {}
    absent: list[str] = []
    for day in days:
        entry = tree.daily.get(day)
        if entry is None or not entry.names_file:
            continue
        found = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
        )
        if found is None:
            absent.append(day)
        else:
            packed[day] = found
    if absent:
        return _refused(
            tree,
            month,
            f"no daily file holds {', '.join(absent)}. Restore each from git history, "
            "and the next wake absorbs the month",
            ledger.LedgerFault.FILE_MISSING,
        )
    holes = [day for day in days if day not in tree.daily]
    try:
        adopted = _adopt(tree, holes)
    except ValueError as refusal:
        return _refused(tree, month, str(refusal))
    packed.update((day, held.path) for day, held in adopted.items())
    sources = [packed[day] for day in sorted(packed)]
    if own is not None and not sources:
        tree.monthly[month] = own.entry
        tree.mark_index(Period.MONTHLY)
        _recovered(tree, RecoveryNote.INDEX_REBUILT, month)
        _forget_days(tree, month)
        return ()
    try:
        rows = [row for path in sources for row in tree.load(path, model=model)]
        if own is not None and tree.load(own.path, model=model) != rows:
            return _refused(
                tree,
                month,
                f"{own.path.name} is at its path, no monthly entry names it, and it holds "
                "other rows than its days. Nothing is written over a packed file no entry "
                "names, so the month waits",
            )
    except ValueError as refusal:
        return _refused(tree, month, str(refusal))
    lost = [
        day
        for day in days
        if (day in holes and day not in adopted)
        or ((entry := tree.daily.get(day)) is not None and entry.state is EntryState.LOST)
    ]
    _keep(tree, adopted)
    for day in holes:
        if day not in adopted:
            _recovered(tree, RecoveryNote.RECORDED_LOST, day)
    if own is not None:
        tree.monthly[month] = own.entry.model_copy(update={"lost_days": lost})
        _recovered(tree, RecoveryNote.INDEX_REBUILT, month)
    elif rows:
        built = ledger.render_period(
            tree.state_dir,
            rows,
            model=model,
            ledger=tree.ledger,
            period=Period.MONTHLY,
            covers=month,
            identity=identity,
            built_from=len(sources),
        )
        tree.write(built.path, built.data)
        tree.monthly[month] = CompactEntry(
            covers=month, rows=len(rows), bytes=len(built.data), lost_days=lost
        )
    else:
        tree.monthly[month] = CompactEntry(
            covers=month, rows=0, bytes=0, state=EntryState.EMPTY, lost_days=lost
        )
    tree.mark_index(Period.MONTHLY)
    for path in sources:
        tree.delete(path)
    _forget_days(tree, month)
    return ()

def absorb(
    tree: CompactTree, choice: StepChoice, *, stamp: str, identity: WriterIdentity
) -> tuple[Stop, ...]:
    """Close the months chosen for this wake, oldest first, stopping at the first one held.

    A choice an operator range refused stops here, at the month the range left
    out, with nothing taken.
    """
    if choice.stopped_because is StopReason.FAILED and choice.resume_from is not None:
        return _refused(
            tree,
            choice.resume_from,
            "the operator range leaves it out, and it closes before any month the range "
            "names. Widen the range to include it",
        )
    if choice.first is None or choice.last is None:
        return ()
    months = month_partition.months_between(choice.first, choice.last)
    tree.name_months(months)
    closing: list[str] = []
    for month in months:
        if _waiting(tree, month):
            break
        closing.append(month)
    tree.listing.fetch(
        [tree.daily_month_folder(month) for month in closing if month not in tree.monthly]
    )
    model = ledger.door_contract(tree.ledger)
    for month in months:
        if month not in closing:
            return _hold(tree, month)
        if month in tree.monthly:
            stops = _finish(tree, month)
        else:
            stops = _close(tree, month, model=model, identity=identity)
        if stops:
            return stops
        tree.monthly_through = max(month, tree.monthly_through or month)
        tree.write_watermark(
            Period.MONTHLY, through=tree.monthly_through, advanced_at=stamp, run_id=identity.run_id
        )
    if choice.stopped_because is StopReason.CEILING and choice.resume_from is not None:
        return (Stop(StopReason.CEILING, choice.resume_from),)
    return ()
