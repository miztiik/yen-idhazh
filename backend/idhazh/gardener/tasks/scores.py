"""Which score-index days and score summaries are past their series, and may go?

The eval ledger's own rows moved to parquet under `state/raw/scores/` and
`state/compact/scores/`, and what keeps or deletes them now is the `scores`
compaction (`config/gardener/compact-scores.json`). This task keeps the two
trees still beside them: the index a run dedupes against, and the month
summaries under `state/score-archive/`.

An index day goes only once an archive covers its month, because it answers
"do we already hold this measurement?" and the archive's sorted digests are the
only other thing that can. A summary goes once it is past the archive's own
series; while that is `forever`, no summary is ever deleted.

**No month is archived here any more.** The summary was built from the CSV day
files and hashed their bytes, and those files are gone. Building it from the
door's rows is a change to the archive's own shape, so until it lands the
`scores` compaction must stay report-only: turned live, it would delete a month
past its window with no summary written for it.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take the index days an archive covers, and any summary past its series."""
    from idhazh import day_partition, day_shards, ledger
    from idhazh.config import FULL_GRAIN
    from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
    from idhazh.contracts.knobs.gardener import ForeverWindow, RetentionPolicy
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.evals import archive as score_archive
    from idhazh.gardener import retention_files

    policy = context.policy
    series = policy.series if isinstance(policy, RetentionPolicy) and policy.series else {}
    full_grain = series.get(FULL_GRAIN, policy.window)
    keep_from = retention_files.first_kept_month(full_grain, context.today)
    archive_from = retention_files.first_kept_month(
        series.get("archive", ForeverWindow(unit="forever")), context.today
    )
    state = context.state_dir
    index = retention_files.owned_tree(context, ledger.tree_root(state, LedgerName.SCORE_INDEX))
    kept = retention_files.owned_tree(context, ledger.tree_root(state, LedgerName.SCORE_ARCHIVE))

    summaries = score_archive.archive_files(state) if kept is not None else []
    covered = {summary.stem for summary in summaries}
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
        *(retention_files.Aged(path=shard, day=day_shards.date_of(shard)) for shard in index_days),
        *(retention_files.Aged(path=summary, day=f"{summary.stem}-01") for summary in past_series),
    ]
    return retention_files.take_files(
        context,
        aged,
        collection=ledger.tree_relpath(LedgerName.SCORE_INDEX),
        first_kept=retention_files.first_day_of(keep_from),
        after_delete=day_partition.drop_empty_day_dirs,
    )
