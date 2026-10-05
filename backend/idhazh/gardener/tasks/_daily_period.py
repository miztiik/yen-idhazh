"""Which raw days one ledger's compaction takes into daily files, and which raw files it drops.

**The new days are the ones chosen for this wake** (`_compaction_periods`):
the days after the daily mark, each `compact_after_days` whole days past its
end, at most `max_periods_per_run` of them, or with no mark the days from where
a first run starts. The step names what it reads of them - each day's raw
folder and its day file, whichever format wrote it - and the same of the packed
days a GitHub re-run may still write into. Then it takes days in order, each on
its own: first each packed day that holds raw files again, then the new days,
all against the one cap. A new day the index already names and no raw file
holds keeps its entry as it is, and the mark moves past it.

**A packed day that holds raw files again is taken again.** A GitHub re-run
writes into the day its run first wrote, for up to thirty days, which is why
the step names those days. A raw day at or below the mark in a month not yet
closed is taken again however old it is: the month step holds such a month
until the day is packed, so leaving it would hold the month for ever. The day
is rebuilt from its own file and the new raw files together, settled once -
one file's rows per work unit, the last of its highest attempt, then the first
row per key - so a re-run replaces its first attempt even when it filed fewer
rows. A day recorded `empty` or `lost` has no file, so it is rebuilt from its
raw files alone. The mark stays where it is. Raw files in a month already
absorbed are refused by name and kept: `daily_keep_days` outlasts GitHub's
re-run window, so no re-run can land there and a person decides what they are.
**A day whose entry says `packed` while its file is not there is refused**, as
`file-missing`, and its raw files are kept: rebuilt from the re-run's files
alone it would hold only the shards that ran again, and its index entry would
call that smaller day complete.

**A day with no row is an entry `empty` with no file.** The entry keeps the
newest day the daily index names equal to the mark, so a reader tells a quiet
day from a hole without a file to open. **A day no entry names that has a file
at its path is adopted first** (`ledger_marks.adopt`): an index restored from
an older commit can lose a day whose file is still there, and recording the
day empty, or writing over the file, would lose its rows.

**A file that cannot be read stops its day and is never deleted**; a day
holding more than `max_raw_files_per_period` files is refused the same way.
Either one leaves the mark before that day, so the next wake retries it rather
than stepping past it. The pass writes its final daily index once, then deletes
raw files, and advances its watermark once, last. Before the index lands, raw
files survive; after it lands, the next wake moves the mark past each indexed
day no raw file is left in, and takes again a day whose raw files remain.

**Raw days past the keep line are past the ledger's reach**, and are dropped
by their listed paths: those in the months the drop step takes, and those a
first run looked back over and did not take. Nothing of them is fetched or
opened, so a file that cannot be read goes with its day. A window that only
reports keeps them instead: it names their files for the record, and the step
takes those days like any other.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.gardener import ledger_marks, named_trees
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop

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
    """Every raw file a live drop would take is named and kept, for `compact` to take."""
    for _day, files in _past_the_line(tree, months, first_kept=first_kept):
        for path in files:
            tree.spare(path)
    return ()


def _days_from(first: str, last: str) -> list[str]:
    """Every UTC day from `first` to `last`, both named."""
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=step)).isoformat() for step in range((end - start).days + 1)]


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
    """Pack one day, or say why it cannot be and which fault that is, if any.

    Nothing is decided for a day that fails, and nothing is said of it.
    """
    try:
        files = tree.raw_files(day, most=policy.max_raw_files_per_period)
    except ValueError as refusal:
        return str(refusal), None
    entry = tree.daily.get(day)
    if entry is not None and not files:
        _advance(tree, day, stamp=stamp, identity=identity)
        return None
    adopted: ledger_marks.Adopted | None = None
    if entry is not None and entry.names_file:
        existing = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
        )
        if existing is None:
            where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.DAILY)
            return (
                f"{where.name} names the day and its file is not there. Restore the file from "
                "git history, and the next wake takes the re-run in",
                ledger.LedgerFault.FILE_MISSING,
            )
    else:
        try:
            adopted = ledger_marks.adopt(
                tree.listing, tree.state_dir, tree.ledger, Period.DAILY, day
            )
        except ValueError as refusal:
            return str(refusal), None
        existing = None if adopted is None else adopted.path
    if adopted is not None and not files:
        tree.daily[day] = adopted.entry
    else:
        try:
            rows = [tree.load(existing, model=model)] if existing is not None else []
            for held in files:
                rows.append(tree.load(held.path, model=model))
        except ValueError as refusal:
            return str(refusal), None
        _record(
            tree,
            day,
            ledger.settle_rows(rows, key),
            existing,
            model=model,
            identity=identity,
            built_from=len(files) + (existing is not None),
        )
        for held in files:
            tree.delete(held.path)
    if adopted is not None:
        tree.note_recovery(RecoveryNote.INDEX_REBUILT, day)
    tree.mark_index(Period.DAILY)
    _advance(tree, day, stamp=stamp, identity=identity)
    return None


def _advance(tree: CompactTree, day: str, *, stamp: str, identity: WriterIdentity) -> None:
    """Move the daily mark to a day the step has finished, when the day is past it."""
    if tree.daily_through is None or day > tree.daily_through:
        tree.daily_through = day
        tree.write_watermark(Period.DAILY, through=day, advanced_at=stamp, run_id=identity.run_id)


def _record[C: Contract](
    tree: CompactTree,
    day: str,
    settled: list[ledger.StoredRow[C]],
    existing: Path | None,
    *,
    model: type[C],
    identity: WriterIdentity,
    built_from: int,
) -> None:
    """Write one day's settled rows into its day file, or record a day with no row as `empty`.

    A day with no row gets no file, so any file at its path goes with it.
    """
    if not settled:
        if existing is not None:
            tree.delete(existing)
        tree.daily[day] = CompactEntry(covers=day, rows=0, bytes=0, state=EntryState.EMPTY)
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
    tree.daily[day] = CompactEntry(covers=day, rows=len(settled), bytes=len(built.data))


def compact(
    tree: CompactTree,
    policy: CompactionPolicy,
    choice: StepChoice,
    *,
    rerun_span: tuple[str, str] | None,
    stamp: str,
    identity: WriterIdentity,
) -> tuple[Stop, ...]:
    """Take again each packed day that holds raw files, then the new days, oldest first, to the cap.

    A choice an operator range refused stops here, at the day the range left
    out, with nothing taken.
    """
    if choice.stopped_because is StopReason.FAILED and choice.resume_from is not None:
        logger.error(
            "a raw day is not compacted, and its files are kept "
            "ledger=%s day=%s fault=%s reason=%s",
            tree.ledger.value,
            choice.resume_from,
            "none",
            "the operator range leaves it out, and it is due before any day the range names. "
            "Widen the range to include it",
        )
        return (Stop(StopReason.FAILED, choice.resume_from),)
    new = (
        [] if choice.first is None or choice.last is None else _days_from(choice.first, choice.last)
    )
    tree.name_days([*(_days_from(*rerun_span) if rerun_span is not None else []), *new])
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
    days = again + new
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
    else:
        if choice.stopped_because is StopReason.CEILING and choice.resume_from is not None:
            stops.append(Stop(StopReason.CEILING, choice.resume_from))
    return tuple(stops)
