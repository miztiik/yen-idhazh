"""Embed the day's items on the runner, so a browser only ever embeds a query.

The corpus is fixed the moment a day publishes. Embedding it again in every
reader's browser is repeated work for an identical answer, and it forces the
encoder onto readers who never search.

One artifact, two runtimes. The runner and the browser load the **same** ONNX
file from `frontend/public/assist/models/`, so a vector committed by the
pipeline and a query embedded in the tab come from identical weights. The
alternative - torch on the runner, ONNX in the browser - has two sets of weights
that agree until one of them is updated.

The vectors are a rendering. They are regenerable from committed text at any
time, so they carry none of the retention promises that protect the ledger.
"""

from __future__ import annotations

import base64
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from idhazh.contracts.digest_day import DigestItem

EMBEDDER_ID: Final = "all-minilm-l6-v2-quantized"

# Relative to the repository root, and the same file the published page fetches.
# `frontend/static/` rather than `frontend/public/`: the latter is where the
# pipeline writes its payloads, which the site reads at BUILD time through the
# filesystem. Only `static/` is copied into the served bundle, so a vendored
# asset a browser fetches at runtime has to live there. POSIX and digest-free,
# per CLAUDE.md section 2.
MODEL_RELDIR: Final = "frontend/static/assist/models/all-MiniLM-L6-v2"
ONNX_RELPATH: Final = f"{MODEL_RELDIR}/onnx/model_quantized.onnx"
TOKENIZER_RELPATH: Final = f"{MODEL_RELDIR}/tokenizer.json"

# 384 is the encoder's own width. The plan called for 256, which assumes a
# Matryoshka-trained model whose vectors truncate cleanly; MiniLM is not one, so
# truncating would discard a third of the signal to save 128 bytes an item. At
# int8 the full width costs 384 bytes, and a fifteen-item day is under 8 KB of
# base64 inside a payload that is already fetched.
DIMENSIONS: Final = 384
DTYPE: Final = "int8"

# The encoder's own limit. Longer input is truncated rather than rejected: a
# summary that runs long still deserves a vector.
MAX_TOKENS: Final = 256

_SCALE: Final = 127.0


class Embedder:
    """Lazily loaded, because most runs of most stages never embed anything."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._session: Any | None = None
        self._tokenizer: Any | None = None

    @property
    def available(self) -> bool:
        return (self._root / ONNX_RELPATH).exists()

    def load(self) -> None:
        import onnxruntime
        from tokenizers import Tokenizer

        self._session = onnxruntime.InferenceSession(str(self._root / ONNX_RELPATH))
        tokenizer = Tokenizer.from_file(str(self._root / TOKENIZER_RELPATH))
        tokenizer.enable_truncation(max_length=MAX_TOKENS)
        tokenizer.enable_padding()
        self._tokenizer = tokenizer

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Mean-pooled, L2-normalised sentence vectors, in input order."""
        if self._session is None or self._tokenizer is None:
            raise RuntimeError("the embedder was used before it was loaded")
        if not texts:
            return []

        import numpy as np

        encodings = self._tokenizer.encode_batch(texts)
        ids = np.array([item.ids for item in encodings], dtype=np.int64)
        mask = np.array([item.attention_mask for item in encodings], dtype=np.int64)
        hidden = self._session.run(
            None,
            {
                "input_ids": ids,
                "attention_mask": mask,
                "token_type_ids": np.zeros_like(ids),
            },
        )[0]
        weights = mask[..., None].astype(np.float32)
        pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
        normalised = pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None)
        return [row.tolist() for row in normalised]


def text_for(item: DigestItem) -> str:
    """What a reader is actually searching: the headline and what we said about it."""
    return f"{item.title}. {item.summary}"


def quantise(vector: list[float]) -> bytes:
    """int8, because the vectors are unit-length so every component is in [-1, 1].

    Measured 2026-08-22: the round trip preserves cosine similarity to 0.999 on
    real summaries, against a four-fold saving over float32.
    """
    if len(vector) != DIMENSIONS:
        raise ValueError(f"expected {DIMENSIONS} dimensions, got {len(vector)}")
    return bytes((round(max(-1.0, min(1.0, value)) * _SCALE) & 0xFF) for value in vector)


def dequantise(raw: bytes) -> list[float]:
    """Back to a unit vector, so a decoded vector is directly comparable."""
    signed = [(byte - 256 if byte > 127 else byte) / _SCALE for byte in raw]
    length = math.sqrt(sum(value * value for value in signed)) or 1.0
    return [value / length for value in signed]


def to_base64(vector: list[float]) -> str:
    return base64.b64encode(quantise(vector)).decode("ascii")


def from_base64(encoded: str) -> list[float]:
    return dequantise(base64.b64decode(encoded))


def cosine(left: list[float], right: list[float]) -> float:
    """Both sides are unit-length by construction, so this is the dot product."""
    return sum(a * b for a, b in zip(left, right, strict=True))
