"""How a closed month takes in raw files that land after it closed.

A GitHub re-run writes into the day its run first wrote, so a raw file can land
in a month the monthly index already names. The day step meets it among the
raw days it names, and hands its month here, before it takes any day.

**The month re-opens, and holds what packing the late day first would have
held.** Each row of a month file keeps the day its raw file covered, so the
month's rows are split back into days. Each late day is settled the way the day
step settles a packed day it takes again: the month's rows of that day first,
then the day's raw files oldest first, one file's rows per work unit - the last
file of its highest attempt - and then one row per key, by the ledger's own
key and preference. The other days' rows stay as they are, and the month is
joined again day by day in date order, as it was built. The month file and its
entry are written again, the late raw files are deleted, and the pass logs the
recovery note `reopened-month` with the month. A late day leaves the month's
`lost_days`, because it now has a record. The marks do not move. An `empty`
month has no file, so its rows are the late rows alone.

**A re-open that cannot be finished keeps every file.** A `packed` entry whose
month file is not there is refused as `file-missing`: rebuilt from the late
files alone, the month would hold only the days that ran again, and its entry
would call that smaller month complete.

**A late raw file that cannot be read is moved aside**, as the day step moves
one, and the month's entry counts it in `set_aside`; a late day whose files
were all moved aside gives no record, so it stays in `lost_days`. A late day
holding more raw files than one period is built from gives its oldest, the rest
wait in its folder, and the month re-opens again at the next wake for them,
ending this pass at `ceiling`. The re-open's download is held to what is left
of the shard's budget: past it, `OverBudgetError` is raised before anything is
decided.
"""

from __future__ import annotations

import logging

from idhazh import ledger
from idhazh.contracts.base import Contract
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.gardener import named_trees
from idhazh.gardener.tasks._compact_tree import CompactTree, PeriodFetch, Stop

logger = logging.getLogger(__name__)


def _kept(
    tree: CompactTree, month: str, why: str, fault: ledger.LedgerFault | None = None
) -> tuple[Stop, ...]:
    """A closed month that is not re-opened, said once by name. Its late raw files are kept."""
    logger.error(
        "a closed month is not re-opened, and the raw files that landed in it are kept "
        "ledger=%s month=%s fault=%s reason=%s",
        tree.ledger.value,
        month,
        fault or "none",
        why,
    )
    return (Stop(StopReason.FAILED, month),)


def reopen[C: Contract](
    tree: CompactTree,
    month: str,
    *,
    most: int,
    model: type[C],
    key: tuple[str, ...],
    identity: WriterIdentity,
) -> tuple[Stop, ...]:
    """Settle every raw day left in one closed month into its file and entry, or say why not.

    The month's raw folder is named first, so every late day of the month is
    taken in, not only the ones the day step named, and the month is written
    once. `most` is how many raw files one period is built from at most. A
    `ceiling` stop at the month says late files wait for the next wake.
    """
    tree.name_months([month])
    late = [day for day in tree.raw_days if day.startswith(f"{month}-")]
    entry = tree.monthly[month]
    own = named_trees.compact_file(
        tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
    )
    if own is None and entry.names_file:
        return _kept(
            tree,
            month,
            "the monthly index names it and no monthly file holds it. Restore the file from "
            "git history, and the next wake re-opens the month",
            ledger.LedgerFault.FILE_MISSING,
        )
    tree.fetch(
        [
            PeriodFetch(
                folders=tuple(tree.raw_day_folder(day) for day in late),
                beside=() if own is None else (own,),
            )
        ]
    )
    try:
        raws = {day: tree.read_raw_day(day, most=most, model=model) for day in late}
        answered = {day: raw for day, raw in raws.items() if raw.taken}
        days: dict[str, list[ledger.StoredRow[C]]] = {}
        for row in [] if own is None or not answered else tree.load(own, model=model):
            days.setdefault(row.identity.covers, []).append(row)
        for day, raw in answered.items():
            days[day] = ledger.settle_rows(
                [days.get(day, []), *(rows for _path, rows in raw.taken)], key
            )
        rows = [row for day in sorted(days) for row in days[day]]
        built = (
            ledger.render_period(
                tree.state_dir,
                rows,
                model=model,
                ledger=tree.ledger,
                period=Period.MONTHLY,
                covers=month,
                identity=identity,
                built_from=(own is not None)
                + sum(len(raw.taken) for raw in answered.values()),
            )
            if answered
            else None
        )
    except ValueError as refusal:
        return _kept(tree, month, str(refusal))
    moved = 0
    for day, raw in raws.items():
        for path, why in raw.unreadable:
            tree.set_aside(path, day, why)
            moved += 1
    if built is None:
        tree.monthly[month] = entry.model_copy(update={"set_aside": entry.set_aside + moved})
    else:
        if own is not None and own != built.path:
            tree.delete(own)
        tree.write(built.path, built.data)
        tree.monthly[month] = CompactEntry(
            covers=month,
            rows=len(rows),
            bytes=len(built.data),
            lost_days=[day for day in entry.lost_days if day not in answered],
            set_aside=entry.set_aside + moved,
        )
    tree.mark_index(Period.MONTHLY)
    for raw in answered.values():
        for path, _rows in raw.taken:
            tree.delete(path)
    if built is not None:
        tree.note_recovery(RecoveryNote.REOPENED_MONTH, month)
    for day, raw in raws.items():
        if raw.unreadable:
            tree.note_recovery(RecoveryNote.SET_ASIDE, day)
        if raw.carried:
            tree.note_recovery(RecoveryNote.CARRIED_OVER, day)
    if any(raw.carried for raw in raws.values()):
        return (Stop(StopReason.CEILING, month),)
    return ()
