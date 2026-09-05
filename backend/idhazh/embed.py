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
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from idhazh.contracts.app_config import AssistConfig

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

# The cap a run uses when nobody configured one, read off the contract so the
# number exists once. The knob is `assist.max_tokens`; it is not a safety guard
# but a statement of how far into an item the encoder reads, and the encoder's
# own position table stops it at 512. Measured 2026-08-26 over the 1886 embedded
# items of the six committed days: p95 is 217 tokens, so 256 reads 99.95 percent
# of everything published. `Embedder` takes the configured cap rather than this
# line, so this is a default and not the number a run truncates at. The browser
# twin is `MAX_TOKENS` in `frontend/src/lib/assist/loader.ts`, and
# `backend/tests/test_embed.py` pins it to the configured cap - to what ships,
# not to this line.
MAX_TOKENS: Final = AssistConfig().max_tokens

_SCALE: Final = 127.0

# What a stored byte is multiplied by to get a component. The published month
# index states it in its header rather than letting a reader assume it
# (`idhazh/contracts/search_index.py`).
VECTOR_SCALE: Final = 1.0 / _SCALE


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


def build_tokenizer(root: Path, *, max_tokens: int = MAX_TOKENS) -> Any:
    """Truncated at the cap and padded to nothing, which is what the browser does.

    Both settings are overrides, not requests. The committed `tokenizer.json`
    carries `truncation: 128` and a fixed `padding: 128` of its own, so a
    tokenizer built without these two lines silently reads half the text and
    pads the rest - and reports 128 tokens for every input, which is what makes
    the mistake hard to see.

    Padding is not free of meaning here. The encoder is dynamically quantised,
    so a pad token's own activations widen the range every real token is then
    measured against. Measured 2026-08-25 (Windows 11, 8 vCPU, onnxruntime
    1.29.0): padding one sentence out to the 256-token cap moves its vector by
    up to 1.6e-2 per component. The browser pads a lone query to nothing, so the
    runner does too.
    """
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(root / TOKENIZER_RELPATH))
    tokenizer.enable_truncation(max_length=max_tokens)
    tokenizer.no_padding()
    return tokenizer


class Embedder:
    """Lazily loaded, because most runs of most stages never embed anything."""

    def __init__(self, root: Path, assist: AssistConfig | None = None) -> None:
        self._root = root
        self._assist = assist or AssistConfig()
        self._session: Any | None = None
        self._tokenizer: Any | None = None

    @property
    def available(self) -> bool:
        return (self._root / ONNX_RELPATH).exists()

    def readable(self, text: str) -> bool:
        """Whether this text is worth a vector at all.

        The encoder answers every input, including one written in a script its
        vocabulary does not carry. The answer is a unit vector like any other -
        confident, well-formed, and about the characters rather than the story,
        so no query a reader types will ever retrieve it. Degrade, do not fail:
        the item publishes, it simply is not searchable.
        """
        return readable_share(text) >= self._assist.min_readable_letter_share

    def load(self) -> None:
        import onnxruntime

        # Naming the provider stops a machine with a second one installed from
        # quietly answering with different kernels.
        self._session = onnxruntime.InferenceSession(
            str(self._root / ONNX_RELPATH),
            session_options(),
            providers=["CPUExecutionProvider"],
        )
        self._tokenizer = build_tokenizer(self._root, max_tokens=self._assist.max_tokens)

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


def readable_share(text: str) -> float:
    """The share of the text's letters that are in the alphabet the encoder learned.

    Letters, not tokens. The obvious test - how many tokens came back `[UNK]` -
    does not work, and it fails in the direction that looks fine: the vocabulary
    holds single Devanagari, Arabic and Cyrillic characters as subword pieces,
    so a Hindi sentence spells out one character at a time and reports an
    unknown share of 0.008 (measured 2026-08-26 with the committed tokenizer).
    What the vocabulary lacks is the words, not the letters, so counting `[UNK]`
    would call every one of those items readable.

    Text with no letters at all - a headline of numbers and punctuation - scores
    1.0. There is no alphabet to be illiterate in, and the tokenizer reads
    digits and punctuation the same way whatever language surrounds them.
    """
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return 1.0
    latin = sum(
        1 for character in letters if unicodedata.name(character, "").startswith("LATIN")
    )
    return latin / len(letters)


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
