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

Regenerable only helps if a regeneration lands on the same bytes, so the
arithmetic is pinned rather than hoped for: one thread, sequential execution,
one sequence per forward pass, and no padding. A vector is then a function of
its own text and the weights - not of the host's core count, and not of which
items happened to share its batch.
"""

from __future__ import annotations

import base64
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from idhazh.contracts.digest_day import DigestItem

EMBEDDER_ID: Final = "all-minilm-l6-v2-quantized"

# The date PROVENANCE.md records these weights were fetched, carried in the path
# the browser loads them from. Different weights are then a different URL, so a
# cached copy of the old encoder can never answer vectors the new one wrote.
# Moving it costs every returning searcher the whole download again, so it moves
# when the weights move and at no other time. The browser's copy is
# `ENCODER_VERSION` in `frontend/src/lib/assist/encoder.ts`.
ENCODER_VERSION: Final = "2026-08-22"

# Relative to the repository root, and the same directory the published page
# fetches. `frontend/static/` rather than `frontend/public/`: the latter is where
# the pipeline writes its payloads, which the site reads at BUILD time through
# the filesystem. Only `static/` is copied into the served bundle, so a vendored
# asset a browser fetches at runtime has to live there. Built from the two
# constants above so the path cannot disagree with the identifier it serves.
# POSIX and digest-free, per CLAUDE.md section 2.
MODEL_RELDIR: Final = f"frontend/static/assist/models/{EMBEDDER_ID}/{ENCODER_VERSION}"
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
# summary that runs long still deserves a vector. It is also the browser's cap,
# because a query read further than the items it is matched against is a
# different question. Row #8 of the plan moves this into `config/`; the browser
# twin is `MAX_TOKENS` in `frontend/src/lib/assist/loader.ts`.
MAX_TOKENS: Final = 256

_SCALE: Final = 127.0


def session_options() -> Any:
    """The pinned arithmetic, in one place so a test reads the object `load` uses.

    Contract, not configuration. Float addition is not associative, so the
    thread count picks the order the partial sums accumulate in - and left
    alone onnxruntime takes that count from the host's cores. A knob here is a
    way for a vector to start depending on the machine that made it.
    """
    import onnxruntime

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
    return options


def build_tokenizer(root: Path) -> Any:
    """Truncated at the cap and padded to nothing, which is what the browser does.

    Padding is not free of meaning here. The encoder is dynamically quantised,
    so a pad token's own activations widen the range every real token is then
    measured against. Measured 2026-08-25 (Windows 11, 8 vCPU, onnxruntime
    1.29.0): padding one sentence out to the 256-token cap moves its vector by
    up to 1.6e-2 per component. The browser pads a lone query to nothing, so the
    runner does too.
    """
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(root / TOKENIZER_RELPATH))
    tokenizer.enable_truncation(max_length=MAX_TOKENS)
    tokenizer.no_padding()
    return tokenizer


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

        # Naming the provider stops a machine with a second one installed from
        # quietly answering with different kernels.
        self._session = onnxruntime.InferenceSession(
            str(self._root / ONNX_RELPATH),
            session_options(),
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = build_tokenizer(self._root)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Mean-pooled, L2-normalised sentence vectors, in input order.

        One sequence per forward pass, whatever the caller hands over. That is
        the whole determinism story: a dynamically quantised encoder reads its
        activation scales off the tensor it is given, so sixteen sentences in
        one call each set the range the other fifteen are measured against.
        Measured 2026-08-25 (Windows 11, 8 vCPU, onnxruntime 1.29.0): two
        batches of sixteen that shared one sentence disagreed about it by up to
        1.5e-2 per component, which survives the int8 round trip and lands in
        the committed bytes.
        """
        if self._session is None or self._tokenizer is None:
            raise RuntimeError("the embedder was used before it was loaded")

        import numpy as np

        vectors: list[list[float]] = []
        for text in texts:
            encoding = self._tokenizer.encode(text)
            ids = np.array([encoding.ids], dtype=np.int64)
            mask = np.array([encoding.attention_mask], dtype=np.int64)
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
            unit_length = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9, None)
            vectors.append((pooled / unit_length)[0].tolist())
        return vectors


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
