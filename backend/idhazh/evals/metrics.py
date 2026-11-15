"""Compute retained length and pipeline rates, and identify the checker that wrote a row."""

from __future__ import annotations

import re
from typing import Final

from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.evals.hhem import CHUNK_ANCHOR

# The checker bundle changed; the HHEM weights, window and thresholds did not.
METRICS_VERSION: Final = "6"

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.,-]*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\s\n]+")


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def word_count(text: str) -> int:
    return len(words(text))


def compression(summary: str, source: str) -> float:
    """Summary length over source length, not a confidence input."""
    total = word_count(source)
    return word_count(summary) / total if total else 0.0


def extractable_but_unused_rate(
    *, chartable_published: int, chartable_charted: int
) -> float | None:
    """Share of published chartable articles with no rendered chart."""
    if chartable_published <= 0:
        return None
    return (chartable_published - chartable_charted) / chartable_published


def span_integrity_rate(*, items: int, passed: int) -> float | None:
    """Share of articles whose element spans still slice their own characters."""
    if items <= 0:
        return None
    return passed / items


def scorer_version(
    *, scorer_id: str, scorer_revision: str, weights_sha256: str, evaluation: EvaluationConfig
) -> str:
    """Identify the loaded scorer, checker bundle, window geometry and confidence cuts."""
    return ";".join(
        (
            f"{scorer_id}@{scorer_revision[:8]}",
            f"weights-{weights_sha256[:8]}",
            f"metrics-{METRICS_VERSION}",
            f"window={evaluation.chunk_words}/{evaluation.chunk_overlap_words}/{CHUNK_ANCHOR}",
            f"bands={evaluation.band_high_min:.2f}/{evaluation.band_medium_min:.2f}",
        )
    )
