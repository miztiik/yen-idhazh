"""How many days back does the hand-marked holdout look?

The `similarity` block of `config/idhazh.json`. Its one knob is read by the Judgement
route's build-time read in `frontend/src/lib/server/content-similarity-holdout.ts` and by
the marks' retention, which may not delete a day inside it. So a read of the marks opens a
fixed number of days however long the ledger grows (Guardrail #12).
"""

from __future__ import annotations

from pydantic import Field

from idhazh.contracts.base import Model


class SimilarityConfig(Model):
    """How far back a hand mark still counts."""

    holdout_reach_days: int = Field(
        default=730,
        ge=1,
        description=(
            "How many UTC days back from the day a read is about the holdout marks are "
            "read. Both ends are named, so 730 reads 731 days. A mark filed before that "
            "stops counting until a person marks the pair again or widens this. The "
            "marks' compaction may not delete a day inside it."
        ),
    )
