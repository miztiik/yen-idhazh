"""Which years one ledger's compaction packs into year files, and what each year file holds.

**The years are the ones chosen for this wake** (`_compaction_periods`):
consecutive years after the yearly mark, each at least `monthly_keep_days`
whole days past its end and each whose December the monthly mark is strictly
past. Only a declaration that sets `monthly_keep_days` packs years; every other
ledger keeps its month files as `monthly_window` says. The step names what it
reads of its years, then packs them oldest first, each whole or not at all.

**A year accounts for every month from January, or from the ledger's first
month when the ledger began inside it.** A month with a `packed` entry gives its
file's rows; an `empty` month gives none. Every month's `lost_days` carry into
the year's entry. A year whose months give no row is an `empty` entry with no
file, its lost days listed on it, unless its own file is at its path while no
entry names it: that file is adopted (`index-rebuilt`). A month no entry names
is a hole: the year is refused by name as `day-missing`, the yearly watermark
stays where it is and the task exits 1, because packing it would put the
missing month in no period. A month whose entry says `packed` while its file is
not there is refused as `file-missing`.

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
filters on a date can skip the other months. A year file over GitHub's
large-file line is refused by name and its month files are kept, because a file
over twice that line would make every later push fail.

Year files are kept for ever. Every year here is a UTC year (CLAUDE.md
section 2).
"""

from __future__ import annotations

import logging
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_events import StepChoice
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import GITHUB_LARGE_FILE_BYTES
from idhazh.contracts.ledger_index import CompactEntry, EntryState
from idhazh.gardener import ledger_marks, named_trees
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop

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


def _record(
    tree: CompactTree,
    year: str,
    held: list[Path],
    lost: list[str],
    *,
    identity: WriterIdentity,
) -> CompactEntry:
    """A year's entry: its file built from its months' files, else its own file, else no file.

    A year whose months hold no file adopts its own file when one is at its path,
    and is `empty` otherwise. Raises `ValueError` saying why the year cannot be
    recorded, before anything about it is written.
    """
    if not held:
        own = ledger_marks.adopt(tree.listing, tree.state_dir, tree.ledger, Period.YEARLY, year)
        if own is None:
            return CompactEntry(
                covers=year, rows=0, bytes=0, state=EntryState.EMPTY, lost_days=lost
            )
        tree.note_recovery(RecoveryNote.INDEX_REBUILT, year)
        return own.entry.model_copy(update={"lost_days": lost})
    model = ledger.door_contract(tree.ledger)
    built = ledger.render_grouped_period(
        tree.state_dir,
        (tree.load(path, model=model) for path in held),
        model=model,
        ledger=tree.ledger,
        period=Period.YEARLY,
        covers=year,
        identity=identity,
        built_from=len(held),
    )
    if len(built.data) > GITHUB_LARGE_FILE_BYTES:
        raise ValueError(
            f"its file would be {len(built.data)} bytes, over GitHub's large-file line of "
            f"{GITHUB_LARGE_FILE_BYTES}, so its month files are kept"
        )
    tree.write(built.path, built.data)
    return CompactEntry(covers=year, rows=built.rows, bytes=len(built.data), lost_days=lost)


def _pack(tree: CompactTree, year: str, *, identity: WriterIdentity) -> tuple[Stop, ...]:
    """Pack one year no entry names yet from its months, then decide every change that takes."""
    months = _counted(tree, year)
    missing = [month for month in months if month not in tree.monthly]
    if missing:
        where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.MONTHLY)
        return _refused(
            tree,
            year,
            f"{where.name} does not name {', '.join(missing)}",
            ledger.LedgerFault.DAY_MISSING,
        )
    packed = [month for month in months if tree.monthly[month].names_file]
    files = [
        named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month)
        for month in packed
    ]
    absent = [month for month, found in zip(packed, files, strict=True) if found is None]
    if absent:
        return _refused(
            tree,
            year,
            f"no monthly file holds {', '.join(absent)}",
            ledger.LedgerFault.FILE_MISSING,
        )
    held = [found for found in files if found is not None]
    lost = [day for month in months for day in tree.monthly[month].lost_days]
    try:
        tree.yearly[year] = _record(tree, year, held, lost, identity=identity)
    except ValueError as refusal:
        return _refused(tree, year, str(refusal))
    tree.mark_index(Period.YEARLY)
    for path in held:
        tree.delete(path)
    for month in months:
        del tree.monthly[month]
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
    for month in months_of(year):
        found = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
        )
        if found is not None:
            tree.delete(found)
        tree.monthly.pop(month, None)
    tree.mark_index(Period.MONTHLY)
    return ()


def absorb(
    tree: CompactTree, choice: StepChoice, *, stamp: str, identity: WriterIdentity
) -> tuple[Stop, ...]:
    """Pack the years chosen for this wake, oldest first, stopping at the first one refused.

    A choice an operator range refused stops here, at the year the range left
    out, with nothing taken.
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
    tree.listing.fetch(
        [tree.monthly_year_folder(year) for year in years if year not in tree.yearly]
    )
    for year in years:
        stops = _finish(tree, year) if year in tree.yearly else _pack(tree, year, identity=identity)
        if stops:
            return stops
        tree.yearly_through = max(year, tree.yearly_through or year)
        tree.write_watermark(
            Period.YEARLY, through=tree.yearly_through, advanced_at=stamp, run_id=identity.run_id
        )
    if choice.stopped_because is StopReason.CEILING and choice.resume_from is not None:
        return (Stop(StopReason.CEILING, choice.resume_from),)
    return ()
