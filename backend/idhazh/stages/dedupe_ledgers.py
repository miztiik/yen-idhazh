"""Settle the keyed ledgers after a merge, and print what it dropped.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is not a worker").
"""

from __future__ import annotations

from pathlib import Path

from idhazh import (
    ledger,
)
from idhazh.evals import writer
from idhazh.stages import common
from idhazh.stages.common import LOG


def stage_dedupe_ledgers(*, state_dir: Path | None = None, date: str | None) -> int:
    """Settle the keyed ledgers after a merge, and print what it dropped.

    The one thing an appending stage cannot do for itself. Each of those stages
    filters what it is about to write against the file it checked out, and
    `actions/checkout` pins a job to the commit its run was triggered at - so a
    second attempt at the same work cannot see the rows the first attempt pushed
    afterwards, appends them again, and `merge=union` concatenates both sides.
    The result is a file whose key repeats, which is the one shape every reader
    of it assumes cannot happen.

    So this runs where the frozen snapshot cannot reach: after the merge, on the
    merged file, which is the only artefact that has ever held both sides at
    once. `.github/scripts/commit-and-push.sh` calls it there through
    `DROP_REPEATED_ROWS_COMMAND`, between the rebase and the push.

    **`date` names the run, and that is the whole cover.** A run appends only to
    the file its own date routes to, so a repeat the merge left can only be in a
    file this run wrote - and the ordinary pass reads six files whether the
    archive holds one day or a thousand. It used to glob every feed-health shard,
    every item-health partition and every score shard, which charged each run for
    every month the pipeline had ever recorded and found nothing, because a
    finished partition was settled when it was written and cannot change again
    (Guardrail #12).

    **`date=None` is the operator's full pass, and it is the one that pays for
    the history.** What the bounded pass gives up is an earlier run whose settle
    step itself failed: no later run writes that day, so nothing sweeps the
    repeat up in passing any more. `idhazh dedupe-ledgers --every-shard` is the
    command a person runs to clear it, and it is deliberately a command rather
    than a default - an unbounded read is a decision somebody takes out loud.

    Every ledger that declares what makes two of its rows the same record is
    settled here. `state/seen/` declares nothing and is left alone - see
    `ledger.keyed_paths`. Feed-health is the one whose repeats can disagree, so
    it is the one settled by a rule rather than by arrival order; the rule is in
    `contracts.feed_health.supersedes` and travels with the key.

    It always returns 0. A repeat it drops is a repair, not a finding, and a
    non-zero exit here would abort the commit step that called it and cost the
    run every ledger row staged beside the one it just fixed.
    """
    state = state_dir if state_dir is not None else common.STATE_ROOT
    scores: list[tuple[Path, tuple[str, ...]]] = (
        [(writer.ledger_path(state, date), writer.OBSERVATION_KEY)]
        if date is not None
        else [(day, writer.OBSERVATION_KEY) for day in writer.ledger_days(state)]
    )
    targets: list[tuple[Path, tuple[str, ...]]] = [
        *ledger.keyed_paths(state, date=date),
        *scores,
    ]
    total = 0
    for path, key in targets:
        dropped = ledger.drop_repeated_rows(path, key)
        total += dropped
        if dropped:
            LOG.info(
                "dropped repeated rows file=%s key=%s rows=%s",
                path.name,
                "+".join(key),
                dropped,
            )
    LOG.info(
        "ledgers settled cover=%s files=%s repeated_rows_dropped=%s",
        date or "every-shard",
        len(targets),
        total,
    )
    return 0
