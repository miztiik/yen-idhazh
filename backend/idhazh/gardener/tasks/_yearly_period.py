"""Which finished years one ledger's compaction packs into year files, and in what order.

**Only a declaration that sets `monthly_keep_days` packs years.** Every other
ledger keeps its month files as `monthly_window` says, exactly as before.

**A year is packed whole or not at all**, and only once three things are true:
at least `monthly_keep_days` whole days have passed since it ended, at 00:00 UTC
on the 1 January after it; the monthly watermark is past its December; and the
monthly index names every month of it, each with its file present. The first two
say the year is done, the third that nothing of it is missing. A year that fails
the first or second waits for a later wake. A year missing a month is a hole: it
is refused by name, the yearly watermark stays where it is and the task exits 1,
because packing it would put the missing month in no period. A year's months run
from January to December, except in the first year a ledger packs, whose months
start at the oldest month the monthly index names.

**The pass writes all year files, then the final yearly and monthly indexes
once, then deletes absorbed month files, then advances the yearly watermark
once, last.** A pass that stops before the yearly index leaves every
month file in place, so the next wake packs that year again from them. A pass
that stops after it leaves a year the yearly index already names, so the next
wake finishes it instead: it finds remaining month files by calendar month,
deletes them, rewrites the
monthly index and moves the watermark, and builds nothing. Either way no row is
lost, and none is read twice, because a reader reads a month both indexes name
from its year. The month files are joined as they are and never settled, because
each already holds one row per record; the monthly watermark is left alone.

**A year file is built one month at a time**, one parquet row group per month
that holds a row, so the pass holds one month's rows at once and a reader that
filters on a date can skip the other months. A year file over GitHub's
large-file line is refused by name and its month files are kept, because a file
over twice that line would make every later push fail.

Year files are kept for ever. Every year here is a UTC year, and every rule is
whole days after a year's own end, so every wake of one UTC day gets the same
answer (CLAUDE.md section 2).
"""

from __future__ import annotations

import logging
from datetime import datetime

from idhazh import ledger
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.knobs.gardener import GITHUB_LARGE_FILE_BYTES, CompactionPolicy
from idhazh.contracts.ledger_index import CompactEntry
from idhazh.gardener import named_trees, schedule
from idhazh.gardener.tasks._compact_tree import CompactTree, Stop

logger = logging.getLogger(__name__)


def months_of(year: str, *, first: str | None = None) -> list[str]:
    """Every UTC month of a `YYYY` year from `first`, or from January, to December."""
    start = 1 if first is None else int(first[5:7])
    return [f"{year}-{number:02d}" for number in range(start, 13)]


def _after(year: str) -> str:
    """The `YYYY` year after this one."""
    return f"{int(year) + 1:04d}"


def _ready(tree: CompactTree, year: str, *, now: datetime, after_days: int) -> bool:
    """Whether a year is done: old enough, and every month of it absorbed."""
    return (
        (tree.months is None or set(months_of(year)).issubset(tree.months))
        and schedule.is_year_eligible(year, now=now, after_days=after_days)
        and tree.monthly_through is not None
        and (
            tree.monthly_through >= f"{year}-12"
            if tree.months is not None
            else tree.monthly_through > f"{year}-12"
        )
    )


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


def _pack(
    tree: CompactTree, year: str, months: list[str], *, identity: WriterIdentity
) -> tuple[Stop, ...]:
    """Build one year's file from its month files, then decide every change packing it takes."""
    missing = [month for month in months if month not in tree.monthly]
    if missing:
        where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.MONTHLY)
        return _refused(
            tree,
            year,
            f"{where.name} does not name {', '.join(missing)}",
            ledger.LedgerFault.DAY_MISSING,
        )
    files = [
        named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month)
        for month in months
    ]
    absent = [month for month, found in zip(months, files, strict=True) if found is None]
    if absent:
        return _refused(
            tree,
            year,
            f"no monthly file holds {', '.join(absent)}",
            ledger.LedgerFault.FILE_MISSING,
        )
    held = [found for found in files if found is not None]
    model = ledger.door_contract(tree.ledger)
    try:
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
    except ValueError as refusal:
        return _refused(tree, year, str(refusal))
    if len(built.data) > GITHUB_LARGE_FILE_BYTES:
        return _refused(
            tree,
            year,
            f"its file would be {len(built.data)} bytes, over GitHub's large-file line of "
            f"{GITHUB_LARGE_FILE_BYTES}, so its month files are kept",
        )
    tree.write(built.path, built.data)
    tree.yearly[year] = CompactEntry(covers=year, rows=built.rows, bytes=len(built.data))
    tree.mark_index(Period.YEARLY)
    for path in held:
        tree.delete(path)
    for month in months:
        del tree.monthly[month]
    tree.mark_index(Period.MONTHLY)
    return ()


def _finish(tree: CompactTree, year: str) -> tuple[Stop, ...]:
    """A year the yearly index already names: delete the month files of it still there."""
    held = named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, Period.YEARLY, year)
    if held is None:
        where = ledger.compact_index_path(tree.state_dir, tree.ledger, Period.YEARLY)
        return _refused(
            tree,
            year,
            f"{where.name} names it and no yearly file holds it",
            ledger.LedgerFault.FILE_MISSING,
        )
    tree.listing.fetch([tree.monthly_year_folder(year)])
    left = months_of(year)
    for month in left:
        found = named_trees.compact_file(
            tree.listing, tree.state_dir, tree.ledger, Period.MONTHLY, month
        )
        if found is not None:
            tree.delete(found)
        tree.monthly.pop(month, None)
    tree.mark_index(Period.MONTHLY)
    return ()


def absorb(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    stamp: str,
    identity: WriterIdentity,
) -> tuple[Stop, ...]:
    """Pack every year that is done, oldest first, at most `max_periods_per_run` of them.

    With no yearly watermark the first year is the oldest one the yearly index
    names, which a pass that stopped before its watermark left; else the one
    holding the oldest month the monthly index names, from that month.
    """
    if policy.monthly_keep_days is None:
        return ()
    first: str | None = None
    if tree.yearly_through is not None:
        year = _after(tree.yearly_through)
    elif tree.yearly:
        year = min(tree.yearly)
    elif tree.monthly:
        first = min(tree.monthly)
        year = first[:4]
    else:
        return ()
    if tree.months is not None:
        candidates = [
            named
            for named in sorted({month[:4] for month in tree.months})
            if set(months_of(named)).issubset(tree.months)
            and (
                tree.yearly_through is None
                or named > tree.yearly_through
                or any(month.startswith(f"{named}-") for month in tree.monthly)
            )
        ]
        if not candidates:
            return ()
        year = candidates[0]
        pending = sorted(
            {
                month[:4]
                for month in tree.monthly
                if month[:4] < year
                and month[:4] not in tree.yearly
                and (tree.yearly_through is None or month[:4] > tree.yearly_through)
            }
        )
        if pending:
            return _refused(
                tree,
                year,
                f"name all months of pending years before advancing the watermark: {pending}",
            )
        held = sorted(month for month in tree.monthly if month.startswith(f"{year}-"))
        first = held[0] if held else None
    ready: list[str] = []
    ahead = year
    while len(ready) < policy.max_periods_per_run and _ready(
        tree, ahead, now=now, after_days=policy.monthly_keep_days
    ):
        ready.append(ahead)
        ahead = _after(ahead)
    tree.listing.fetch(
        [tree.monthly_year_folder(held) for held in ready if held not in tree.yearly]
    )
    taken = 0
    while _ready(tree, year, now=now, after_days=policy.monthly_keep_days):
        if taken == policy.max_periods_per_run:
            return (Stop(StopReason.CEILING, year),)
        if year in tree.yearly:
            stops = _finish(tree, year)
        else:
            stops = _pack(tree, year, months_of(year, first=first), identity=identity)
        if stops:
            return stops
        tree.yearly_through = max(year, tree.yearly_through or year)
        tree.write_watermark(
            Period.YEARLY, through=tree.yearly_through, advanced_at=stamp, run_id=identity.run_id
        )
        taken += 1
        year, first = _after(year), None
    return ()
