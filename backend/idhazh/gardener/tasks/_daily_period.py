"""Which raw days one ledger's compaction takes into daily files, and which raw files it drops.

**The new days are the ones chosen for this wake** (`_compaction_periods`):
the days after the daily mark, each `compact_after_days` whole days past its
end, at most `max_periods_per_run` of them, or with no mark the days from where
a first run starts. The step names what it reads of them - each day's raw
folder and its day file, whichever format wrote it - and the same of the packed
days a GitHub re-run may still write into. Then it works oldest first, against
the one cap: first each closed month a raw file landed in, which it re-opens,
then each packed day that holds raw files again, then the new days, each day on
its own.

**A packed day that holds raw files again is taken again.** A GitHub re-run
writes into the day its run first wrote, for up to thirty days, which is why
the step names those days. A raw day at or below the mark in a month not yet
closed is taken again however old it is: the month step holds such a month
until the day is packed, so leaving it would hold the month for ever. The day
is rebuilt from its own file and the new raw files together, settled once -
one file's rows per work unit, the last of its highest attempt, then the first
row per key - so a re-run replaces its first attempt even when it filed fewer
rows. A day recorded `empty` or `lost` has no file, so it is rebuilt from its
raw files alone. The mark stays where it is.
**A day whose entry says `packed` while its file is not there is refused**, as
`file-missing`, and its raw files are kept: rebuilt from the re-run's files
alone it would hold only the shards that ran again, and its index entry would
call that smaller day complete. So is a day whose packed file cannot be read.
Either way a person restores the file from git history, and the pass ends
`deferred` with the fault `packed-file-unreadable` rather than turning the job
red.

**A raw day in a month the monthly index names landed after its month closed,
and the month re-opens** (`_reopened_month`): the month's rows and the late
rows are settled the way a day taken again is. It counts once against the cap.
One in a month past the keep line is the drop steps' instead (below). A raw day
in a month the monthly mark is past that no monthly entry names is refused by
name and kept, for a person: that month never closed, was dropped, or sits in a
packed year, so there is no month to re-open. The pass ends `deferred` with the
fault `no-month-to-reopen`.

**A day with no row is an entry `empty` with no file.** The entry keeps the
newest day the daily index names equal to the mark, so a reader tells a quiet
day from a hole without a file to open, and the next pass works the mark out
from the index again. **A day no entry names that has a file
at its path is adopted first** (`ledger_marks.adopt`): an index restored from
an older commit can lose a day whose file is still there, and recording the
day empty, or writing over the file, would lose its rows. **A day at or below
the mark that no entry names, with raw files and no file to adopt, is a hole
in the ledger's history, and it is packed again from its raw files**, noted
`repacked-from-raw`.

**A file that cannot be read is moved aside, and the rest of its day packs.**
Its envelope or a row this build refuses moves it to the ledger's set-aside
folder, under its path (`CompactTree.set_aside`), and the day's entry counts it
in `set_aside`; a day taken again keeps the count it had and adds to it. **A
day holding more than `max_raw_files_per_period` readable files packs its
oldest that many**, and the rest stay in its folder: the mark moves past the
day, the pass ends `ceiling` at it, and the next wake takes the rest in as it
takes a re-run. Nothing is decided for a day that is refused, so a refused day
keeps every file. The pass writes its final daily index once, then deletes raw
files, so before the index lands raw files survive. The daily mark is the
newest day the indexes name, so a raw file left after the index landed sits in
a day at or below the mark, and the next wake takes that day again.

**The step takes only the days whose fetch fits the shard's download budget**,
oldest first, read off the listing's sizes before anything is downloaded. The
first day that does not fit ends the step at `ceiling`, for a later wake, or
`failed` by name when that day alone is larger than the whole budget.

**Raw days past the keep line are past the ledger's reach**, and are dropped
by their listed paths: those in the months the drop step takes, and those a
first run looked back over and did not take. Nothing of them is fetched or
opened, so a file that cannot be read goes with its day. A window that only
reports keeps them instead and names their files for the record. The step takes
such a day like any other while its month is open, as a first run that starts
before the line does. In a month already closed it leaves the day alone, live
or not: the drop steps own it, and a re-open would write a month file the
window deletes.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason, stop_for
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import StepChoice
from idhazh.contracts.gardener_fault import GardenerFault, RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.gardener import ledger_marks, named_trees
from idhazh.gardener.file_listing import OverBudgetError
from idhazh.gardener.tasks import _reopened_month
from idhazh.gardener.tasks._compact_tree import CompactTree, PeriodFetch, Stop

logger = logging.getLogger(__name__)


def _past_the_line(
    tree: CompactTree, months: Sequence[str], *, first_kept: str | None
) -> list[tuple[str, list[Path]]]:
    """Every raw day past the keep line in these months, beside every file the listing holds in it.

    Read off the listing alone, so nothing is fetched or opened, and a file that
    cannot be read is named with the rest of its day.
    """
    if first_kept is None:
        return []
    named = set(months)
    root = tree.listing.repo_root
    return [
        (day, [root / path for path in tree.listing.files_under(tree.raw_day_folder(day))])
        for day in tree.raw_days
        if day[:7] in named and day[:7] < first_kept
    ]


def drop(tree: CompactTree, months: Sequence[str], *, first_kept: str | None) -> tuple[Stop, ...]:
    """Raw days past the keep line in these months go, each with every file it holds, unread.

    `months` are those the drop step takes and those a first run looked back
    over, so what goes does not depend on how much else the listing names.
    """
    gone = _past_the_line(tree, months, first_kept=first_kept)
    for _day, files in gone:
        for path in files:
            tree.delete(path)
    dropped = {day for day, _files in gone}
    tree.raw_days = [day for day in tree.raw_days if day not in dropped]
    return ()


def spare(tree: CompactTree, months: Sequence[str], *, first_kept: str | None) -> tuple[Stop, ...]:
    """Every raw file a live drop would take is named and kept, for `compact` in an open month."""
    for _day, files in _past_the_line(tree, months, first_kept=first_kept):
        for path in files:
            tree.spare(path)
    return ()


def _days_from(first: str, last: str) -> list[str]:
    """Every UTC day from `first` to `last`, both named."""
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


def _refused(
    tree: CompactTree,
    day: str,
    why: str,
    ledger_fault: ledger.LedgerFault | None = None,
    *,
    fault: GardenerFault = GardenerFault.RAISED,
) -> Stop:
    """A raw day the step does not take, said once by name. Its files are kept.

    `fault` is the record's word for it: `raised`, a defect, unless the caller
    names a cause outside the code, which defers the pass instead.
    """
    logger.error(
        "a raw day is not compacted, and its files are kept ledger=%s day=%s fault=%s reason=%s",
        tree.ledger.value,
        day,
        ledger_fault or "none",
        why,
    )
    return Stop(stop_for(fault), day, fault)


def _take[C: Contract](
    tree: CompactTree,
    policy: CompactionPolicy,
    day: str,
    *,
    model: type[C],
    key: tuple[str, ...],
    identity: WriterIdentity,
) -> Stop | None:
    """Pack one day; None when it is packed whole.

    A `ceiling` stop at the day when it is packed from its oldest files and the
    rest wait in its folder for the next wake. A `failed` or `deferred` stop
    when the day is refused: nothing is decided for it, and the refusal is all
    that is said of it. A fetch past the shard's budget raises
    `OverBudgetError`, with nothing decided either. A day at or below the mark
    that no entry names, packed from raw files with no file of its own to
    adopt, is a hole in the ledger's history filled again: `repacked-from-raw`.
    """
    history = tree.daily_through is not None and day <= tree.daily_through
    try:
        raw = tree.read_raw_day(day, most=policy.max_raw_files_per_period, model=model)
    except ValueError as refusal:
        return _refused(tree, day, str(refusal))
    entry = tree.daily.get(day)
    adopted: ledger_marks.Adopted | None = None
    if entry is not None and entry.names_file:
        existing = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
        )
        if existing is None:
            where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.DAILY)
            return _refused(
                tree,
                day,
                f"{where.name} names the day and its file is not there. Restore the file from "
                "git history, and the next wake takes the re-run in",
                ledger.LedgerFault.FILE_MISSING,
                fault=GardenerFault.PACKED_FILE_UNREADABLE,
            )
    else:
        try:
            adopted = ledger_marks.adopt(
                tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
            )
        except ValueError as refusal:
            return _refused(tree, day, str(refusal))
        existing = None if adopted is None else adopted.path
    try:
        kept = [tree.load(existing, model=model)] if existing is not None and raw.taken else []
    except ValueError as refusal:
        return _refused(tree, day, str(refusal), fault=GardenerFault.PACKED_FILE_UNREADABLE)
    for path, why in raw.unreadable:
        tree.set_aside(path, day, why)
    set_aside = (0 if entry is None else entry.set_aside) + len(raw.unreadable)
    if raw.taken:
        _record(
            tree,
            day,
            ledger.settle_rows([*kept, *(rows for _path, rows in raw.taken)], key),
            existing,
            model=model,
            identity=identity,
            built_from=len(raw.taken) + (existing is not None),
            set_aside=set_aside,
        )
        for path, _rows in raw.taken:
            tree.delete(path)
    elif adopted is not None:
        tree.daily[day] = adopted.entry.model_copy(update={"set_aside": set_aside})
    elif entry is not None:
        tree.daily[day] = entry.model_copy(update={"set_aside": set_aside})
    else:
        tree.daily[day] = CompactEntry(
            covers=day, rows=0, bytes=0, state=EntryState.EMPTY, set_aside=set_aside
        )
    if raw.unreadable:
        tree.note_recovery(RecoveryNote.SET_ASIDE, day)
    if adopted is not None:
        tree.note_recovery(RecoveryNote.INDEX_REBUILT, day)
    elif history and entry is None and raw.taken:
        tree.note_recovery(RecoveryNote.REPACKED_FROM_RAW, day)
    tree.mark_index(Period.DAILY)
    _advance(tree, day)
    if raw.carried:
        tree.note_recovery(RecoveryNote.CARRIED_OVER, day)
        logger.info(
            "a day's newest raw files wait for the next wake ledger=%s day=%s waiting=%s most=%s",
            tree.ledger.value,
            day,
            raw.carried,
            policy.max_raw_files_per_period,
        )
        return Stop(StopReason.CEILING, day)
    return None


def _advance(tree: CompactTree, day: str) -> None:
    """Move the daily mark to a day the step has finished, when the day is past it."""
    if tree.daily_through is None or day > tree.daily_through:
        tree.daily_through = day


def _record[C: Contract](
    tree: CompactTree,
    day: str,
    settled: list[ledger.StoredRow[C]],
    existing: Path | None,
    *,
    model: type[C],
    identity: WriterIdentity,
    built_from: int,
    set_aside: int,
) -> None:
    """Write one day's settled rows into its day file, or record a day with no row as `empty`.

    A day with no row gets no file, so any file at its path goes with it.
    `set_aside` is every file the day's packing has moved aside, this pass's
    and those its entry counted before.
    """
    if not settled:
        if existing is not None:
            tree.delete(existing)
        tree.daily[day] = CompactEntry(
            covers=day, rows=0, bytes=0, state=EntryState.EMPTY, set_aside=set_aside
        )
        return
    built = ledger.render_period(
        tree.state_dir,
        settled,
        model=model,
        ledger=tree.ledger,
        period=Period.DAILY,
        covers=day,
        identity=identity,
        built_from=built_from,
    )
    if existing is not None and existing != built.path:
        tree.delete(existing)
    tree.write(built.path, built.data)
    tree.daily[day] = CompactEntry(
        covers=day, rows=len(settled), bytes=len(built.data), set_aside=set_aside
    )


def _fetched(tree: CompactTree, day: str) -> PeriodFetch:
    """What packing one day downloads: its raw folder, and its month's day files beside its own.

    The day's own file is read when the day is taken again, or adopted when no
    entry names it, and a day file comes with the files beside it.
    """
    own = named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day)
    return PeriodFetch(
        folders=(
            tree.raw_day_folder(day),
            *(() if own is None else (tree.daily_month_folder(day[:7]),)),
        )
    )


def compact(
    tree: CompactTree,
    policy: CompactionPolicy,
    choice: StepChoice,
    *,
    rerun_span: tuple[str, str] | None,
    first_kept: str | None,
    identity: WriterIdentity,
) -> tuple[Stop, ...]:
    """Re-open each closed month raw files landed in, then take days again and new days, to the cap.

    `first_kept` is the keep line, the oldest month the monthly window keeps,
    or None when it keeps every month. A re-opened month counts once against
    the cap, as a day does. A choice an operator range refused stops here,
    deferred at the day the range left out, with nothing taken. The step takes
    only the days whose fetch fits what is left of the shard's download budget,
    and stops at the first that does not. A day refused for a fault holds the
    mark below it, whether the fault fails the pass or defers it.
    """
    if choice.stopped_because is StopReason.DEFERRED and choice.resume_from is not None:
        return (
            _refused(
                tree,
                choice.resume_from,
                "the operator range leaves it out, and it is due before any day the range "
                "names. Widen the range to include it",
                fault=GardenerFault.RANGE_STARTS_LATE,
            ),
        )
    new = (
        [] if choice.first is None or choice.last is None else _days_from(choice.first, choice.last)
    )
    tree.name_days([*(_days_from(*rerun_span) if rerun_span is not None else []), *new])
    model, key = ledger.door_contract(tree.ledger), ledger.door_key(tree.ledger)
    stops: list[Stop] = []
    closed: list[str] = []
    again: list[str] = []
    for day in tree.raw_days:
        if tree.daily_through is None or day > tree.daily_through:
            continue
        month = day[:7]
        if month in tree.monthly and month[:4] not in tree.yearly:
            # A closed month past the keep line is the drop steps', live or only reported.
            if (first_kept is None or month >= first_kept) and month not in closed:
                closed.append(month)
        elif tree.monthly_through is not None and month <= tree.monthly_through:
            stops.append(
                _refused(
                    tree,
                    day,
                    "no monthly entry names its month and the monthly mark is past it: the "
                    "month never closed, was dropped, or sits in a packed year, so there is "
                    "no month to re-open",
                    fault=GardenerFault.NO_MONTH_TO_REOPEN,
                )
            )
        else:
            again.append(day)
    taken = 0
    for month in closed:
        if taken == policy.max_periods_per_run:
            return (*stops, Stop(StopReason.CEILING, month))
        try:
            reopened = _reopened_month.reopen(
                tree,
                month,
                most=policy.max_raw_files_per_period,
                model=model,
                key=key,
                identity=identity,
            )
        except OverBudgetError as spent:
            return (*stops, tree.stop_spent(month, spent))
        stops.extend(reopened)
        if not any(stop.fault is not None for stop in reopened):
            taken += 1
    days = again + new
    # Every day the cap and the budget can reach, fetched in one call before the
    # first is read: a day that fails costs nothing, so the ones waiting again may
    # all fail first.
    reached = days[: len(again) + policy.max_periods_per_run - taken]
    fits, over = tree.fit_to_budget(reached, lambda day: _fetched(tree, day))
    tree.fetch(_fetched(tree, day) for day in fits)
    for position, day in enumerate(days):
        if taken == policy.max_periods_per_run:
            stops.append(Stop(StopReason.CEILING, day))
            break
        if over is not None and position == len(fits):
            stops.append(over)
            break
        fresh = tree.daily_through is None or day > tree.daily_through
        try:
            stop = _take(tree, policy, day, model=model, key=key, identity=identity)
        except OverBudgetError as spent:
            stops.append(tree.stop_spent(day, spent))
            break
        if stop is not None and stop.fault is not None:
            stops.append(stop)
            if fresh:
                break
            continue
        if stop is not None:
            stops.append(stop)
        taken += 1
    else:
        if choice.stopped_because is StopReason.CEILING and choice.resume_from is not None:
            stops.append(Stop(StopReason.CEILING, choice.resume_from))
    return tuple(stops)
