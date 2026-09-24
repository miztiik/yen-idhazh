"""Does the summary read as connected prose, measured with the sentence encoder.

The one measure in `evals/` that needs a model to compute, which is why it is
not in `metrics.py` - that file's first paragraph promises its counterweights
are model-free and run even when no scorer fits the runner.

It is also the only measure that reads the summary against ITSELF at the level
of meaning. Every other column compares the summary to the article, and a
summary of five true sentences that do not follow one another scores perfectly
on all of them.

Recorded only. It is a poor thing to gate on and always will be: a summary that
says the same sentence twice reads as maximally coherent, so the failure it is
blindest to is one `self_repetition` already names.
"""

from __future__ import annotations

import re
from itertools import pairwise
from typing import Protocol

#: Sentence boundaries, spelled the way `evals.metrics` spells them. A copy and
#: not an import: this module may grow a boundary rule of its own - an encoder
#: reads a fragment differently from a counter of four-grams - and the two files
#: agreeing today is not a reason for one to own the other's definition.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[\s\n]+")

#: Fewer sentences than this and there is no neighbouring pair to compare.
_PAIR = 2


class Encoder(Protocol):
    """Whatever turns sentences into unit vectors, in input order.

    A protocol rather than `idhazh.embed.Embedder` so this module states what it
    needs rather than what production happens to hand it, and so a test can
    drive it with vectors it wrote down.
    """

    def encode(self, texts: list[str]) -> list[list[float]]: ...


def sentences(summary: str) -> list[str]:
    """The summary's sentences, empty ones dropped.

    A blank fragment is not a sentence, and encoding one would put a vector of
    whatever the encoder does with nothing between two real ones.
    """
    return [line for line in (part.strip() for part in _SENTENCE_SPLIT.split(summary)) if line]


def mean_adjacent_cosine(vectors: list[list[float]]) -> float | None:
    """The mean dot product of each neighbouring pair, or None below two vectors.

    A dot product rather than a full cosine because the caller hands over unit
    vectors - `Embedder.encode` L2-normalises every one it returns - so dividing
    by two lengths of 1.0 is arithmetic that can only lose bits.

    Split out from `coherence` so the arithmetic can be checked against numbers
    a person wrote down, with no model in the room.
    """
    if len(vectors) < _PAIR:
        return None
    products = [
        sum(left * right for left, right in zip(one, two, strict=True))
        for one, two in pairwise(vectors)
    ]
    return sum(products) / len(products)


def coherence(summary: str, *, encoder: Encoder) -> float | None:
    """How connected the summary reads, on the encoder's own -1 to 1 scale.

    None when the summary holds fewer than two sentences. That is a real and
    different answer from a low score: one sentence cannot fail to follow the
    one before it, and 0.0 would claim a measurement nothing took.

    Raw rather than rescaled to 0-to-1, so the number stays the cosine a reader
    can recompute from two vectors.

    **One sequence per forward pass, which is `Embedder.encode`'s contract and
    not an accident of this call.** The encoder is dynamically quantised, so a
    batch sets the activation range every sentence in it is measured against -
    batching these to save time would make a summary's score depend on how many
    sentences it had.
    """
    parts = sentences(summary)
    if len(parts) < _PAIR:
        return None
    return mean_adjacent_cosine(encoder.encode(parts))
