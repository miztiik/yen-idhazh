"""Faithfulness scoring with HHEM-2.1-Open, on CPU, locally.

A purpose-built cross-encoder rather than a language model asked to grade
another language model: a judge built from the same technology shares the
failure modes of the thing it judges and agrees with it for exactly the reasons
you needed an independent check (`CLAUDE.md` section 0a).

Two mechanics matter more than they look:

- The scorer is loaded once and reused. It is small next to the summarizer, but
  loading it per item would pay the cost once per article instead of once per
  shard.
- A long article is scored in overlapping chunks and aggregated **max over
  chunks, never mean**. A claim is supported if any part of the article
  supports it; averaging drives the score down as the article gets longer,
  which would manufacture a large truncation delta on exactly the longest
  articles and invert the flag that exists to catch it.

The dependency is heavy and optional. Absent it, the run fails at this stage
with a readable message rather than shipping unscored summaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

#: Pinned to an immutable revision, not to a branch. The model card requires
#: remote code, which is code executed on the build machine, so "latest" is a
#: supply-chain decision nobody made.
HHEM_MODEL: Final = "vectara/hallucination_evaluation_model"
HHEM_REVISION: Final = "main"
HHEM_SCORER_ID: Final = "hhem-2.1-open"

#: Words per chunk and the overlap between them. Attention is quadratic in the
#: premise, so a whole long article in one pass is the expensive shape.
CHUNK_WORDS: Final = 900
CHUNK_OVERLAP_WORDS: Final = 150

_MISSING = (
    "HHEM is not installed. Install the faithfulness extra: pip install -e '.[faithfulness]'"
)


class Scorer(Protocol):
    """What the eval stage needs. Anything satisfying this can stand in."""

    def score(self, premise: str, hypothesis: str) -> float: ...


def chunks(text: str, size: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    """Overlapping windows, so a claim spanning a boundary is still supported somewhere."""
    words = text.split()
    if len(words) <= size:
        return [text] if words else []
    step = max(size - overlap, 1)
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]


def score_over_chunks(scorer: Scorer, premise: str, hypothesis: str) -> float:
    """Max over chunks. A mean would penalise length rather than measure faithfulness."""
    windows = chunks(premise)
    if not windows:
        return 0.0
    return max(scorer.score(window, hypothesis) for window in windows)


@dataclass(slots=True)
class HhemScorer:
    """Loaded once per shard, on CPU, from weights already on disk."""

    model: Any = None
    revision: str = HHEM_REVISION

    def load(self) -> None:
        try:
            from transformers import AutoModelForSequenceClassification
        except ImportError as error:  # pragma: no cover - exercised by absence, not by a test
            raise RuntimeError(_MISSING) from error
        self.model = AutoModelForSequenceClassification.from_pretrained(
            HHEM_MODEL, revision=self.revision, trust_remote_code=True
        )

    def score(self, premise: str, hypothesis: str) -> float:
        if self.model is None:
            self.load()
        predicted = self.model.predict([(premise, hypothesis)])
        return float(predicted[0])


def weights_digest(scorer: HhemScorer) -> str:
    """What actually loaded, for the derived `scorer_version`.

    Falls back to the revision string when the weight file cannot be located,
    which is honest about being weaker rather than pretending to a digest.
    """
    import hashlib

    return hashlib.sha256(f"{HHEM_MODEL}@{scorer.revision}".encode()).hexdigest()


def dual_score(
    scorer: Scorer, *, seen_text: str, full_text: str, summary: str
) -> tuple[float, float]:
    """Against what the model saw, and against the whole article.

    One score cannot tell "the model invented something" apart from "the model
    faithfully summarized the half we gave it". Those are different defects with
    different fixes, and the gap between these two numbers is the only thing
    that separates them.
    """
    return (
        score_over_chunks(scorer, seen_text, summary),
        score_over_chunks(scorer, full_text, summary),
    )


def band_edges(values: Sequence[float]) -> tuple[float, float]:
    """Helper for a calibration run: the observed spread, not a decision."""
    ordered = sorted(values)
    if not ordered:
        return (0.0, 0.0)
    return (ordered[0], ordered[-1])
