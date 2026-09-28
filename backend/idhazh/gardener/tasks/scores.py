"""Which score months are past full grain, and what must be proved before their days go?

The eval ledger is the only record of how a summary scored. Past the full-grain
series a month stops being rows and becomes one summary under
`state/score-archive/`, and four steps per month come before a single day file
of it is unlinked: summarise, write it, read it back through its contract, and
reconcile it against a second reading of those days. A summary that will not
reconcile stops the pass with its days in place, because `prune.yml` rewrites
history on a schedule and a deleted day does not come back.

The index beside those days goes in the same pass, for every month an archive
covers: it is derived from the days and answers only for them. A month is taken
whole, which is why a task that keeps series carries no ceiling. The archive's
own series keeps each summary; while it is `forever`, no summary is ever
deleted.

A dry run still summarises every due month, so the log says what the archive
would weigh against the days it replaces - the figure this policy rests on.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Archive each due month, then take its days, its index, and any summary past its series."""
    import dataclasses
    import logging

    from idhazh import day_partition, day_shards, ledger
    from idhazh.config import FULL_GRAIN
    from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
    from idhazh.contracts.knobs.gardener import ForeverWindow, RetentionPolicy
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.evals import archive as score_archive
    from idhazh.evals import writer as score_writer
    from idhazh.gardener import retention_files
    from idhazh.gardener.one_at_a_time import PruneInterruptedError

    policy = context.policy
    series = policy.series if isinstance(policy, RetentionPolicy) and policy.series else {}
    full_grain = series.get(FULL_GRAIN, policy.window)
    keep_from = retention_files.first_kept_month(full_grain, context.today)
    archive_from = retention_files.first_kept_month(
        series.get("archive", ForeverWindow(unit="forever")), context.today
    )
    state = context.state_dir
    scores = retention_files.owned_tree(context, ledger.tree_root(state, LedgerName.SCORES))
    index = retention_files.owned_tree(context, ledger.tree_root(state, LedgerName.SCORE_INDEX))
    kept = retention_files.owned_tree(context, ledger.tree_root(state, LedgerName.SCORE_ARCHIVE))

    by_month = (
        day_shards.shards_by_month(scores, days=UNBOUNDED_WINDOW)
        if scores is not None and keep_from is not None
        else {}
    )
    due = {
        month: days
        for month, days in sorted(by_month.items())
        if keep_from is not None and month < keep_from
    }
    due_days = {path for days in due.values() for path in days}
    built = {
        month: score_archive.summarise(
            days, month=month, observation_key=score_writer.OBSERVATION_KEY
        )
        for month, days in due.items()
    }
    summaries = score_archive.archive_files(state) if kept is not None else []
    covered = {summary.stem for summary in summaries} | set(due)
    index_days = [
        shard
        for shard in (
            day_shards.shard_files(index, days=UNBOUNDED_WINDOW) if index is not None else ()
        )
        if keep_from is not None
        and day_shards.date_of(shard)[:7] < keep_from
        and day_shards.date_of(shard)[:7] in covered
    ]
    past_series = [
        summary
        for summary in summaries
        if archive_from is not None and summary.stem < archive_from
    ]
    aged = [
        *(
            retention_files.Aged(path=path, day=day_shards.date_of(path))
            for days in due.values()
            for path in days
        ),
        *(retention_files.Aged(path=shard, day=day_shards.date_of(shard)) for shard in index_days),
        *(retention_files.Aged(path=summary, day=f"{summary.stem}-01") for summary in past_series),
    ]

    archived: list[str] = []

    def archive_first(item: retention_files.Aged) -> None:
        """Write, read back and reconcile a month's summary before its first day file goes."""
        month = item.day[:7]
        if item.path not in due_days or month in archived:
            return
        target = score_archive.archive_path(state, month)
        score_archive.write(target, built[month])
        score_archive.reconcile(
            score_archive.read(target),
            due[month],
            month=month,
            observation_key=score_writer.OBSERVATION_KEY,
        )
        archived.append(month)

    def written() -> tuple[str, ...]:
        months = list(due) if policy.dry_run else archived
        return tuple(score_archive.archive_relpath(month) for month in months)

    logging.getLogger(__name__).info(
        "score archive%s: %s due - %s rows into %s bytes of archive, from %s bytes of %s day files",
        " (dry run)" if policy.dry_run else "",
        ", ".join(due) or "no month",
        sum(summary.source_rows for summary in built.values()),
        sum(len(summary.to_json().encode("utf-8")) for summary in built.values()),
        sum(path.stat().st_size for days in due.values() for path in days),
        sum(len(days) for days in due.values()),
    )
    try:
        outcome = retention_files.take_files(
            context,
            aged,
            collection=ledger.tree_relpath(LedgerName.SCORES),
            first_kept=retention_files.first_day_of(keep_from),
            after_delete=day_partition.drop_empty_day_dirs,
            before_delete=archive_first,
        )
    except PruneInterruptedError as stop:
        raise PruneInterruptedError(dataclasses.replace(stop.so_far, written=written())) from stop
    return dataclasses.replace(outcome, written=written())
