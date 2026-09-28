"""Which item-health months are past full grain, and what is kept of them once their rows go?

The census files one row per item per run, and past the full-grain series a
month stops being rows: it is folded to one row per (date, step) under
`state/item-health-summary/`, written whole, and read back before a single day
file of it is unlinked - a fold nobody verified is a deletion nobody can undo.
Each day is settled before it is folded, because a re-run leaves a second
attempt beside the first and folding both would count an item twice.

The browser's copy of each month under `frontend/public/telemetry/` goes after
the days it copies, once it is past the public-copy series, and so does a copy
whose source month an earlier pass already folded. A summary past the
aggregate series is deleted outright; while that series is `forever`, none is.

A month is taken whole, which is why a task that keeps series carries no
ceiling. A dry run still folds every due month in memory, so the log says how
many rows would become how many.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Fold each due month, then take its days, expired copies, and summaries past their series."""
    import dataclasses
    import logging

    from idhazh import config, day_partition, day_shards, ledger, retention
    from idhazh.config import FULL_GRAIN
    from idhazh.contracts.item_health import ItemHealthRow
    from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
    from idhazh.contracts.knobs.gardener import ForeverWindow, RetentionPolicy
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.gardener import retention_files
    from idhazh.gardener.one_at_a_time import PruneInterruptedError
    from idhazh.telemetry.publish import public_telemetry

    policy = context.policy
    series = policy.series if isinstance(policy, RetentionPolicy) and policy.series else {}
    never = ForeverWindow(unit="forever")
    keep_from = retention_files.first_kept_month(
        series.get(FULL_GRAIN, policy.window), context.today
    )
    public_from = retention_files.first_kept_month(series.get("public-copy", never), context.today)
    aggregate_from = retention_files.first_kept_month(series.get("aggregate", never), context.today)
    state = context.state_dir
    census = retention_files.owned_tree(context, ledger.tree_root(state, LedgerName.ITEM_HEALTH))
    folds = retention_files.owned_tree(
        context, ledger.tree_root(state, LedgerName.ITEM_HEALTH_SUMMARY)
    )
    copies_root = public_telemetry.DEFAULT_PUBLIC_ROOT.relative_to(config.REPO_ROOT)
    public = retention_files.owned_tree(context, context.repo_root / copies_root)

    by_month = (
        day_shards.shards_by_month(census, days=UNBOUNDED_WINDOW)
        if census is not None and keep_from is not None
        else {}
    )
    due = {
        month: days
        for month, days in sorted(by_month.items())
        if keep_from is not None and month < keep_from
    }
    due_days = {path for days in due.values() for path in days}
    folded_rows = {
        month: [
            ItemHealthRow.from_csv_row(cells)
            for date in sorted({day_shards.date_of(day) for day in days})
            for cells in day_shards.settled_day(
                census, date, ledger.ITEM_HEALTH_KEY, ItemHealthRow
            )
        ]
        for month, days in due.items()
        if census is not None
    }
    summaries = {month: retention.compact_month(rows) for month, rows in folded_rows.items()}
    copies = [
        copy
        for copy in (retention.month_shards(public) if public is not None else [])
        if public_from is not None and copy.stem < public_from
    ]
    old_folds = [
        fold
        for fold in (retention.month_shards(folds) if folds is not None else [])
        if aggregate_from is not None and fold.stem < aggregate_from
    ]
    aged = [
        *(
            retention_files.Aged(path=path, day=day_shards.date_of(path))
            for days in due.values()
            for path in days
        ),
        *(retention_files.Aged(path=copy, day=f"{copy.stem}-01") for copy in copies),
        *(retention_files.Aged(path=fold, day=f"{fold.stem}-01") for fold in old_folds),
    ]

    written_months: list[str] = []

    def fold_first(item: retention_files.Aged) -> None:
        """Write a month's summary whole, and read it back, before its first day file goes."""
        month = item.day[:7]
        if item.path not in due_days or month in written_months:
            return
        target = ledger.path(state, LedgerName.ITEM_HEALTH_SUMMARY, month)
        ledger.write_item_health_summary(target, summaries[month])
        if ledger.load_item_health_summary(target) != summaries[month]:
            raise ValueError(
                f"{ledger.relpath(LedgerName.ITEM_HEALTH_SUMMARY, month)} did not read back as "
                f"it was written, so the {len(due[month])} day files of {month} stay"
            )
        written_months.append(month)

    def written() -> tuple[str, ...]:
        months = list(due) if policy.dry_run else written_months
        return tuple(ledger.relpath(LedgerName.ITEM_HEALTH_SUMMARY, month) for month in months)

    logging.getLogger(__name__).info(
        "telemetry fold%s: %s due - %s rows into %s summary rows, %s browser copies expired",
        " (dry run)" if policy.dry_run else "",
        ", ".join(due) or "no month",
        sum(len(rows) for rows in folded_rows.values()),
        sum(len(summary) for summary in summaries.values()),
        len(copies),
    )
    try:
        outcome = retention_files.take_files(
            context,
            aged,
            collection=ledger.tree_relpath(LedgerName.ITEM_HEALTH),
            first_kept=retention_files.first_day_of(keep_from),
            after_delete=day_partition.drop_empty_day_dirs,
            before_delete=fold_first,
        )
    except PruneInterruptedError as stop:
        raise PruneInterruptedError(dataclasses.replace(stop.so_far, written=written())) from stop
    return dataclasses.replace(outcome, written=written())
