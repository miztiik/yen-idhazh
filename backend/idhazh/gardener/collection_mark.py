"""Through which UTC day has a collection task's walk handled every member, by its own record?

A task that walks its collection a day at a time writes the newest day it
handled whole on its row of the gardener's record, as `handled_through`. Its
next pass reads that day back here and starts the day after. Nothing else is
read: the gardener's own ledger, over the last `mark_lookback_days` UTC days,
today included, through the ledger door.

**Every path the door may read is named before it is fetched.** The three
indexes, each day's raw folder, and the day, month and year files that could
hold one of those days are named in the task's listing at run time, then
fetched, then read. So the read is those days and no more (Guardrail #12), and
it is the same read on a runner, whose checkout holds no record until it is
fetched, as on a developer's machine.

**Only a row from a pass with the same `dry_run` counts.** A dry run handles a
day by reporting or counting it, which deletes nothing, so its mark says
nothing about what a live pass has deleted. A row that carries no mark is
passed over: its task failed before its walk began. Of the rest, the latest
day wins, because a day stays true once it is written: whichever pass wrote
it, every member up to it was handled.
"""

from __future__ import annotations

from datetime import timedelta

from idhazh import ledger
from idhazh.contracts.collection_prune import CollectionPruneRow
from idhazh.contracts.file_envelope import Format, Period
from idhazh.contracts.knobs.gardener import CollectionTaskPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.context import TaskContext


def last_mark(context: TaskContext, policy: CollectionTaskPolicy) -> str | None:
    """The latest day this task's own rows say a pass with its `dry_run` handled through."""
    state = context.state_dir
    which = LedgerName.GARDENER
    days = [
        (context.today - timedelta(days=back)).isoformat()
        for back in range(policy.mark_lookback_days)
    ]
    raw = ledger.raw_root(state, which)
    folders = [
        ledger.compact_index_path(state, which, Period.DAILY).parent,
        *(raw.joinpath(day[:4], day[5:7], day[8:10]) for day in days),
    ]
    covering = sorted(
        {(Period.DAILY, day) for day in days}
        | {(Period.MONTHLY, day[:7]) for day in days}
        | {(Period.YEARLY, day[:4]) for day in days}
    )
    packed = [
        ledger.compact_path(state, which, period, covers, fmt=fmt)
        for period, covers in covering
        for fmt in Format
    ]
    listing = context.listing.name([*folders, *packed])
    listing.fetch(folders, beside=[path for path in packed if listing.holds(path)])
    task = policy.collection.value
    marks = [
        row.handled_through
        for row in ledger.load_days(state, which, days, model=CollectionPruneRow)
        if row.task == task and row.dry_run == policy.dry_run and row.handled_through is not None
    ]
    return max(marks, default=None)
