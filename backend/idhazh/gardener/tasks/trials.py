"""Which files under the trial trees - the folders under `state/` nothing else claims - are too old?

A trial run exercises production's code path and writes every ledger it would
write, under a folder of its own beside the ledgers. Nothing reads those rows,
so the honest retention is deletion, and the window is about disk and about a
reader who opens `state/` and wonders what a folder is.

This task owns everything else under `state/`: the runner hands it every folder
there that the commit holds and that no ledger family claims and no other task
owns. So a trial renamed since its last run is cleaned like any other, and a
ledger's own tree is never reached. Each file is dated from its path by
`retention.trial_day`, whatever grammar the ledger that wrote it uses; a file
whose path spells no day is kept, and a day after the wake is kept. A trial
tree the pass empties is taken away, root and all, so the count of folders
under `state/` does not only ever rise (Guardrail #12).
"""

from __future__ import annotations

from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener.context import TaskContext
from idhazh.gardener.one_at_a_time import Pass

KIND = TaskKind.RETENTION


def run(context: TaskContext) -> Pass:
    """Take every dated trial file at least the window's days old, tree by tree."""
    from datetime import timedelta

    from idhazh import ledger, retention
    from idhazh.gardener import named_trees, period_inputs, retention_files

    first_kept = retention_files.first_kept_day(
        context.policy.window,
        context.today,
        days_back=lambda days: context.today - timedelta(days=days - 1),
    )
    roots = [context.repo_root / folder for folder in context.owned_folders]
    period_range = context.period_range or period_inputs.scheduled_range(
        "trials", context.policy, context.today
    )
    named_days = (
        set(period_inputs.periods_in_range(period_range)[0])
        if period_range is not None
        else set()
    )

    def aged() -> list[retention_files.Aged]:
        if first_kept is None:
            return []
        found: list[retention_files.Aged] = []
        for root in roots:
            for path in named_trees.files_named(context.listing, root):
                written = retention.trial_day(path.relative_to(root).as_posix())
                if written is not None and written in named_days and written < first_kept:
                    found.append(retention_files.Aged(path=path, day=written.isoformat()))
        return found

    candidates = aged()
    outcome = retention_files.take_files(
        context, candidates, collection=ledger.STATE_DIRNAME, first_kept=first_kept
    )
    if not context.policy.dry_run:
        deleted = [context.repo_root / path for path in outcome.taken]
        for root in roots:
            retention.drop_empty_directories(
                root, (path for path in deleted if path.is_relative_to(root))
            )
    return outcome
