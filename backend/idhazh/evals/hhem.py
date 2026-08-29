"""Faithfulness scoring with HHEM-2.1-Open, on CPU, locally.

A purpose-built cross-encoder rather than a language model asked to grade
another language model: a judge built from the same technology shares the
failure modes of the thing it judges and agrees with it for exactly the reasons
you needed an independent check (`CLAUDE.md` section 0a).

Three mechanics matter more than they look:

- The scorer is loaded once and reused. It is small next to the summarizer, but
  loading it per item would pay the cost once per article instead of once per
  shard.
- A long article is scored in overlapping windows and aggregated **max over
  windows, never mean**. A claim is supported if any part of the article
  supports it; averaging drives the score down as the article gets longer,
  which would manufacture a large truncation delta on exactly the longest
  articles and invert the flag that exists to catch it.
- **Every window is the same size, the last one included.** The last window is
  anchored to the end of the premise instead of being whatever the walk had
  left over. A max over windows compares them against each other, so a runt
  window is a rival that was never given the same premise to work with.

The dependency is heavy and optional. Absent it, the run fails at this stage
with a readable message rather than shipping unscored summaries.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

from idhazh.contracts.app_config import EvaluationConfig

#: Pinned to an immutable revision, not to a branch. The model card requires
#: remote code, which is code executed on the build machine, so "latest" is a
#: supply-chain decision nobody made.
#:
#: This was the literal string `main` until 2026-08-26, which is the branch and
#: not a revision - it moved on 2025-10-20 and could move again tonight. The
#: value below is the revision `main` resolved to when it was read from the
#: Hugging Face model API on 2026-08-26. A faithfulness floor measured against
#: a branch measures an instrument nobody can name afterwards (Rule #10).
HHEM_MODEL: Final = "vectara/hallucination_evaluation_model"
HHEM_REVISION: Final = "8e4a2e6e96c708cc76c2344f7e4757df2515292c"
HHEM_SCORER_ID: Final = "hhem-2.1-open"

#: A revision is immutable when it is a full 40-character git object name. A
#: branch or a tag is not: it names wherever that pointer happens to be today.
_IMMUTABLE_REVISION: Final = re.compile(r"^[0-9a-f]{40}$")

#: How the last window is placed. `metrics.scorer_version` spells this beside the
#: window size, so a ledger row records the geometry that produced it.
#:
#: A code constant and not a config knob (Rule #6 is about tunables). The window
#: size and the overlap are numbers an operator can reasonably move; "should the
#: last window be the same size as the others" is not a question anyone answers
#: twice.
CHUNK_ANCHOR: Final = "anchored"

_MISSING = "HHEM is not installed. Install the faithfulness extra: pip install -e '.[faithfulness]'"


class Scorer(Protocol):
    """What the eval stage needs. Anything satisfying this can stand in."""

    def score(self, premise: str, hypothesis: str) -> float: ...


def chunks(text: str, size: int, overlap: int) -> list[str]:
    """Overlapping windows of exactly `size` words, the last one ending on the last word.

    Overlap is why a claim spanning a boundary is still supported somewhere.
    Anchoring is why the tail of an article is read the same way as the middle.

    Until 2026-08-28 the walk stepped past the end and the final window was
    whatever remained. That window was short on **every** premise longer than
    one window - 3,100 of 3,100 lengths from 901 to 4,000 words, as little as
    one word and 370 words on average against 900-word rivals. The aggregation
    is a max, so a partial premise competed with full ones on every long
    article.

    Anchoring also drops a window where the leftover was small, though not at
    today's lengths: an article at the 1,923-word cap takes 3 windows either
    way. At 3,846 words it is 6 windows before and 5 after, which is 16.7
    percent less scorer work - a saving that arrives when the cap does.
    """
    words = text.split()
    if len(words) <= size:
        return [text] if words else []
    step = max(size - overlap, 1)
    starts = list(range(0, len(words) - size + 1, step))
    if starts[-1] + size < len(words):
        starts.append(len(words) - size)
    return [" ".join(words[start : start + size]) for start in starts]


def score_over_chunks(
    scorer: Scorer, premise: str, hypothesis: str, *, evaluation: EvaluationConfig
) -> float:
    """Max over windows. A mean would penalise length rather than measure faithfulness."""
    windows = chunks(premise, evaluation.chunk_words, evaluation.chunk_overlap_words)
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


def is_pinned(revision: str = HHEM_REVISION) -> bool:
    """Whether the scorer revision names bytes rather than a moving pointer."""
    return bool(_IMMUTABLE_REVISION.fullmatch(revision))


def weights_digest(scorer: HhemScorer) -> str:
    """The weights that loaded, digested tensor by tensor.

    Until 2026-08-26 this hashed the string `name@revision`, which is the label
    the loader was handed and not the bytes it came back with - two different
    checkpoints behind one branch name produced one digest, and the derived
    `scorer_version` said the instrument had not changed. It now walks the
    loaded state dict in key order and digests the actual parameter bytes, so
    the value is an observation (Rule #10).

    Raises when nothing is loaded. A scorer that cannot name its own weights
    cannot support a faithfulness gate, and a fallback string here is what let
    that be true quietly for four months.
    """
    if scorer.model is None:
        raise RuntimeError(
            "the scorer has not loaded, so there are no weights to digest; "
            "call HhemScorer.load() first"
        )
    digest = hashlib.sha256()
    state = scorer.model.state_dict()
    for name in sorted(state):
        tensor = state[name].detach().to("cpu").contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tensor.dtype).encode("utf-8"))
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def dual_score(
    scorer: Scorer,
    *,
    seen_text: str,
    full_text: str,
    summary: str,
    evaluation: EvaluationConfig,
) -> tuple[float, float]:
    """Against what the model saw, and against the whole article.

    One score cannot tell "the model invented something" apart from "the model
    faithfully summarized the half we gave it". Those are different defects with
    different fixes, and the gap between these two numbers is the only thing
    that separates them.

    Identical texts are scored once and the result reused. The scorer is
    deterministic, so the second pass could only ever return the first answer,
    and about 97 percent of items are never truncated. Measured on
    `ubuntu-latest` 2026-08-26, run `2026-08-26-5`: one pass over a 900-word
    chunk takes 2.88 to 3.08 s (n=5), so the pass this skips is worth roughly
    2 s an item.
    """
    seen = score_over_chunks(scorer, seen_text, summary, evaluation=evaluation)
    if seen_text == full_text:
        return (seen, seen)
    return (seen, score_over_chunks(scorer, full_text, summary, evaluation=evaluation))


def band_edges(values: Sequence[float]) -> tuple[float, float]:
    """Helper for a calibration run: the observed spread, not a decision."""
    ordered = sorted(values)
    if not ordered:
        return (0.0, 0.0)
    return (ordered[0], ordered[-1])
