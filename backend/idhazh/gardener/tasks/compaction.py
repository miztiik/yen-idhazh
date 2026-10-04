"""What one pass of a ledger's compaction does, in which order, and what its record says.

One task a ledger, declared as `config/gardener/compact-<ledger>.json` and
served by this module through its kind, so a ledger joins the compaction with
one declaration and no Python. A pass runs five steps in one process, and the
shard lands all of them in one commit:

1. the month files the monthly window no longer keeps are dropped;
2. raw days past the monthly window are dropped;
3. every year that is done is packed into its year file, where the declaration
   sets `monthly_keep_days`;
4. every month that is done is absorbed into its month file;
5. every raw day that is due is taken into its daily file.

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
minus the `bytes` of the index entries the pass wrote. `seen` counts every raw
day folder listed and every file read or weighed, so the listing's growth while
a compaction stays dry shows in each record. A day, month or year refused ends
the pass `failed` at that period, and the task exits 1 while every other step it
took still lands; a budget running out ends it at `ceiling`.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.COMPACTION


def run(context: TaskContext, *, months: frozenset[str] | None = None) -> Pass:
    """Drop, or only name, what the window no longer keeps; pack years and months; take days."""
    import logging
    from datetime import UTC, datetime, time
    from pathlib import Path

    from idhazh import month_partition
    from idhazh.contracts.collection_prune import StopReason
    from idhazh.contracts.file_envelope import WriterIdentity
    from idhazh.contracts.knobs.gardener import CompactionPolicy
    from idhazh.gardener import schedule
    from idhazh.gardener.tasks import _daily_period, _monthly_period, _yearly_period
    from idhazh.gardener.tasks._compact_tree import CompactTree

    policy = context.policy
    if not isinstance(policy, CompactionPolicy):
        raise ValueError(f"the compaction task was handed a {policy.kind} declaration")
    now = datetime.combine(context.today, time.min, tzinfo=UTC)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    identity = WriterIdentity(
        run_id=context.run_id,
        attempt=context.attempt,
        job=context.job,
        shard=context.shard,
        producer=__name__.partition(".")[2],
        git_sha=context.git_sha,
    )
    if context.period_range is not None:
        months = frozenset(month_partition.months_between(*context.period_range))
    tree = CompactTree.read(context.state_dir, policy.ledger, context.listing, months=months)
    first_kept = _monthly_period.first_kept_month(
        now=now, daily_keep_days=policy.daily_keep_days, window=policy.monthly_window
    )
    # A window that only reports keeps what it would drop, so packing reads it as forever.
    reports = policy.month_deletes_dry_run
    stops = (
        *(_monthly_period.spare if reports else _monthly_period.drop)(tree, first_kept=first_kept),
        *(_daily_period.spare if reports else _daily_period.drop)(tree, first_kept=first_kept),
        *_yearly_period.absorb(tree, policy, now=now, stamp=stamp, identity=identity),
        *_monthly_period.absorb(tree, policy, now=now, stamp=stamp, identity=identity),
        *_daily_period.compact(
            tree,
            policy,
            now=now,
            stamp=stamp,
            identity=identity,
            first_kept=None if reports else first_kept,
        ),
    )
    tree.finish()
    if not policy.dry_run:
        tree.apply()

    def shown(path: Path) -> str:
        return path.relative_to(context.repo_root).as_posix()

    taken = tree.taken(shown)
    spared = tree.spared(shown)
    stop = next((held for held in stops if held.because is StopReason.FAILED), None) or next(
        (held for held in stops if held.because is StopReason.CEILING), None
    )
    if context.period_range is None:
        date_range = None
        until = schedule.newest_eligible(now=now, after_days=policy.compact_after_days).isoformat()
    else:
        date_range = month_partition.day_bounds(*context.period_range)
        until = date_range[1]
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
    )
    logging.getLogger(__name__).info(
        "compaction of %s%s: %s files written, %s deleted, %s kept that the monthly window "
        "would delete, %s bytes freed, daily through %s, monthly through %s, yearly through "
        "%s, stopped %s",
        policy.ledger.value,
        " (dry run)" if policy.dry_run else "",
        len(outcome.written),
        len(outcome.taken),
        len(spared),
        outcome.bytes_freed,
        tree.daily_through or "nothing yet",
        tree.monthly_through or "nothing yet",
        tree.yearly_through or "nothing yet",
        outcome.stopped_because.value
        + (f" at {outcome.resume_from}" if outcome.resume_from else ""),
    )
    return outcome
