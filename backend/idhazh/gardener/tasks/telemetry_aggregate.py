"""Which item-health months are past full grain, and what is kept of them before their rows go?

The census files one row per item per run, and past the full-grain series a
month is folded to one row per (date, step) under
`state/raw/item-health-summary/`, through the ledger door, and read back. The
rows themselves moved to parquet under
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

A month already summarised is not folded again. The summary's raw folder need
not be in the checkout yet: the first summary a pass writes is what creates it,
so a due month never waits on it. A dry run folds every due month in memory and
writes nothing, so its finished event names each summary file it would write.
"""

from __future__ import annotations

import uuid

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION
OWNED_LEDGERS = (LedgerName.ITEM_HEALTH_SUMMARY,)


def run(context: TaskContext) -> Pass:
    """Summarise each due month, then take expired copies and summaries past their series."""
    import dataclasses

    from idhazh import config, day_partition, ledger, month_partition, retention
    from idhazh.config import FULL_GRAIN
    from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
    from idhazh.contracts.item_health import ItemHealthRow
    from idhazh.contracts.item_health_summary import ItemHealthSummaryRow
    from idhazh.contracts.knobs.gardener import ForeverWindow, RetentionPolicy
    from idhazh.gardener import named_trees, retention_files
    from idhazh.telemetry.publish import public_telemetry

    policy = context.policy
    series = policy.series if isinstance(policy, RetentionPolicy) and policy.series else {}
    never = ForeverWindow(unit="forever")
    keep_from = retention_files.first_kept_month(
        series.get(FULL_GRAIN, policy.window), context.today
    )
    public_from = retention_files.first_kept_month(series.get("public-copy", never), context.today)

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
    state = context.state_dir
    listing = context.listing
    copies_root = public_telemetry.DEFAULT_PUBLIC_ROOT.relative_to(config.REPO_ROOT)
    public = retention_files.owned_tree(context, context.repo_root / copies_root)

    held_item_health_months = set(named_trees.held_months(listing, state, LedgerName.ITEM_HEALTH))
    summarised_months = {
        day[:7]
        for day in named_trees.raw_days(
            listing, state, LedgerName.ITEM_HEALTH_SUMMARY, months=expired_full_grain
        )
    }
    due = [
        month
        for month in expired_full_grain
        if month in held_item_health_months and month not in summarised_months
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
    filed: list[str] = []
    identity = WriterIdentity(
        run_id=context.run_id,
        attempt=context.attempt,
        job=context.job,
        shard=context.shard,
        producer=__name__.partition(".")[2],
        git_sha=context.git_sha,
    )
    planned = [
        ledger.raw_path(
            state,
            LedgerName.ITEM_HEALTH_SUMMARY,
            day,
            uuid.uuid5(uuid.NAMESPACE_URL, f"{context.run_id}|item-health-summary|{day}"),
            fmt=Format.PARQUET,
        )
        .relative_to(context.repo_root)
        .as_posix()
        for summary in summaries.values()
        for day in sorted({row.date for row in summary})
    ]
    for month, summary in summaries.items():
        if policy.dry_run:
            continue
        written = ledger.persist(
            state,
            summary,
            ledger=LedgerName.ITEM_HEALTH_SUMMARY,
            covers=f"{month}-01",
            identity=identity,
        )
        filed.extend(path.relative_to(context.repo_root).as_posix() for path in written)
        if (
            ledger.load_days(
                state,
                LedgerName.ITEM_HEALTH_SUMMARY,
                ledger.month_days(month),
                model=ItemHealthSummaryRow,
            )
            != summary
        ):
            shown = ledger.raw_root(state, LedgerName.ITEM_HEALTH_SUMMARY).relative_to(
                context.repo_root
            )
            raise ValueError(
                f"{shown.as_posix()}/{month[:4]}/{month[5:7]} did not read back as it was written"
            )
    copies = (
        named_trees.month_files(listing, public, ".csv", expired_public)
        if public is not None
        else []
    )
    aged = [
        *(retention_files.Aged(path=copy, day=f"{copy.stem}-01") for copy in copies),
    ]
    outcome = retention_files.take_files(
        context,
        aged,
        collection=copies_root.as_posix(),
        first_kept=retention_files.first_day_of(keep_from),
        after_delete=day_partition.drop_empty_day_dirs,
    )
    return dataclasses.replace(
        outcome,
        written=tuple(planned if policy.dry_run else filed),
    )
