"""Which years one ledger's compaction packs into year files, and what each year file holds.

**The years are the ones chosen for this wake** (`_compaction_periods`):
consecutive years after the yearly mark, each at least `monthly_keep_days`
whole days past its end and each whose December the monthly mark is strictly
past. Only a declaration that sets `monthly_keep_days` packs years; every other
ledger keeps its month files as `monthly_window` says. The step names what it
reads of its years, then packs them oldest first, each whole or not at all.

**A year's own file, at its path while no entry names it, is the year's record
(`index-rebuilt`), and the step looks for it first.** A shard lands a year file
only in the commit that also indexes it and deletes its months, and a month
inside a packed year never changes again, so such a file - left by an index
restored from an older commit - holds exactly its months' rows. Its months'
lost days and set-aside counts carry onto its entry, and their files go by
their names, unread.

**Otherwise a year accounts for every month from January, or from the ledger's
first month when the ledger began inside it.** A month with a `packed` entry
gives its file's rows; an `empty` month gives none. Every month's `lost_days`
and `set_aside` carry into the year's entry. A year whose months give no row is
an `empty` entry with no file, its lost days listed on it. A month no entry
names adopts its own file when one is at its path. With none, when nothing of
the month is left - no day file, no raw file, no daily entry - every day of it
is recorded lost (`recorded-lost`); while something is left, the month never
closed, so the year is refused by name as `day-missing` and the task exits 1,
because recording those days lost would hide rows that are still there. A month
file that cannot be read is moved to the ledger's set-aside folder
(`set-aside`), and one its entry names that the tree lacks has nothing to move;
either way nothing else says which of its days held rows, so every day of the
month is recorded lost, and the year packs from the rest.

**The pass writes all year files, then the final yearly and monthly indexes
once, then deletes absorbed month files, then advances the yearly watermark
once, last.** A pass that stops before the yearly index leaves every
month file in place, so the next wake packs that year again from them. A pass
that stops after it leaves a year the yearly index already names, so the next
wake finishes it instead: it finds remaining month files by calendar month,
deletes them, rewrites the monthly index and moves the watermark, and builds
nothing; an `empty` year has no file of its own to look for. Either way no row
is lost, and none is read twice, because a reader reads a month both indexes
name from its year. The month files are joined as they are and never settled,
because each already holds one row per record; the monthly watermark is left
alone.

**A year file is built one month at a time**, one parquet row group per month
that holds a row, so the pass holds one month's rows at once and a reader that
filters on a date can skip the other months. A month file found unreadable
while the year is built leaves the build to be made again from the rest, which
only a year that sets a file aside pays for. A year file over GitHub's
large-file line is refused by name and its month files are kept, because a file
over twice that line would make every later push fail.

**The step packs only the years whose files fit what is left of the shard's
download budget**, read off the listing's sizes before anything is downloaded,
and stops at the first that does not.

Year files are kept for ever. Every year here is a UTC year (CLAUDE.md
section 2).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import GITHUB_LARGE_FILE_BYTES
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.gardener import ledger_marks, named_trees
from idhazh.gardener.file_listing import OverBudgetError
from idhazh.gardener.tasks._compact_tree import CompactTree, PeriodFetch, Stop
from idhazh.gardener.tasks._monthly_period import days_of
from idhazh.ledger import StoredRow

logger = logging.getLogger(__name__)


def months_of(year: str) -> list[str]:
    """Every UTC month of a `YYYY` year, January to December."""
    return [f"{year}-{number:02d}" for number in range(1, 13)]


def _counted(tree: CompactTree, year: str) -> list[str]:
    """The months of a year its record accounts for: every one, or those from the ledger's first.

    The ledger began inside the year when no year is packed or marked and the
    oldest month its monthly index names falls in it.
    """
    months = months_of(year)
    if tree.yearly or tree.yearly_through or not tree.monthly:
        return months
    first = min(tree.monthly)
    return [month for month in months if month >= first]


def _refused(
    tree: CompactTree, year: str, why: str, fault: ledger.LedgerFault | None = None
) -> tuple[Stop, ...]:
    """A year that cannot be packed, said once by name. The watermark stays where it is."""
    logger.error(
        "a year is not packed ledger=%s year=%s fault=%s reason=%s",
        tree.ledger.value,
        year,
        fault or "none",
        why,
    )
    return (Stop(StopReason.FAILED, year),)


def _drop_months(tree: CompactTree, year: str) -> None:
    """Take every month of a packed year out of the monthly index, and delete its files by name."""
    for month in months_of(year):
        found = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
        )
        if found is not None:
            tree.delete(found)
        tree.monthly.pop(month, None)
    tree.mark_index(Period.MONTHLY)


def _keep_own(tree: CompactTree, year: str, own: ledger_marks.Adopted) -> None:
    """Index a year's own file, which no entry named, as the year, and let its months go.

    Its months' lost days and set-aside counts carry onto its entry, and their
    files go by their names, so none of them is downloaded.
    """
    held = [tree.monthly[month] for month in months_of(year) if month in tree.monthly]
    tree.yearly[year] = own.entry.model_copy(
        update={
            "lost_days": sorted({day for entry in held for day in entry.lost_days}),
            "set_aside": sum(entry.set_aside for entry in held),
        }
    )
    tree.note_recovery(RecoveryNote.INDEX_REBUILT, year)
    tree.mark_index(Period.YEARLY)
    _drop_months(tree, year)


def _left_of(tree: CompactTree, months: Sequence[str]) -> list[str]:
    """Which of these months, which no entry or own file names, still hold something of their days.

    Their daily and raw folders are listed in one call, and nothing is
    downloaded; a daily entry for one of their days counts too. Such a month
    never closed, so its days are not lost.
    """
    if not months:
        return []
    tree.name_months(months)
    return [
        month
        for month in months
        if tree.listing.files_under(tree.daily_month_folder(month))
        or tree.listing.files_under(tree.raw_month_folder(month))
        or any(day.startswith(f"{month}-") for day in tree.daily)
    ]


def _build[C: Contract](
    tree: CompactTree,
    year: str,
    held: dict[str, Path],
    *,
    model: type[C],
    identity: WriterIdentity,
) -> tuple[ledger.PeriodFile | None, dict[str, str]]:
    """The year's file from its months' files, one month at a time, and each one it could not read.

    A month file that cannot be read is passed over, and the build is made
    again from the rest, so the file says how many files it was built from.
    None when no month file is left to build from. Raises `ValueError` for a
    year file over GitHub's large-file line, before anything is written.
    """
    unreadable: dict[str, str] = {}

    def groups(months: Sequence[str]) -> Iterator[list[StoredRow[C]]]:
        for month in months:
            try:
                rows = tree.load(held[month], model=model)
            except ValueError as refusal:
                unreadable[month] = str(refusal)
                continue
            yield rows

    def render(months: Sequence[str]) -> ledger.PeriodFile | None:
        if not months:
            return None
        return ledger.render_grouped_period(
            tree.state_dir,
            groups(months),
            model=model,
            ledger=tree.ledger,
            period=Period.YEARLY,
            covers=year,
            identity=identity,
            built_from=len(months),
        )

    built = render(sorted(held))
    if unreadable:
        built = render([month for month in sorted(held) if month not in unreadable])
    if built is not None and len(built.data) > GITHUB_LARGE_FILE_BYTES:
        raise ValueError(
            f"its file would be {len(built.data)} bytes, over GitHub's large-file line of "
            f"{GITHUB_LARGE_FILE_BYTES}, so its month files are kept"
        )
    return built, unreadable


def _pack(tree: CompactTree, year: str, *, identity: WriterIdentity) -> tuple[Stop, ...]:
    """Pack one year no entry names yet: from its own file when one is there, else its months.

    Nothing is decided until every refusal is behind it, and a fetch past the
    shard's budget raises `OverBudgetError` before anything is decided.
    """
    try:
        own = ledger_marks.adopt(tree.listing, tree.state_dir, tree.ledger, Period.YEARLY, year)
    except ValueError as refusal:
        return _refused(tree, year, str(refusal))
    if own is not None:
        _keep_own(tree, year, own)
        return ()
    months = _counted(tree, year)
    recovered: dict[str, ledger_marks.Adopted] = {}
    try:
        for month in months:
            if month in tree.monthly:
                continue
            found = ledger_marks.adopt(
                tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
            )
            if found is not None:
                recovered[month] = found
    except ValueError as refusal:
        return _refused(tree, year, str(refusal))
    nowhere = [month for month in months if month not in tree.monthly and month not in recovered]
    left = _left_of(tree, nowhere)
    if left:
        where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.MONTHLY)
        return _refused(
            tree,
            year,
            f"{where.name} does not name {', '.join(left)}, and its days are still there, "
            "so it never closed",
            ledger.LedgerFault.DAY_MISSING,
        )
    files = {
        month: named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
        )
        for month in months
        if month in tree.monthly and tree.monthly[month].names_file
    }
    absent = [month for month, found in files.items() if found is None]
    held = {month: found for month, found in files.items() if found is not None}
    held.update((month, adopted.path) for month, adopted in recovered.items())
    try:
        built, unreadable = _build(
            tree, year, held, model=ledger.door_contract(tree.ledger), identity=identity
        )
    except ValueError as refusal:
        return _refused(tree, year, str(refusal))
    for month in sorted(unreadable):
        tree.set_aside(held[month], month, unreadable[month])
        tree.note_recovery(RecoveryNote.SET_ASIDE, month)
    for month in sorted(recovered):
        if month not in unreadable:
            tree.note_recovery(RecoveryNote.INDEX_REBUILT, month)
    gone = sorted({*nowhere, *absent, *unreadable})
    for month in gone:
        tree.note_recovery(RecoveryNote.RECORDED_LOST, month)
    entries = [tree.monthly[month] for month in months if month in tree.monthly]
    lost = sorted(
        {
            *(day for entry in entries for day in entry.lost_days),
            *(day for month in gone for day in days_of(month)),
        }
    )
    set_aside = sum(entry.set_aside for entry in entries) + len(unreadable)
    if built is None:
        tree.yearly[year] = CompactEntry(
            covers=year,
            rows=0,
            bytes=0,
            state=EntryState.EMPTY,
            lost_days=lost,
            set_aside=set_aside,
        )
    else:
        tree.write(built.path, built.data)
        tree.yearly[year] = CompactEntry(
            covers=year,
            rows=built.rows,
            bytes=len(built.data),
            lost_days=lost,
            set_aside=set_aside,
        )
    tree.mark_index(Period.YEARLY)
    for month in sorted(held):
        if month not in unreadable:
            tree.delete(held[month])
    for month in months:
        tree.monthly.pop(month, None)
    tree.mark_index(Period.MONTHLY)
    return ()


def _finish(tree: CompactTree, year: str) -> tuple[Stop, ...]:
    """Finish a year the yearly index already names: its entry stands, its month files go.

    An `empty` year has no file of its own to look for, and a `packed` one whose
    file is not there is refused as `file-missing`. The month files go by their
    names, so none of them is downloaded.
    """
    if (
        tree.yearly[year].names_file
        and named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.YEARLY, year
        )
        is None
    ):
        where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.YEARLY)
        return _refused(
            tree,
            year,
            f"{where.name} names it and no yearly file holds it",
            ledger.LedgerFault.FILE_MISSING,
        )
    _drop_months(tree, year)
    return ()


def _fetched(tree: CompactTree, year: str) -> PeriodFetch:
    """What packing one year downloads: its own file when one is at its path, else its months.

    A year its index names is finished by names and downloads nothing, and a
    year whose own file is there is adopted from that file alone.
    """
    if year in tree.yearly:
        return PeriodFetch()
    own = named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.YEARLY, year)
    if own is not None:
        return PeriodFetch(beside=(own,))
    return PeriodFetch(folders=(tree.monthly_year_folder(year),))


def absorb(
    tree: CompactTree, choice: StepChoice, *, stamp: str, identity: WriterIdentity
) -> tuple[Stop, ...]:
    """Pack the years chosen for this wake, oldest first, stopping at the first one refused.

    A choice an operator range refused stops here, at the year the range left
    out, with nothing taken. The step packs only the years whose files fit what
    is left of the shard's download budget, and stops at the first that does
    not.
    """
    if choice.stopped_because is StopReason.FAILED and choice.resume_from is not None:
        return _refused(
            tree,
            choice.resume_from,
            "the operator range leaves it out, and it is packed before any year the range "
            "names. Widen the range to include it",
        )
    if choice.first is None or choice.last is None:
        return ()
    years = [f"{number:04d}" for number in range(int(choice.first), int(choice.last) + 1)]
    tree.name_years(years)
    fits, over = tree.fit_to_budget(years, lambda year: _fetched(tree, year))
    tree.fetch(_fetched(tree, year) for year in fits)
    for position, year in enumerate(years):
        if over is not None and position == len(fits):
            return (over,)
        try:
            if year in tree.yearly:
                stops = _finish(tree, year)
            else:
                stops = _pack(tree, year, identity=identity)
        except OverBudgetError as spent:
            return (tree.stop_spent(year, spent),)
        if stops:
            return stops
        tree.yearly_through = max(year, tree.yearly_through or year)
        tree.write_watermark(
            Period.YEARLY, through=tree.yearly_through, advanced_at=stamp, run_id=identity.run_id
        )
    if choice.stopped_because is StopReason.CEILING and choice.resume_from is not None:
        return (Stop(StopReason.CEILING, choice.resume_from),)
    return ()
