"""One typed name per committed ledger under `state/`.

What each ledger answers and why it files at the grain it does is
`docs/architecture/contracts/state-ledgers.md`. This page of the contract graph
says only which ledgers there are, so nothing here depends on where a file is
put or how its rows are read.
"""

from __future__ import annotations

from enum import UNIQUE, StrEnum, verify


@verify(UNIQUE)
class LedgerName(StrEnum):
    """Which ledger under `state/` a caller means. A closed set, and that is the point.

    One name for one ledger, so the directory a writer fills, the directory a
    reader walks and the word an operator types cannot be spelled three ways. A
    A ledger joins this set with its row contract and reader registration, before
    its writer emits rows. The reader can then accept the declared shape before
    any producer starts writing it.

    **A value is the ledger's own name, never a filename.** Where the ledger is a
    directory the value is that directory. Where it is a single file the value is
    the stem with no extension, because the extension is a separate fact about
    the file and a second spelling of it can disagree with the first.

    **A value is one segment, and the nest above it is not part of it.** Several
    of these sit under `content-similarity-judge/`. Where a
    ledger lives is the path builder's answer; this is only its name.

    **The Python name is spelled from the value and the family, and nothing
    else.** A ledger that is its own family is its value in upper snake case:
    `feed-health` is `FEED_HEALTH`. A ledger inside a family puts the family
    first: `metrics` under `content-similarity-judge` is
    `CONTENT_SIMILARITY_JUDGE_METRICS`. The registry refuses a member that
    breaks the rule when it loads, because a Python name that says something the
    value does not is a second name a reader has to learn.

    Two members may not share a value. An enum takes a repeated value as an alias
    and says nothing, and two ledgers reading back as one name is a row filed
    into the wrong tree, so the repeat is refused when this module loads.
    """

    SEEN = "seen"
    FEED_HEALTH = "feed-health"
    ITEM_HEALTH = "item-health"
    HOST_FINGERPRINT = "host-fingerprint"
    SUMMARY_QUALITY_EVALS = "summary-quality-evals"
    ITEM_HEALTH_SUMMARY = "item-health-summary"
    PUBLISHED = "published"
    FEED_RETIREMENTS = "feed-retirements"
    VISUAL_PRUNES = "visual-prunes"
    COUNTERFACTUAL_SCORES = "counterfactual-scores"
    CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS = "scored-pairs"
    CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS = "fitted-thresholds"
    CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS = "holdout-pairs"
    CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION = "score-distribution"
    CONTENT_SIMILARITY_JUDGE_ARCHIVE = "archive"
    CONTENT_SIMILARITY_JUDGE_METRICS = "metrics"
    CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES = "merge-line-holdout-scores"
    TRACES = "traces"
    DAY_METRICS = "day-metrics"
    DIGEST_FRAGMENTS = "digest-fragments"
    GARDENER = "gardener"
    RUN_PLAN = "run-plan"
    RUN_SHARDS = "run-shards"
    COUNCIL_RUN_RECORDS = "council-run-records"
    FEED_INGEST_PLAN_EDITORIAL_SELECTIONS = "editorial-selections"
    FEED_INGEST_PLAN_DISPATCHES = "dispatches"
    FEED_INGEST_PLAN_REJECTIONS = "rejections"
    FEED_INGEST_PLAN_SOURCE_RUNS = "source-runs"
    FEED_INGEST_PLAN_ARTICLE_ASSESSMENTS = "article-assessments"
    FEED_INGEST_PLAN_DIVERSITY = "diversity"
    FEED_INGEST_PLAN_DOCUMENT_OBSERVATIONS = "document-observations"
