"""What one pass of a ledger's compaction does, in which order, and what its record says.

One task a ledger, declared as `config/gardener/compact-<folder>.json` and
served by this module through its kind, so a ledger joins the compaction with
one declaration and no Python. A pass runs five steps in one process, and the
shard lands all of them in one commit:

0. expired indexed years are dropped by exact path in every format, at most
   `max_periods_per_run`, with progress preserved in the yearly index;
1. the oldest months past the monthly window's keep line are dropped, at most
   `max_periods_per_run` of them, each with every file at its paths and then
   its index entry;
2. raw days past the keep line are dropped by their listed paths, unread: those
   in the months step 1 drops, and those a first day run looked back over;
3. every year chosen for this wake is packed into its year file, or into an
   entry with no file, where the declaration sets `monthly_keep_days`;
4. every month chosen for this wake is closed into its month file;
5. every closed month a raw file landed in is re-opened, then every day chosen
   for this wake is packed into its day file, after each packed day that holds
   raw files again.

**Each step chooses its own periods.** The months step 1 drops, the years step
3 packs, the months step 4 closes and the days step 5 packs are chosen before
any step runs, from the ledger's own indexes and the marks worked out from
them, and the wake's day (`_compaction_periods`), and logged once as
`PeriodsChosen`. An index that is not there is first rebuilt from the files of
its periods, found in one named folder a year (`_absent_indexes`). A range a person
names, or the first and last month a migration packs, limits that choice. A
scheduled wake names no range, and its listing holds nothing of the ledger but
its marks until a step names what it chose. A day step with no mark first has
the months it looks back over named, because its first day is a raw day. Step 2
chooses nothing of its own: it takes the raw days past the keep line in the
months step 1 drops and in those a first day run looked back over.

**The monthly window has a switch of its own.** Steps 3 to 5 delete only files
whose rows they have just written into a coarser file; the window's drops in
steps 1 and 2 delete rows. So while `month_deletes_dry_run` is true, steps 1 and
2 name the month files and raw days the window would drop and keep them, and
the packing steps take those periods like any other, as if the window kept
every month. `dry_run` still decides whether anything at all lands.

**Drops first and days last, because no pass may write a path it deletes.** The
shard that lands a pass refuses a path it both wrote and deleted, and a pass
that did either would stall every wake after it. In this order a year packs
month files and a month absorbs daily files that earlier wakes wrote, never one
this pass wrote, and a period whose last part this pass writes is taken at the
next wake instead.

**Every rule is whole days after a period's own end**, so the pass measures
from 00:00 UTC on the wake's own UTC day and gets the answer any instant of
that day would (CLAUDE.md section 2).

**A dry run does all of the work and changes nothing.** It reads every file,
settles the rows, builds each file in memory, and reports every path a live
pass would write and delete, so the list a person reads before turning a
compaction live is the list the live pass carries out.

**What the record says.** `taken` is every file the pass deleted, or would
have; `written` every file it wrote, or would have. `selected` counts those
deletes and every file the monthly window would delete that the pass kept
because the window only reports, so `selected` minus the deletes is what turning
the window live would take at that wake. `bytes_freed` is what the
deletes free and is never netted against the writes: the net is `bytes_freed`
minus the `bytes` of the index entries the pass wrote. A file moved aside is
deleted at its old path and written at its new one, so it is in both lists and
frees nothing. `seen` counts every raw day folder listed and every file read or
weighed, so the listing's growth while a compaction stays dry shows in each
record. A day, month or year refused ends the pass at that period while every
other step it took still lands: `failed`, fault `raised`, for a defect, or
`failed`, fault `manual-action`, for a named refusal only a person can settle;
the task exits 1 either way. A cause outside the code that waits for another
wake or a named repair ends `deferred` with a word that names it, and the job
stays green.
A budget running out ends it at `ceiling` - the cap, a day's most raw files, or
what is left of the shard's download budget. A pass whose marks, or the files
an absent index is rebuilt from, do not fit that budget takes nothing and ends
`ceiling` at its index folder, or `failed` there when they alone are larger
than the whole budget. `recovered` is every fault the pass recorded instead of
stopping, one note a period, in the order it met them. `periods` is what the
pass did, period by period, compared with the indexes it read, and where each
mark ended; its task's finished event carries it. A pass that takes nothing
ends on its own idle word: `outside-range` when a person named a range,
`empty` when no step has anything to start from, else `not-due`. The
compaction reads no clock: every age is counted from the wake's UTC day.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.COMPACTION


def run(context: TaskContext) -> Pass:
    """Drop, or only name, the oldest months past the keep line; pack years and months; take days.

    `context.operator_range` is the range a person named; no step takes
    anything outside it.
    """
    from datetime import UTC, datetime, time
    from pathlib import Path

    from idhazh import ledger, month_partition
    from idhazh.contracts.collection_prune import StopReason
    from idhazh.contracts.file_envelope import Period, WriterIdentity
    from idhazh.contracts.knobs.gardener import CompactionPolicy
    from idhazh.gardener import event_log
    from idhazh.gardener.file_listing import OverBudgetError
    from idhazh.gardener.tasks import (
        _absent_indexes,
        _compaction_periods,
        _daily_period,
        _monthly_period,
        _yearly_expiry,
        _yearly_period,
    )
    from idhazh.gardener.tasks._compact_tree import CompactTree, stop_over_budget

    policy = context.policy
    if not isinstance(policy, CompactionPolicy):
        raise ValueError(f"the compaction task was handed a {policy.kind} declaration")
    now = datetime.combine(context.today, time.min, tzinfo=UTC)
    identity = WriterIdentity(
        run_id=context.run_id,
        attempt=context.attempt,
        job=context.job,
        shard=context.shard,
        producer=__name__.partition(".")[2],
        git_sha=context.git_sha,
    )
    operator_range = context.operator_range
    if operator_range is None:
        date_range = None
        until = _compaction_periods.newest_due(policy, now=now)
    else:
        date_range = month_partition.day_bounds(*operator_range)
        until = date_range[1]

    def shown(path: Path) -> str:
        return path.relative_to(context.repo_root).as_posix()

    try:
        tree = CompactTree.read(context.state_dir, policy.ledger, context.listing)
        read = tree.entries_now()
        _absent_indexes.rebuild(
            tree,
            policy,
            now=now,
            operator_range=operator_range,
            first_ledger_year=context.first_ledger_year,
            owned_folders=context.owned_folders,
        )
    except OverBudgetError as spent:
        marks = ledger.compact_index_path(context.state_dir, policy.ledger, Period.DAILY).parent
        held = stop_over_budget(policy.ledger, shown(marks), spent)
        return Pass(
            collection=policy.ledger.value,
            since=None if date_range is None else date_range[0],
            until=until,
            ceiling=None,
            dry_run=policy.dry_run,
            seen=0,
            selected=0,
            taken=(),
            written=(),
            bytes_freed=0,
            stopped_because=held.because,
            resume_from=held.resume_from,
            fault=held.fault,
        )
    expiry_stops = _yearly_expiry.drop(
        tree, policy, now=now, operator_range=operator_range
    )
    looked_back = _compaction_periods.first_run_months(
        tree, policy, now=now, operator_range=operator_range
    )
    tree.name_raw_months(looked_back)
    chosen = _compaction_periods.choose(tree, policy, now=now, operator_range=operator_range)
    event_log.emit(chosen)
    first_kept = chosen.keep_line
    # Worked out before step 1 takes its months out of the index, for step 2 to read.
    raw_drop_months = [*_monthly_period.months_to_drop(tree, chosen.drops), *looked_back]
    # A window that only reports keeps what it would drop, so packing reads it as forever.
    reports = policy.month_deletes_dry_run
    stops = (
        *expiry_stops,
        *(_monthly_period.spare if reports else _monthly_period.drop)(tree, chosen.drops),
        *(_daily_period.spare if reports else _daily_period.drop)(
            tree, raw_drop_months, first_kept=first_kept
        ),
        *(
            ()
            if chosen.years is None
            else _yearly_period.absorb(tree, chosen.years, identity=identity)
        ),
        *_monthly_period.absorb(tree, chosen.months, identity=identity),
        *_daily_period.compact(
            tree,
            policy,
            chosen.days,
            rerun_span=chosen.rerun_span,
            first_kept=first_kept,
            identity=identity,
        ),
    )
    tree.finish()
    if not policy.dry_run:
        tree.apply()

    taken = tree.taken(shown)
    spared = tree.spared(shown)
    # Table F's order: a defect first, then a cause outside the code, then a budget.
    stop = next(
        (
            held
            for because in (StopReason.FAILED, StopReason.DEFERRED, StopReason.CEILING)
            for held in stops
            if held.because is because
        ),
        None,
    )
    outcome = Pass(
        collection=policy.ledger.value,
        since=None if date_range is None else date_range[0],
        until=until,
        ceiling=None,
        dry_run=policy.dry_run,
        seen=tree.seen(),
        selected=len(taken) + len(spared),
        taken=taken,
        written=tree.written(shown),
        bytes_freed=tree.freed(),
        stopped_because=StopReason.EXHAUSTED if stop is None else stop.because,
        resume_from=None if stop is None else stop.resume_from,
        fault=None if stop is None else stop.fault,
        recovered=tuple(tree.recovered),
        idle_outcome=_compaction_periods.idle_word(chosen),
        periods=tree.periods_taken(read),
    )
    return outcome
