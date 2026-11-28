"""Which days of its own two ledgers does this judge read back, and through which door?

The reads live here and not in `idhazh/ledger/rows.py` because the council's verbs import
that module, and a judge's row contract may not join what a council verb imports: a judge
deleted from the tree has to leave every council verb running
(`backend/tests/council/test_council_runs_without_a_judge.py`).

Each read takes the days its caller names. Nothing here walks a ledger, so what a read costs
is the number of days asked for and never how long the ledger has been filling
(CLAUDE.md Guardrail #12). The night's review names its days once, in `review_days`, and the
collecting job's sparse checkout is told the same days from the same function, so the days a
stage opens and the days that are fetched for it cannot drift apart.

**Two doors, for two questions.** `load_pair_verdicts` asks which rows the ledger holds for
the days, and a day a compact index already names is served from that record. A night the
judge repairs is such a day: the gardener recorded it as quiet before the judge came back to it,
and the rows filed since sit in raw files the index does not look at. `load_pair_verdicts_filed_on`
reads the raw files of one day and nothing else, so the run that has just filed a night's rows
can read them back.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

from idhazh import ledger
from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityJudgeConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.similarity.threshold_evidence import evidence_days
from idhazh.similarity.thresholds_in_force import lookback_days


@dataclass(frozen=True, slots=True)
class ReviewDays:
    """The UTC days of each ledger a night's review reads, oldest first."""

    pair_verdicts: tuple[str, ...]
    threshold_history: tuple[str, ...]
    fit_history: tuple[str, ...]


def review_days(night: str, *, config: ContentSimilarityJudgeConfig) -> ReviewDays:
    """Name the sparse checkout and review windows for the fit and for drift.

    **Guardrail #12 declaration.** Pair verdicts cover `thresholds.effective_max_window_nights`
    ending on the night, bounding both the adaptive evidence window and the sparse checkout.
    History covers the maximum of the draw lookback, the pull window, and the drift lookback,
    all ending before the night. The fit keeps only its original draw and pull days.
    """
    fit_window = max(config.draw.thresholds_lookback_days, config.thresholds.pull_window_nights)
    return ReviewDays(
        pair_verdicts=evidence_days(
            night, window_nights=config.thresholds.effective_max_window_nights
        ),
        threshold_history=lookback_days(
            night, within_days=max(fit_window, config.diagnostics.score_baseline_lookback_days)
        ),
        fit_history=lookback_days(night, within_days=fit_window),
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


def load_pair_verdicts_filed_on(
    state_dir: Path, day: str
) -> list[StorySimilarityPairVerdict]:
    """The pair verdicts filed as raw files for this one UTC day, whatever the indexes say of it.

    **Guardrail #12 declaration.** The fixed-size input is the one day named: the door lists
    that day's raw folder and no other, whatever the ledger holds.

    The run that has just filed a night's rows reads them back here. `load_pair_verdicts`
    would serve a day the gardener already recorded as quiet from that record and never open
    the raw files filed after it, which is what a night the judge repairs is. The rows come
    oldest file first, so the last row of a pair is the newest, and rows of every run of the
    night are here: the caller picks its own run's.
    """
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
    return ledger.load_current_rows(
        state_dir,
        which,
        model=StorySimilarityPairVerdict,
        key=ledger.door_key(which),
        days=[day],
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
