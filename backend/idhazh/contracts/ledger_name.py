"""One typed name per committed ledger under `state/`.

What each ledger answers and why it files at the grain it does is
`docs/architecture/contracts/state-ledgers.md`. This page of the contract graph
says only which ledgers there are and which of them a writer files a segment
into, so nothing here depends on where a file is put or how its rows are read.
"""

from __future__ import annotations

from enum import UNIQUE, StrEnum, verify
from typing import Final


@verify(UNIQUE)
class LedgerName(StrEnum):
    """Which ledger under `state/` a caller means. A closed set, and that is the point.

    One name for one ledger, so the directory a writer fills, the directory a
    reader walks and the word an operator types cannot be spelled three ways. A
    ledger joins this set in the change that gives it a writer, never before one.

    **A value is the ledger's own name, never a filename.** Where the ledger is a
    directory the value is that directory. Where it is a single file the value is
    the stem with no extension, because the extension is a separate fact about
    the file and a second spelling of it can disagree with the first.

    **A value is one segment, and the nest above it is not part of it.** Several
    of these sit under `content-similarity-judge/` or `llm-council/`. Where a
    ledger lives is the path builder's answer; this is only its name.

    Two members may not share a value. An enum takes a repeated value as an alias
    and says nothing, and two ledgers reading back as one name is a row filed
    into the wrong tree, so the repeat is refused when this module loads.
    """

    SEEN = "seen"
    HEALTH = "feed-health"
    ITEM_HEALTH = "item-health"
    HOST_FINGERPRINT = "host-fingerprint"
    SCORES = "scores"
    SCORE_INDEX = "score-index"
    VALIDATION = "validation"
    TELEMETRY_AGGREGATE = "telemetry-aggregate"
    SPAN_ROLLUP = "span-rollup"
    PUBLISHED = "published"
    FEED_RETIREMENTS = "feed-retirements"
    VISUAL_PRUNES = "visual-prunes"
    COUNTERFACTUAL_SCORES = "counterfactual-scores"
    SCORED_PAIRS = "scored-pairs"
    FITTED_THRESHOLDS = "fitted-thresholds"
    SIMILARITY_HOLDOUT = "holdout-pairs"
    SCORE_DISTRIBUTION = "score-distribution"
    SCORE_ARCHIVE = "archive"
    SHARD_OUTCOMES = "shard-outcomes"
    JUDGE_METRICS = "metrics"
    MERGE_LINE_HOLDOUT_SCORES = "merge-line-holdout-scores"


#: The ledgers a writer files its own segment into, one file per writer under
#: `<ledger>/<YYYY>/<MM>/<DD>/`. The subset exists because only these carry a
#: settlement shape - what makes two of their rows one record - so a segment call
#: naming any other ledger is a wrong call and is refused by name.
DAY_TREES: Final[frozenset[LedgerName]] = frozenset(
    {
        LedgerName.ITEM_HEALTH,
        LedgerName.HOST_FINGERPRINT,
        LedgerName.SPAN_ROLLUP,
        LedgerName.SCORES,
        LedgerName.SCORE_INDEX,
        LedgerName.VALIDATION,
        LedgerName.HEALTH,
        LedgerName.COUNTERFACTUAL_SCORES,
    }
)
