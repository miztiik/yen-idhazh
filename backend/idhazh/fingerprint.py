"""Build the pipeline stamp, and read what a stamp meant.

Row 15 exists because `temperature=0, seed=0` is not determinism - it is
determinism given identical logits. Eleven of the sixteen enumerated ways an
output can move are silent without a stamp, including a publisher rewriting an
article at the same URL.

Two consequences run through this module. Skip-if-exists becomes
skip-if-fingerprint-matches: identical inputs do no work and write no eval row,
because a re-run that changed nothing measured nothing. And a matching stamp
with different words is recorded as a `determinism_violation`, never raised - a
gate that fires across runner CPU classes for reasons unrelated to a regression
gets switched off within a month.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final, NamedTuple

from idhazh.contracts.app_config import InferenceConfig, ModelRef
from idhazh.contracts.fingerprint import FingerprintRow, PipelineInputs

# Relative and POSIX-separated, because it is quoted in logs and manifests
# (CLAUDE.md section 2).
LEDGER_RELPATH: Final = "state/fingerprints.csv"

_READ_CHUNK: Final = 1024 * 1024


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    """Digest a weight file or a binary without reading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_READ_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def sampling_spelling(inference: InferenceConfig) -> str:
    """One canonical spelling of the decoding parameters.

    `seed` is enumerated as an input and is still dead code under greedy
    decoding - it is recorded so a future move off greedy cannot change an
    output silently, and it is never cited as the determinism control.
    """
    return ";".join(
        (
            f"temperature={inference.temperature:.4f}",
            f"top_p={inference.top_p:.4f}",
            f"seed={inference.seed}",
            f"max_output_tokens={inference.max_output_tokens}",
            f"thinking={'on' if inference.thinking else 'off'}",
        )
    )


class Undigested(NamedTuple):
    """Why one inference knob sits outside the stamp."""

    moves_logits: bool
    reason: str


#: Every `InferenceConfig` knob the stamp does not carry, and why each one is out.
#:
#: `moves_logits=True` marks a known blind spot, not a claim that the knob is
#: safe: those five change the arithmetic the runtime does, so moving one can
#: rewrite a summary while the stamp holds still. Row 4 of
#: `TODO/20260825-qwen35-9b-swap-plan.md` digests them, because it resets every
#: fingerprint already and doing that twice spends the reset twice.
#:
#: The set is closed: a knob that is neither here nor digested fails the
#: contract test in `backend/tests/test_fingerprint.py`.
NOT_DIGESTED: Final[Mapping[str, Undigested]] = MappingProxyType(
    {
        "cache_type_k": Undigested(
            True, "A quantised K cache changes the attention arithmetic."
        ),
        "cache_type_v": Undigested(
            True, "A quantised V cache changes the attention arithmetic."
        ),
        "flash_attention": Undigested(
            True, "Another kernel adds the same values in another order."
        ),
        "n_parallel": Undigested(
            True, "Slots divide the context, which changes the batch shapes."
        ),
        "n_threads_batch": Undigested(
            True, "Prompt threads change how the partial sums accumulate."
        ),
        "load_mode": Undigested(
            False, "mmap and mlock move where the weights sit, not what they hold."
        ),
        "poll": Undigested(
            False, "How the runtime waits for work. It calculates nothing."
        ),
        "priority": Undigested(
            False, "Scheduler priority changes when work runs, not what it produces."
        ),
        "startup_warmup": Undigested(
            False, "A pass before the run. It decodes nothing that we keep."
        ),
        "request_timeout_minutes": Undigested(
            False, "A clock bound on one POST. It stops a call, it does not reword one."
        ),
    }
)


def digested_inference_fields() -> frozenset[str]:
    """The `InferenceConfig` knobs the stamp carries, read back from the stamp itself.

    Four reach `PipelineInputs` under their own name. The rest arrive folded
    into the sampling spelling, so the names come out of that spelling rather
    than out of a second list somebody has to keep in step.
    """
    folded = (pair.split("=", 1)[0] for pair in sampling_spelling(InferenceConfig()).split(";"))
    reaches_the_digest = frozenset(PipelineInputs.model_fields) | frozenset(folded)
    return frozenset(InferenceConfig.model_fields) & reaches_the_digest


def build_inputs(
    *,
    model: ModelRef,
    model_sha256: str,
    inference: InferenceConfig,
    truncation_cap_tokens: int,
    runtime_build: str,
    chat_template: str,
    prompt: str,
    output_schema: str,
    runner_class: str,
    extractor_version: str,
    sanitizer_version: str,
) -> PipelineInputs:
    """Assemble the stamp from the weights that were loaded, not the ones configured.

    `model_sha256` is the digest of the file the runtime actually opened.
    `ModelRef.sha256` is what config expected, and the two disagreeing is the
    exact event this stamp exists to make visible.
    """
    return PipelineInputs(
        model_sha256=model_sha256,
        quantisation=model.quantisation,
        runtime_build=runtime_build,
        chat_template_sha256=text_digest(chat_template),
        prompt_sha256=text_digest(prompt),
        output_schema_sha256=text_digest(output_schema),
        truncation_cap_tokens=truncation_cap_tokens,
        sampling=sampling_spelling(inference),
        n_ctx=inference.n_ctx,
        n_batch=inference.n_batch,
        n_ubatch=inference.n_ubatch,
        n_threads=inference.n_threads,
        runner_class=runner_class,
        extractor_version=extractor_version,
        sanitizer_version=sanitizer_version,
    )


class Observation(StrEnum):
    """What a prior stamp says about the work in front of us."""

    FIRST_RUN = "first_run"
    INPUTS_CHANGED = "inputs_changed"
    UNCHANGED = "unchanged"
    DETERMINISM_VIOLATION = "determinism_violation"


#: The one observation that does no work. Everything else summarizes.
SKIPPABLE: Final[frozenset[Observation]] = frozenset({Observation.UNCHANGED})


def classify(
    *,
    prior_fingerprint: str | None,
    prior_output_digest: str | None = None,
    current_fingerprint: str,
    current_output_digest: str | None = None,
) -> Observation:
    """Compare this item's stamp against the one the committed ledger carries.

    `current_output_digest` is None before the work is done - that is the normal
    path, where a matching stamp is enough to skip. It is supplied only when a
    run was forced, which is the only way to observe a violation at all.
    """
    if prior_fingerprint is None:
        return Observation.FIRST_RUN
    if prior_fingerprint != current_fingerprint:
        return Observation.INPUTS_CHANGED
    if current_output_digest is None or prior_output_digest is None:
        return Observation.UNCHANGED
    if current_output_digest != prior_output_digest:
        return Observation.DETERMINISM_VIOLATION
    return Observation.UNCHANGED


def read_ledger(path: Path) -> dict[str, FingerprintRow]:
    """Every stamp ever written, keyed by its digest. Missing file means none yet."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [FingerprintRow.from_csv_row(row) for row in csv.DictReader(handle)]
    return {row.pipeline_fingerprint: row for row in rows}


def append_new(path: Path, rows: Iterable[FingerprintRow]) -> list[FingerprintRow]:
    """Append the stamps this ledger has not seen. Never rewrites, never prunes.

    Returns what was written, so a caller can log the new stamps rather than
    re-read the file to find out.
    """
    known = set(read_ledger(path))
    fresh: list[FingerprintRow] = []
    for row in rows:
        if row.pipeline_fingerprint not in known:
            known.add(row.pipeline_fingerprint)
            fresh.append(row)
    if not fresh:
        return []

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=FingerprintRow.csv_columns(), lineterminator="\n"
        )
        if not exists:
            writer.writeheader()
        for row in fresh:
            writer.writerow(row.csv_row())
    return fresh
