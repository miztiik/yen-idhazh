"""Add this run's accepted pairs to the training window, and roll it.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is not a worker").
"""

from __future__ import annotations

from pathlib import Path

from idhazh import (
    config,
    corpus,
)
from idhazh.stages.common import LOG, _run_dir


def stage_harvest(
    date: str,
    *,
    settings: config.Settings,
    corpus_dir: Path,
    force: bool = False,
) -> int:
    """Add this run's accepted pairs to the training window, and roll it.

    A step in the digest run rather than a workflow of its own, because the only
    place the article text exists is the machine that just read it: `items/` is
    gitignored and travels as a one-day artifact, so a scheduled job with a fresh
    checkout would find an empty directory and harvest nothing, silently, forever.

    It is still a stage that runs alone with a file in and a file out (section 4),
    and it reads the items directory rather than the run plan - the directory is
    the record of what was worked, so the plan is a second artifact that has to be
    present and answers nothing the files do not. That is also what lets
    `data_wrangler.py backfill` replay a finished run from its artifacts alone.

    The cadence lives in `finetune.harvest_every_days` and is decided here rather
    than in a cron line, because `on.schedule` is parsed before any step runs and
    no config value can reach it. Returns the row count the window now holds, and
    zero when the harvest was not due.
    """
    finetune = settings.app.finetune
    meta = corpus.read_meta(corpus_dir)
    if not force and not corpus.harvest_is_due(
        meta, date=date, every_days=finetune.harvest_every_days
    ):
        LOG.info(
            "harvest not due date=%s last=%s every=%s rows=%s",
            date,
            meta.harvested_date,
            finetune.harvest_every_days,
            meta.rows,
        )
        return 0

    written = corpus.harvest(
        corpus_dir,
        corpus.scored_from_items(_run_dir(date) / "items"),
        date=date,
        finetune=finetune,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )
    return written.rows
