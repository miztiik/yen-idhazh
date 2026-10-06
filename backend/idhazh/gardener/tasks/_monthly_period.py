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

**A day file the month cannot read, or that its entry names and the tree
lacks, costs that day and not the month.** One that cannot be read is moved to
the ledger's set-aside folder (`set-aside`), and one that is not there has
nothing to move; either way its day goes into `lost_days` (`recorded-lost`) and
the month closes from the rest. Every month entry the step writes counts in
`set_aside` the files its days moved aside and those it moved itself, so no
count is lost when the days leave the daily index.

**A month's own file, at its path while no entry names it, is adopted first.**
It gives the month its rows and no lost day, so a day file missing beside it is
not lost: its rows are in the month's file. A month whose days still hold files
beside such a file is kept only when the file holds exactly their rows, and
refused otherwise, because nothing is written over a packed file no entry
names.

**The pass writes all month files, then the final monthly and daily indexes
once, then deletes absorbed daily files, then advances the monthly watermark
once, last.** Before the monthly index lands, daily files survive. After it
lands, the next wake keeps the indexed month, removes remaining daily files
by their calendar dates, and advances the watermark without rebuilding.
The daily files are joined as they are and never settled across days: a key
with no date cell may repeat on two days, and both rows are facts. The step
closes only the months whose day files fit what is left of the shard's
download budget, and stops at the first that does not.

**A month file lives exactly `monthly_window` after its month is absorbed.**
Month M goes at the instant month M plus the window becomes absorbable, so the
period holds exactly that many months at every wake and the ledger reaches back
`daily_keep_days` further. `first_kept_month` is the one place that is worked
out; the daily period's first run asks it too, so it never compacts a day the
window would drop at once. A declaration that packs years keeps the window
forever, and its month files leave only by being packed into their year
(`_yearly_period`).

**Each old month is dropped once, and the monthly index says which are left.**
The drop step takes the months chosen for this wake (`_compaction_periods`):
the oldest monthly entries past the keep line, at most `max_periods_per_run`
of them. It names each one's month file and raw folder, deletes every file at
the month's paths whatever its entry says, and then the entry, so no later pass
looks at the month again. It opens nothing. A `packed` entry with no file left
is said once as `file-missing`; an `empty` one has no file to miss.

**A window that only reports names the month files it would drop and keeps
them**, with their index entries, so the record counts what turning it live
would take at that wake while packing goes on. `drop` and `spare` read the same
months.

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
from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
from idhazh.contracts.gardener_events import StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import DaysWindow, ForeverWindow, Window
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.gardener import ledger_marks, named_trees, schedule
from idhazh.gardener.file_listing import OverBudgetError
from idhazh.gardener.tasks._compact_tree import CompactTree, PeriodFetch, Stop

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


def months_to_drop(tree: CompactTree, choice: StepChoice | None) -> list[str]:
    """The months the drop step takes on this wake: each monthly entry inside its choice's span.

    The span counts entries, so a month inside it that the index does not name
    is not one. The pass works this out before the step takes the months out of
    the index, so the raw-day drop is handed the same months.
    """
    if choice is None or choice.first is None or choice.last is None:
        return []
    first, last = choice.first, choice.last
    return [month for month in sorted(tree.monthly) if first <= month <= last]


def _files_at(tree: CompactTree, month: str) -> list[Path]:
    """Every file the listing holds at a month's named paths, in any format."""
    named = (
        ledger.compact_path(tree.state_dir, tree.ledger, Period.MONTHLY, month, fmt=fmt)
        for fmt in Format
    )
    return [path for path in named if tree.listing.holds(path)]


def drop(tree: CompactTree, choice: StepChoice | None) -> tuple[Stop, ...]:
    """Each month chosen past the keep line goes: every file at its paths, then its entry.

    A file at an `empty` entry's path goes too, because nothing looks at the
    month again once its entry has left. A `packed` entry with no file left is
    said once as `file-missing`; an `empty` one has no file to miss.
    """
    months = months_to_drop(tree, choice)
    tree.name_drops(months)
    for month in months:
        found = _files_at(tree, month)
        for path in found:
            tree.delete(path)
        if not found and tree.monthly[month].names_file:
            logger.warning(
                "a month the window drops has no file left to delete ledger=%s month=%s fault=%s",
                tree.ledger.value,
                month,
                ledger.LedgerFault.FILE_MISSING,
            )
        del tree.monthly[month]
    if months:
        tree.mark_index(Period.MONTHLY)
    if (
        choice is not None
        and choice.stopped_because is StopReason.CEILING
        and choice.resume_from is not None
    ):
        return (Stop(StopReason.CEILING, choice.resume_from),)
    return ()


def spare(tree: CompactTree, choice: StepChoice | None) -> tuple[Stop, ...]:
    """Each month chosen past the keep line is named and kept, with every file at its paths.

    A window that only reports takes nothing, so it stops nowhere, and the next
    wake names the same months again.
    """
    months = months_to_drop(tree, choice)
    tree.name_drops(months)
    for month in months:
        for path in _files_at(tree, month):
            tree.spare(path)
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
        tree.note_recovery(RecoveryNote.INDEX_REBUILT, day)
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
    names. With no such file, a day file that cannot be read is moved aside, one
    its entry names that is not there has nothing to move, and either day is
    recorded lost. Nothing is recorded or logged until every refusal is behind
    it, so a month that waits leaves no day half recorded, and a fetch past the
    shard's budget raises `OverBudgetError` before anything is decided.
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
    holes = [day for day in days if day not in tree.daily]
    try:
        adopted = _adopt(tree, holes)
    except ValueError as refusal:
        return _refused(tree, month, str(refusal))
    packed.update((day, held.path) for day, held in adopted.items())
    gone = [day for day in holes if day not in adopted]
    lost = [
        day
        for day in days
        if (entry := tree.daily.get(day)) is not None and entry.state is EntryState.LOST
    ]
    set_aside = sum(entry.set_aside for day in days if (entry := tree.daily.get(day)) is not None)
    if own is not None:
        return _keep_own(
            tree,
            month,
            own,
            [packed[day] for day in sorted(packed)],
            adopted,
            gone=gone,
            lost=sorted({*lost, *gone}),
            set_aside=set_aside,
            model=model,
        )
    rows: list[ledger.StoredRow[C]] = []
    unreadable: dict[str, str] = {}
    for day in sorted(packed):
        try:
            rows.extend(tree.load(packed[day], model=model))
        except ValueError as refusal:
            unreadable[day] = str(refusal)
    _keep(tree, {day: held for day, held in adopted.items() if day not in unreadable})
    for day in sorted(unreadable):
        tree.set_aside(packed[day], day, unreadable[day])
        tree.note_recovery(RecoveryNote.SET_ASIDE, day)
    for day in sorted({*gone, *absent, *unreadable}):
        tree.note_recovery(RecoveryNote.RECORDED_LOST, day)
    lost_days = sorted({*lost, *gone, *absent, *unreadable})
    set_aside += len(unreadable)
    sources = [packed[day] for day in sorted(packed) if day not in unreadable]
    if rows:
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
            covers=month,
            rows=len(rows),
            bytes=len(built.data),
            lost_days=lost_days,
            set_aside=set_aside,
        )
    else:
        tree.monthly[month] = CompactEntry(
            covers=month,
            rows=0,
            bytes=0,
            state=EntryState.EMPTY,
            lost_days=lost_days,
            set_aside=set_aside,
        )
    tree.mark_index(Period.MONTHLY)
    for path in sources:
        tree.delete(path)
    _forget_days(tree, month)
    return ()


def _keep_own[C: Contract](
    tree: CompactTree,
    month: str,
    own: ledger_marks.Adopted,
    sources: list[Path],
    adopted: dict[str, ledger_marks.Adopted],
    *,
    gone: list[str],
    lost: list[str],
    set_aside: int,
    model: type[C],
) -> tuple[Stop, ...]:
    """Close a month from its own file, which no entry names, or refuse it when its days differ.

    A day whose file its entry names and the tree lacks is not lost here: its
    rows are in the month's file, or the file proves it had none, and the
    compare decides the rest. The month's days hold `set_aside` files moved
    aside before, and its entry keeps the count.
    """
    if not sources:
        tree.monthly[month] = own.entry.model_copy(update={"set_aside": set_aside})
    else:
        try:
            rows = [row for path in sources for row in tree.load(path, model=model)]
            if tree.load(own.path, model=model) != rows:
                return _refused(
                    tree,
                    month,
                    f"{own.path.name} is at its path, no monthly entry names it, and it holds "
                    "other rows than its days. Nothing is written over a packed file no entry "
                    "names, so the month waits",
                )
        except ValueError as refusal:
            return _refused(tree, month, str(refusal))
        _keep(tree, adopted)
        for day in gone:
            tree.note_recovery(RecoveryNote.RECORDED_LOST, day)
        tree.monthly[month] = own.entry.model_copy(
            update={"lost_days": lost, "set_aside": set_aside}
        )
    tree.mark_index(Period.MONTHLY)
    tree.note_recovery(RecoveryNote.INDEX_REBUILT, month)
    for path in sources:
        tree.delete(path)
    _forget_days(tree, month)
    return ()


def _fetched(tree: CompactTree, month: str) -> PeriodFetch:
    """What closing one month downloads: its day files, and the month files beside its own.

    An indexed month is finished by its names and downloads nothing.
    """
    if month in tree.monthly:
        return PeriodFetch()
    own = named_trees.compact_file(
        tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
    )
    return PeriodFetch(
        folders=(tree.daily_month_folder(month),), beside=() if own is None else (own,)
    )


def absorb(
    tree: CompactTree, choice: StepChoice, *, stamp: str, identity: WriterIdentity
) -> tuple[Stop, ...]:
    """Close the months chosen for this wake, oldest first, stopping at the first one held.

    A choice an operator range refused stops here, at the month the range left
    out, with nothing taken. The step closes only the months whose files fit
    what is left of the shard's download budget, and stops at the first that
    does not.
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
    fits, over = tree.fit_to_budget(closing, lambda month: _fetched(tree, month))
    tree.fetch(_fetched(tree, month) for month in fits)
    model = ledger.door_contract(tree.ledger)
    for position, month in enumerate(months):
        try:
            if month not in closing:
                return _hold(tree, month)
            if over is not None and position == len(fits):
                return (over,)
            if month in tree.monthly:
                stops = _finish(tree, month)
            else:
                stops = _close(tree, month, model=model, identity=identity)
        except OverBudgetError as spent:
            return (tree.stop_spent(month, spent),)
        if stops:
            return stops
        tree.monthly_through = max(month, tree.monthly_through or month)
        tree.write_watermark(
            Period.MONTHLY, through=tree.monthly_through, advanced_at=stamp, run_id=identity.run_id
        )
    if choice.stopped_because is StopReason.CEILING and choice.resume_from is not None:
        return (Stop(StopReason.CEILING, choice.resume_from),)
    return ()
