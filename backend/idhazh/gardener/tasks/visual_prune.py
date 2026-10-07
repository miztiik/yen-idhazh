"""Which rendered pictures are past the archive's window, and what did the cleanup find?

A picture is a file named for an item under a published day of the one digest
tree this declaration owns, and the day's own payloads are never candidates -
they are the record that the day happened. A day before the first one the
window keeps may lose its pictures, oldest day first, up to the declaration's
ceiling: the fuse, because a date read wrong must never eat the archive. The
window is whole days back from the wake, the thirty-day months the old
`retention.image_months` knob counted.

Every pass that walks the tree files one report row, whatever it found, through
the ledger door into `visual-prunes` - the ledger this declaration `appends_to`.
A series written only on the interesting runs could not show a backlog
shrinking, because the runs it skipped would have been the baseline. The row
carries what the fuse held back, which `take` cannot count past its ceiling, so
this counts it. A tree the commit does not hold is not walked, so it is not
reported either: the runner has already said why it walks none.
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take the oldest pictures past the window up to the fuse, and file what was found."""
    import dataclasses
    from datetime import date, timedelta
    from pathlib import Path

    from idhazh import day_partition, ledger
    from idhazh.contracts.file_envelope import WriterIdentity
    from idhazh.contracts.knobs.gardener import DaysWindow, ForeverWindow
    from idhazh.contracts.ledger_name import LedgerName
    from idhazh.contracts.visual_prune import VisualPruneRow
    from idhazh.gardener import named_trees, retention_files

    policy = context.policy
    owns = policy.owns
    if len(owns) != 1 or policy.max_deletes_per_run is None:
        raise ValueError(
            "visual-prune walks one digest tree and reports the fuse that held a pass back, "
            "so config/gardener/visual-prune.json owns exactly one folder and names a "
            "max_deletes_per_run"
        )
    collection = owns[0]
    first_kept = retention_files.first_kept_day(
        policy.window,
        context.today,
        days_back=lambda days: context.today - timedelta(days=days),
    )
    root = retention_files.owned_tree(context, context.repo_root / collection)
    if root is None:
        return retention_files.take_files(
            context, (), collection=collection, first_kept=first_kept
        )
    listing = context.listing
    if context.period_range is not None:
        start_text, end_text = context.period_range
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
        if start > end:
            raise ValueError("a visual-prune backlog range starts after it ends")
        if first_kept is None or end >= first_kept:
            raise ValueError("a visual-prune backlog range must end before the kept-day boundary")
        candidate_days = [
            start + timedelta(days=offset) for offset in range((end - start).days + 1)
        ]
    else:
        candidate_days = (
            day_partition.days_before(first_kept, policy.lookback_periods + 1)
            if first_kept is not None
            else []
        )
    before = named_trees.measure_days(listing, root, candidate_days)
    candidates = named_trees.visuals_older_than(listing, root, candidate_days)
    sizes: dict[Path, int] = {}
    gone: dict[Path, int] = {}

    def weigh(item: retention_files.Aged) -> None:
        sizes[item.path] = listing.size_of(item.path)

    def count_gone(path: Path) -> None:
        if not path.exists():
            gone[path] = sizes[path]

    outcome = retention_files.take_files(
        context,
        [
            retention_files.Aged(path=path, day="-".join(path.parent.parts[-3:]))
            for path in candidates
        ],
        collection=collection,
        first_kept=first_kept,
        after_delete=count_gone,
        before_delete=weigh,
    )
    after = before - sum(gone.values())
    if after < 0:
        raise ValueError("visual cleanup removed more bytes than its named period window held")
    skipped = len(candidates) - len(outcome.taken)
    window = policy.window
    row = VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=context.today.isoformat(),
        run_id=context.run_id,
        policy_months=(
            -1
            if isinstance(window, ForeverWindow)
            else window.value // 30
            if isinstance(window, DaysWindow)
            else window.value
        ),
        max_deletes_per_run=policy.max_deletes_per_run,
        dry_run=policy.dry_run,
        cutoff_date=first_kept.isoformat() if first_kept else None,
        window_start=candidate_days[0].isoformat() if candidate_days else None,
        window_end=candidate_days[-1].isoformat() if candidate_days else None,
        candidates_found=len(candidates),
        deleted=0 if policy.dry_run else len(outcome.taken),
        skipped_by_fuse=skipped,
        fuse_tripped=skipped > 0,
        bytes_reclaimed=before - after,
        oldest_kept=(
            oldest.isoformat()
            if first_kept is not None
            and (
                oldest := named_trees.oldest_visual(
                    listing, root, first_kept, without=gone
                )
            )
            else None
        ),
        payload_bytes_before=before,
        payload_bytes_after=after,
    )
    reports = ledger.persist(
        context.state_dir,
        [row],
        ledger=LedgerName.VISUAL_PRUNES,
        covers=row.date,
        identity=WriterIdentity(
            run_id=context.run_id,
            attempt=context.attempt,
            job=context.job,
            shard=context.shard,
            producer=__name__.partition(".")[2],
            git_sha=context.git_sha,
        ),
    )
    appended = tuple(path.relative_to(context.repo_root).as_posix() for path in reports)
    return dataclasses.replace(outcome, appended=appended)
