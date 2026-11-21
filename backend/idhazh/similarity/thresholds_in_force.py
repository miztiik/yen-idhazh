"""Which two thresholds does a night's draw follow?

The newest threshold-history row dated before the night and inside the lookback sets them,
and with no such row the configured starts do. The night's own pair-verdict rows record what
this answered, so the answer is on the data it shaped.

Nothing here reads a ledger or a config file. The caller names the days to read with
`lookback_days`, reads them, and hands the rows back.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import timedelta

from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)


@dataclass(frozen=True, slots=True)
class ThresholdsInForce:
    """The lower and the upper bound threshold a night follows, unrounded."""

    lower: float
    upper: float
    #: The UTC day of the row that set them, empty when the configured starts did.
    set_on: str | None
    #: The row that set them, so whoever needs more than the two thresholds from it reads the
    #: row the draw read and not a second answer to "which row is newest". Left out of equality:
    #: two nights that follow the same thresholds follow the same thresholds.
    row: StorySimilarityThresholdHistoryRow | None = field(default=None, compare=False)


def lookback_days(night: str, *, within_days: int) -> tuple[str, ...]:
    """The `within_days` UTC days before `night`, oldest first, which are the days to read.

    **Guardrail #12 declaration.** The fixed-size input is `within_days`, a named setting,
    so the read costs the same on the thousandth night as on the third.
    """
    start = date_type.fromisoformat(night)
    return tuple(
        (start - timedelta(days=back)).isoformat() for back in range(within_days, 0, -1)
    )


def council_run_order(run_id: str) -> tuple[str, int]:
    """Compare Council runs by UTC prefix, then by numeric run suffix."""
    day, _, number = run_id.rpartition("-")
    return day, int(number)


def thresholds_in_force(
    history: Sequence[StorySimilarityThresholdHistoryRow],
    *,
    night: str,
    within_days: int,
    lower_start: float,
    upper_start: float,
) -> ThresholdsInForce:
    """The `threshold_after` columns of the newest row before `night`, else the starts.

    A row of the night itself or of a later night is never followed, so a re-run of a night
    starts from the place its first run started from. When one day holds two rows, two runs
    of that night, the one filed last is the newest, which is the order the ledger door
    returns them in.
    """
    first = (date_type.fromisoformat(night) - timedelta(days=within_days)).isoformat()
    earlier = sorted(
        (row for row in history if first <= row.date < night), key=lambda row: row.date
    )
    if not earlier:
        return ThresholdsInForce(lower=lower_start, upper=upper_start, set_on=None)
    newest = earlier[-1]
    return ThresholdsInForce(
        lower=newest.lower_threshold_after,
        upper=newest.upper_threshold_after,
        set_on=newest.date,
        row=newest,
    )
