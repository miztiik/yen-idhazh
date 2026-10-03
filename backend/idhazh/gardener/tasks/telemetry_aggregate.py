"""Which item-health months are past full grain, and what is kept of them before their rows go?

The census files one row per item per run, and past the full-grain series a
month is folded to one row per (date, step) under `state/item-health-summary/`,
written whole and read back. The rows themselves moved to parquet under
`state/raw/item-health/` and `state/compact/item-health/`, and what deletes them
now is the `item-health` compaction's monthly window, which reaches further back
than the full-grain series here - so a month is summarised before anything can
take its rows. Each day is read settled, through the ledger door, because a
re-run files a second attempt beside the first and folding both would count an
item twice.

**Both item-health folders are read here and owned by the compaction.** The
declaration names them under `reads`, so their names are listed for this task
whichever shard it lands in, and a due month is found from those names alone.
Only a due month's folders are fetched, and the compact index with them: the
ledger door decides from that index which files serve a day, and an index the
checkout lacked would read as no compact file at all.

The browser's copy of each month under `frontend/public/telemetry/` goes once it
is past the public-copy series. A summary past the aggregate series is deleted
outright; while that series is `forever`, none is.

A month already summarised is not folded again. The summary folder need not be
in the checkout yet: the first summary a pass writes is what creates it, so a
due month never waits on it. A dry run folds every due month
in memory and writes nothing, so the log says how many rows would become how
many.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Summarise each due month, then take expired copies and summaries past their series."""
    import dataclasses
    import logging

    from idhazh import config, day_partition, ledger, month_partition, retention
    from idhazh.config import FULL_GRAIN
    from idhazh.contracts.file_envelope import Period
    from idhazh.contracts.item_health import ItemHealthRow
    from idhazh.contracts.knobs.gardener import ForeverWindow, RetentionPolicy
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import named_trees, retention_files
    from idhazh.telemetry.publish import public_telemetry

    policy = context.policy
    series = policy.series if isinstance(policy, RetentionPolicy) and policy.series else {}
    never = ForeverWindow(unit="forever")
    keep_from = retention_files.first_kept_month(
        series.get(FULL_GRAIN, policy.window), context.today
    )
    public_from = retention_files.first_kept_month(series.get("public-copy", never), context.today)
    aggregate_from = retention_files.first_kept_month(series.get("aggregate", never), context.today)
    def expired(first_kept: str | None) -> list[str]:
        if first_kept is None:
            return []
        if context.period_range is None:
            return month_partition.months_before(first_kept, policy.lookback_periods + 1)
        start, end = context.period_range
        requested = month_partition.months_between(start, end)
        if requested[-1] >= first_kept:
            raise ValueError(
                f"backlog range {start} through {end} must end before the kept-month "
                f"boundary {first_kept}"
            )
        return requested

    expired_full_grain = expired(keep_from)
    expired_public = expired(public_from)
    expired_aggregate = expired(aggregate_from)
    state = context.state_dir
    listing = context.listing
    folds = retention_files.owned_tree(
        context, ledger.tree_root(state, LedgerName.ITEM_HEALTH_SUMMARY)
    )
    copies_root = public_telemetry.DEFAULT_PUBLIC_ROOT.relative_to(config.REPO_ROOT)
    public = retention_files.owned_tree(context, context.repo_root / copies_root)

    held_item_health_months = set(
        named_trees.held_months(listing, state, LedgerName.ITEM_HEALTH)
    )
    due = [
        month
        for month in expired_full_grain
        if month in held_item_health_months
        and not listing.holds(ledger.path(state, LedgerName.ITEM_HEALTH_SUMMARY, month))
    ]
    if due:
        raw = ledger.raw_root(state, LedgerName.ITEM_HEALTH)
        index = ledger.compact_index_path(state, LedgerName.ITEM_HEALTH, Period.DAILY)
        listing.fetch(
            [
                index.parent,
                *(raw.joinpath(month[:4], month[5:7]) for month in due),
                *(
                    ledger.compact_path(
                        state, LedgerName.ITEM_HEALTH, Period.DAILY, f"{month}-01"
                    ).parent
                    for month in due
                ),
            ],
            beside=[
                found
                for month in due
                if (
                    found := named_trees.compact_file(
                        listing, state, LedgerName.ITEM_HEALTH, Period.MONTHLY, month
                    )
                )
                is not None
            ],
        )
    summaries = {
        month: retention.compact_month(
            ledger.load_days(
                state, LedgerName.ITEM_HEALTH, ledger.month_days(month), model=ItemHealthRow
            )
        )
        for month in due
    }
    if not policy.dry_run:
        for month, summary in summaries.items():
            target = ledger.path(state, LedgerName.ITEM_HEALTH_SUMMARY, month)
            ledger.write_item_health_summary(target, summary)
            if ledger.load_item_health_summary(target) != summary:
                raise ValueError(
                    f"{ledger.relpath(LedgerName.ITEM_HEALTH_SUMMARY, month)} did not read "
                    "back as it was written"
                )
    copies = (
        named_trees.month_files(listing, public, ".csv", expired_public)
        if public is not None
        else []
    )
    old_folds = (
        named_trees.month_files(listing, folds, ".csv", expired_aggregate)
        if folds is not None
        else []
    )
    aged = [
        *(retention_files.Aged(path=copy, day=f"{copy.stem}-01") for copy in copies),
        *(retention_files.Aged(path=fold, day=f"{fold.stem}-01") for fold in old_folds),
    ]
    logging.getLogger(__name__).info(
        "telemetry fold%s: %s due - %s summary rows, %s browser copies expired",
        " (dry run)" if policy.dry_run else "",
        ", ".join(due) or "no month",
        sum(len(summary) for summary in summaries.values()),
        len(copies),
    )
    outcome = retention_files.take_files(
        context,
        aged,
        collection=ledger.tree_relpath(LedgerName.ITEM_HEALTH_SUMMARY),
        first_kept=retention_files.first_day_of(keep_from),
        after_delete=day_partition.drop_empty_day_dirs,
    )
    return dataclasses.replace(
        outcome,
        written=tuple(ledger.relpath(LedgerName.ITEM_HEALTH_SUMMARY, month) for month in due),
    )
