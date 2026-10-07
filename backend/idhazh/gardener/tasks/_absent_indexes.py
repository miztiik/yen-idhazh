"""Where a compaction looks for a ledger's packed files when one of its indexes is absent.

An index can be absent while its periods were packed: somebody restored the
ledger's folder from an older commit, or deleted the file. Read as empty, it
would be written again naming only what this pass packs, and every period
packed before would drop out of every read. So before any step runs, the pass
rebuilds each absent index from the files of a bounded list of periods,
coarsest period first, and adopts each file it finds as a step adopts its own
file (`ledger_marks.adopt`): a `packed` entry, its bytes from the listing and
its rows from its footer, logged with the recovery note `index-rebuilt` and the
period. A period with no file adds nothing. The marks are worked out again
after each period, because the next one's periods start where the coarser
rebuild left them.

**The periods it looks for.** For the yearly index, each year from
`first_ledger_year` to the newest year old enough to pack, and none when the
declaration packs no year. For the monthly index, each month from the keep line
of a monthly window whose deletes are live to the newest month old enough to
close. A window that keeps every month, or whose deletes only report, keeps
months older than any line, so its months start at the January after the
newest yearly entry, or at January of `first_ledger_year`. For the daily index,
each day from the month after the monthly mark to the newest due day; with no
monthly mark, from the month a first day run looks back to, or the first month
of an operator range when that is earlier. No period is from before
`first_ledger_year`, when no ledger held a row.

**It names one folder a year, not each period's file.** For each index it
rebuilds, it names the folder of each year those periods fall in -
`daily/<YYYY>`, `monthly/<YYYY>` or `yearly/<YYYY>` under the ledger's compact
folder - and git lists every file inside: at most 366 day files, 12 month files
or one year file a year in each format. It adopts only the files of the periods
it looks for. So a rebuild names at most one more folder each year (CLAUDE.md
Guardrail #12), and a window that keeps every month downloads up to twelve more
month files each year, the rows one packed year file holds.

**An operator range never narrows where the rebuild looks.** A rebuilt index is
written whole, and no later pass looks again once it exists, so a period a
range left out now would be left out of every read for ever.

**Each period's files are fetched in one call**, inside what is left of the
shard's download budget, before any is read. A rebuild whose files do not fit
raises `OverBudgetError`, naming what that whole period's files need, so the
pass takes nothing and ends `ceiling`, or `failed` by name when they alone are
larger than the whole budget. A file at a period's path whose envelope names
another ledger or period is refused by name, and the pass stops: adopting it
would put another period's rows under this one, and leaving it out would drop
the period from every read.

**What it cannot see.** A day file older than the days it looks for stays out
of the rebuilt index, as does a month file before the keep line of a window
whose deletes are live. Looking further back would make the read grow with time
(CLAUDE.md Guardrail #12).

Every rule counts whole days after a period's own end, from 00:00 UTC on the
wake's day (CLAUDE.md section 2).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from idhazh import month_partition
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.gardener_fault import RecoveryNote
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.gardener import ledger_marks, named_trees, schedule
from idhazh.gardener.tasks._compact_tree import CompactTree, PeriodFetch
from idhazh.gardener.tasks._compaction_periods import newest_due
from idhazh.gardener.tasks._monthly_period import days_of, first_kept_month, shift


def rebuild(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
    first_ledger_year: str,
) -> None:
    """Rebuild each index the pass did not find from the files of its periods, coarsest first.

    The marks are worked out again after each period, because the next one's
    paths start where the coarser rebuild left them.
    """
    if Period.YEARLY not in tree.indexed:
        _adopt(
            tree,
            Period.YEARLY,
            pick_years(policy, now=now, first_ledger_year=first_ledger_year),
        )
    if Period.MONTHLY not in tree.indexed:
        _adopt(
            tree,
            Period.MONTHLY,
            pick_months(tree, policy, now=now, first_ledger_year=first_ledger_year),
        )
    if Period.DAILY not in tree.indexed:
        _adopt(
            tree,
            Period.DAILY,
            pick_days(
                tree,
                policy,
                now=now,
                operator_range=operator_range,
                first_ledger_year=first_ledger_year,
            ),
        )


def pick_years(
    policy: CompactionPolicy, *, now: datetime, first_ledger_year: str
) -> list[str]:
    """The years whose own files an absent yearly index is rebuilt from, oldest first."""
    if policy.monthly_keep_days is None:
        return []
    newest = schedule.newest_eligible_year(now=now, after_days=policy.monthly_keep_days)
    return [f"{year:04d}" for year in range(int(first_ledger_year), int(newest) + 1)]


def pick_months(
    tree: CompactTree, policy: CompactionPolicy, *, now: datetime, first_ledger_year: str
) -> list[str]:
    """The months whose own files an absent monthly index is rebuilt from, oldest first."""
    keep_line = (
        None
        if policy.month_deletes_dry_run
        else first_kept_month(
            now=now, daily_keep_days=policy.daily_keep_days, window=policy.monthly_window
        )
    )
    if keep_line is None:
        first = f"{int(max(tree.yearly)) + 1:04d}-01" if tree.yearly else f"{first_ledger_year}-01"
    else:
        first = keep_line
    first = max(first, f"{first_ledger_year}-01")
    newest = schedule.newest_eligible_month(now=now, after_days=policy.daily_keep_days)
    return month_partition.months_between(first, newest) if first <= newest else []


def pick_days(
    tree: CompactTree,
    policy: CompactionPolicy,
    *,
    now: datetime,
    operator_range: tuple[str, str] | None,
    first_ledger_year: str,
) -> list[str]:
    """The days whose own files an absent daily index is rebuilt from, oldest first."""
    newest = newest_due(policy, now=now)
    if tree.monthly_through is not None:
        first = shift(tree.monthly_through, 1)
    else:
        first = shift(newest[:7], -policy.lookback_periods)
        if operator_range is not None:
            first = min(first, operator_range[0])
    first = max(first, f"{first_ledger_year}-01")
    if first > newest[:7]:
        return []
    return [
        day
        for month in month_partition.months_between(first, newest[:7])
        for day in days_of(month)
        if day <= newest
    ]


def _adopt(tree: CompactTree, period: Period, covers: Sequence[str]) -> None:
    """Adopt into an absent index the file of each of these periods, fetched in one call."""
    tree.name_year_folders(period, covers)
    found: dict[str, Path] = {}
    for each in covers:
        held = named_trees.compact_file(tree.listing, tree.state_dir, tree.ledger, period, each)
        if held is not None:
            found[each] = held
    tree.fetch([PeriodFetch(beside=tuple(found.values()))])
    entries = tree.entries(period)
    for each in sorted(found):
        adopted = ledger_marks.adopt(tree.listing, tree.state_dir, tree.ledger, period, each)
        if adopted is None:
            continue
        entries[each] = adopted.entry
        tree.note_recovery(RecoveryNote.INDEX_REBUILT, each)
    if found:
        tree.mark_index(period)
    tree.work_out_marks()
