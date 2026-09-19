"""Write `state/score-index/` again from the rows it indexes, and say what drifted.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from idhazh import (
    day_partition,
)
from idhazh.evals import writer
from idhazh.stages import common
from idhazh.stages.common import LOG


def stage_rebuild_score_index(
    *, months: Sequence[str] | None, state_dir: Path | None = None
) -> int:
    """Write `state/score-index/` again from the rows it indexes, and say what drifted.

    The operator's repair for an index that stopped describing the rows beside
    it. A fill a crash cut short, a day file a `merge=union` grew behind the
    index's back, or an index left at a grain the ledger no longer uses all read
    as a success today: `evals.writer.refresh_index` only fills a partition with
    no index at all, so a wrong one is never compared against anything and the
    next dedupe silently admits a measurement the ledger already holds.

    **The cover is named in months and the work is done in days.** Both files
    moved to `<YYYY>/<MM>/<DD>.csv` on 2026-09-13, but the thing an operator
    knows is that a month looks wrong, and naming thirty-one days to say so is a
    worse command than naming one month. So `--month` is expanded to that month's
    committed days here and `writer.rebuild_index` is given days - the same split
    the prunes already use, where a `keep_months` knob deletes day files.

    **Never a step of a run, and that is the design rather than an oversight.**
    Rebuilding reads every score row of every day it is given, which is the
    read the index exists to avoid (Guardrail #12), and an index that repaired itself
    on a schedule would hide the drift this exists to reveal. So a person types
    it, and the cover is stated: `--month` names the months to rebuild and
    `--every-shard` is the full pass over the archive. Neither is the default,
    so a caller that named neither gets an error rather than the archive.

    A month with no committed rows exits non-zero rather than reporting a clean
    pass over nothing, and so does a tree with no rows at all - the rule
    `validate-days` and `site-weight` already hold.
    """
    state = state_dir if state_dir is not None else common.STATE_ROOT
    by_month = day_partition.days_by_month(state / writer.LEDGER_DIRNAME)
    named = sorted(by_month) if months is None else sorted({month[:7] for month in months})
    if not named:
        LOG.error(
            "rebuild-score-index found no rows under %s, so no index can be wrong about one",
            writer.LEDGER_RELDIR,
        )
        return 1
    absent = [month for month in named if month not in by_month]
    if absent:
        LOG.error("rebuild-score-index was asked for months that are not committed: %s", absent)
        return 1

    days = [day_partition.date_of(day) for month in named for day in by_month[month]]
    found = writer.rebuild_index(state, days)
    for date, drift in sorted(found.items()):
        LOG.info(
            "index rebuilt file=%s held_the_rows_cannot_produce=%s rows_it_did_not_hold=%s",
            writer.index_relpath(date),
            len(drift.extra),
            len(drift.missing),
        )
    LOG.info(
        "score index rebuilt cover=%s months=%s days=%s drifted=%s",
        "every-shard" if months is None else ",".join(named),
        len(named),
        len(days),
        sum(1 for drift in found.values() if drift.extra or drift.missing),
    )
    return 0
