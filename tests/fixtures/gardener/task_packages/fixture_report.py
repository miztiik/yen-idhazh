"""What does a fixture task that files a report of its own write, and what does it hand back?

One visual-prunes row through the ledger door, under the day it is told to
cover, dry run or not - the same kind of write the shipped visual-prune task
makes, with nothing walked, so a runner test holds the report and nothing else.
"""

from __future__ import annotations

import dataclasses
from datetime import date

from idhazh import ledger
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.gardener import retention_files
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass


def file_report(context: TaskContext, *, producer: str, covers: date) -> Pass:
    row = VisualPruneRow(
        version=VisualPruneRow.schema_version(),
        date=covers.isoformat(),
        run_id=context.run_id,
        policy_months=-1,
        max_deletes_per_run=200,
        dry_run=context.policy.dry_run,
        cutoff_date=None,
        candidates_found=0,
        deleted=0,
        skipped_by_fuse=0,
        fuse_tripped=False,
        bytes_reclaimed=0,
        oldest_kept=None,
        payload_bytes_before=0,
        payload_bytes_after=0,
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
            producer=producer,
            git_sha=context.git_sha,
        ),
    )
    walked = retention_files.take_files(
        context, (), collection=context.owned_folders[0], first_kept=None
    )
    return dataclasses.replace(
        walked,
        appended=tuple(path.relative_to(context.repo_root).as_posix() for path in reports),
    )
