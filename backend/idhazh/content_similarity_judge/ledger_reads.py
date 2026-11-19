"""Which days of its own two ledgers does this judge read back, and through which door?

The reads live here and not in `idhazh/ledger/rows.py` because the council's verbs import
that module, and a judge's row contract may not join what a council verb imports: a judge
deleted from the tree has to leave every council verb running
(`backend/tests/council/test_council_runs_without_a_judge.py`).

Each read takes the days its caller names. Nothing here walks a ledger, so what a read costs
is the number of days asked for and never how long the ledger has been filling
(CLAUDE.md Guardrail #12).
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)


def load_pair_verdicts(
    state_dir: Path, days: Collection[str]
) -> list[StorySimilarityPairVerdict]:
    """These UTC days' pair verdicts, read through the ledger door, oldest day first.

    **Guardrail #12 declaration.** The fixed-size input is the list of days the caller
    names, which is the number of nights the evidence reads and no more. For each day the
    door opens the three compact indexes, the one compact file that serves it, and the raw
    files of the days no index names. The ledger is never walked, so the read costs the
    same on the thousandth night as on the third.

    Each day is settled on its own by the ledger's key, so two runs of one night keep their
    own rows. Within a day the rows come in the order the door filed them, so the last row
    of a date is the newest, and there is no timestamp column to say otherwise. A file this
    build cannot read is skipped with a warning naming it, the way the door reads every
    ledger, so a short window is said in the log rather than read as a quiet one. A day
    nothing was filed for is not a fault.
    """
    return ledger.load_days(
        state_dir,
        LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS,
        days,
        model=StorySimilarityPairVerdict,
    )


def load_threshold_history(
    state_dir: Path, days: Collection[str]
) -> list[StorySimilarityThresholdHistoryRow]:
    """These UTC days' threshold rows, read through the ledger door, oldest day first.

    **Guardrail #12 declaration.** The fixed-size input is the list of days the caller
    names, for the reason `load_pair_verdicts` gives: the door opens only the indexes and
    files that serve those days.

    A night nothing was filed for has no row, which is not a fault. Two runs of one night
    both keep their row, and within a day the rows come in the order the door filed them, so
    the last row of a date is the newest. A file this build cannot read is skipped with a
    warning naming it.
    """
    return ledger.load_days(
        state_dir,
        LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
        days,
        model=StorySimilarityThresholdHistoryRow,
    )
