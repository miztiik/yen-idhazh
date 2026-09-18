"""Which merge line does today's build use - the fitted one, or the committed floor?

Pure reading and one `model_copy`. Nothing here fits, damps or clamps: row 8
already did that and wrote the answer down, and a second clamp here would be a
second answer nobody could reconcile with the row.

**The read is bounded by a knob and never by the archive** (Guardrail #12).
`applied_lookback_days` names the days, `day_partition.days_in_window` turns that
into at most `applied_lookback_days + 1` file opens, and the walk stops at the
first row carrying a line. A gap longer than the lookback means the judge has
been down that long, and the committed config value is the honest answer.
"""

from __future__ import annotations

from pathlib import Path

from idhazh import ledger
from idhazh.contracts.fitted_similarity_threshold import HeldReason
from idhazh.contracts.knobs.placement import SameStoryConfig, SimilarityThresholdConfig


def applied_line(
    state_dir: Path, *, date: str, knobs: SimilarityThresholdConfig
) -> float | None:
    """The newest line a fit applied inside the lookback, or `None`.

    `None` on four counts, and every one of them is an ordinary day rather than
    an error: the flag is off, the tree is not there, every row inside the
    lookback was held, or the newest row carries no line. A caller reading `None`
    publishes on `config/idhazh.json`, which is what keeps a fresh clone running
    on the defaults (Guardrail #6).

    A held row is skipped rather than read. It carries yesterday's line in
    `applied` so the column is never empty, and taking that value would make a
    line the evidence refused to move look like a line the evidence chose.
    """
    if not knobs.enabled:
        return None
    rows = ledger.load_fitted_thresholds(
        state_dir, today=date, within_days=knobs.applied_lookback_days
    )
    for row in reversed(rows):
        if row.held_reason is HeldReason.NONE:
            return row.applied
    return None


def effective_same_story(
    same_story: SameStoryConfig,
    *,
    state_dir: Path,
    date: str,
    knobs: SimilarityThresholdConfig | None = None,
) -> SameStoryConfig:
    """The committed block unchanged, or one copy with `floor_min` replaced.

    One `model_copy` and no function signature moves. `collapse_same_story`
    already reads the floor off the value it is handed, so the fitted line
    arrives the same way the committed one always has - which is what makes this
    row revertible by a one-character config edit rather than by a revert commit.

    `knobs` defaults to the block nested inside `same_story`, so production has
    one place the knobs come from. The parameter exists so a test can drive this
    with a built block without building a whole `SameStoryConfig` around it.
    """
    tuning = same_story.adaptive_dedup_threshold if knobs is None else knobs
    line = applied_line(state_dir, date=date, knobs=tuning)
    if line is None:
        return same_story
    return same_story.model_copy(update={"floor_min": line})
