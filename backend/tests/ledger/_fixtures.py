"""Which named recorded rows do the ledger round-trip and lifecycle tests use?"""

from __future__ import annotations

from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.contracts.base import Contract

FIXTURE_NAMES = {
    "collection-prune-row": (
        "a-compaction-that-recovered-three-periods.json",
        "a-dry-walk-that-counted-past-its-ceiling.json",
        "a-live-fold-beside-a-dry-window.json",
        "a-live-walk-past-a-member-github-kept.json",
        "a-pass-github-did-not-answer.json",
        "ceiling-reached.json",
        "exhausted-dry-run.json",
    ),
    "content-similarity-judge-merge-line-holdout-score": (
        "a-holdout-retention-has-eaten-into.json",
        "a-line-scored-against-the-holdout.json",
    ),
    "content-similarity-judge-metrics": (
        "a-shard-that-read-its-pairs.json",
        "a-shard-that-was-dealt-nothing.json",
    ),
    "council-run-record": (
        "a-part-that-ran-the-model.json",
        "a-selection-that-ran-no-model.json",
        "a-migrated-count-that-had-nothing-to-do.json",
    ),
    "day-metrics": ("full.json", "with-label-similarity.json"),
    "eval-row": (
        "determinism-violation.json",
        "high.json",
        "low-invented-number.json",
        "premise-recorded.json",
        "truncation-artifact.json",
    ),
    "feed-health-row": ("answered.json", "unreachable.json"),
    "feed-retirement-row": ("answered-and-never-read.json", "gone.json"),
    "fitted-similarity-threshold": (
        "the-clamp-held-a-fall-back-to-the-step.json",
        "the-record-is-too-small-to-fit-on.json",
    ),
    "host-fingerprint-row": (
        "a-machine-that-reported-nothing.json",
        "every-reading-taken.json",
        "the-clock-a-job-kept.json",
    ),
    "published-row": ("one-item.json",),
    "seen-row": ("first-sight.json",),
    "story-similarity-pair": (
        "a-headline-match-scores-one.json",
        "judged-the-same-in-both-orders.json",
        "scored-but-not-yet-judged.json",
    ),
    "visual-prune-row": ("fuse-tripped.json", "policy-off.json"),
}


def fixture_rows[M: Contract](model: type[M]) -> list[M]:
    """Read the named examples inside the test, never discover new fixture files."""
    directory = CONTRACT_FIXTURES_DIR / model.__schema_stem__
    return [
        model.from_json(read_text(directory / name))
        for name in FIXTURE_NAMES[model.__schema_stem__]
    ]
