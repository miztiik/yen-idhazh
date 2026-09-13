"""Record that `prune.yml` ran today, so tomorrow's check does not fire again.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is not a worker").
"""

from __future__ import annotations

from pathlib import Path

from idhazh import (
    corpus,
)
from idhazh.stages.common import LOG


def stage_prune_stamp(*, corpus_dir: Path, date: str) -> int:
    """Record that `prune.yml` ran today, so tomorrow's check does not fire again.

    Separate from the squash itself, which is git surgery and belongs in the
    workflow. What this owns is the one piece of durable state that turns a
    force-push a day into a force-push a month.
    """
    meta = corpus.stamp_prune(corpus_dir, date=date)
    LOG.info("prune stamped date=%s rows=%s", meta.pruned_date, meta.rows)
    return 0
