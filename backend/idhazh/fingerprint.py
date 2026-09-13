"""Record what a run summarized with, and raise the one alarm that survives.

Row 15 exists because `temperature=0, seed=0` is not determinism - it is
determinism given identical logits. Eleven of the sixteen enumerated ways an
output can move are silent unless the inputs are written down, including a
publisher rewriting an article at the same URL.

Every input is read from the thing it describes rather than from a literal
beside the call: the build from the environment the job pinned, the chat
template from the server that will apply it, the runner class from the runner.
A source that does not answer is recorded as unanswered, which is a different
reading from a source that answered (Guardrail #10).

**This records and it gates nothing.** Owner decision, 2026-09-10. The digest
over these inputs used to do two jobs and did neither: the skip-if-unchanged
half was never wired to a caller, and the eval-window half withheld a quality
number until N consecutive run-days ran at one digest - which, in a repository
whose prompts and vocabularies change weekly, meant never. What is left is the
reading: `build_inputs` assembles the manifest, the caller hangs it on the run
record, and `prose_changed_alone` is the single alarm. It reports; it never
blocks and it never withholds a number.
"""

from __future__ import annotations

import hashlib
import os
import platform
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final, NamedTuple

from idhazh.contracts.app_config import InferenceConfig, ModelRef
from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.fingerprint import PipelineInputs

#: Sixty-four zeroes. It satisfies `Sha256`, so a manifest built on it validates,
#: publishes, and still says nothing about which weights ran (Guardrail #10).
PLACEHOLDER_DIGEST: Final = "0" * 64

#: What the manifest records when the runtime did not name the build that decoded
#: the weights. It is not a llama.cpp release tag and cannot be read as one, so
#: a run whose build went unrecorded reads apart from every run whose build is
#: known. Declaring the ignorance is the point (Guardrail #10).
UNRECORDED_BUILD: Final = "build-not-recorded"

#: The same, for a chat template no server was there to hand over.
UNRECORDED_TEMPLATE: Final = "chat-template-not-recorded"

#: How the stamp spells a runtime knob config left null. Null means "whatever
#: the runtime picks", which is a real and different choice from pinning a
#: value, so it gets its own spelling rather than being folded into one of the
#: values it might resolve to.
RUNTIME_DEFAULT: Final = "runtime-default"

#: Where Linux names the processor. `platform.processor()` answers `x86_64`
#: there, which is the same string on every runner and so explains nothing.
CPUINFO: Final = Path("/proc/cpuinfo")

_CPU_MODEL_KEY: Final = "model name"

_READ_CHUNK: Final = 1024 * 1024


def text_digest(text: str) -> str:
    return derive_text_digest(text)


def file_digest(path: Path) -> str:
    """Digest a weight file or a binary without reading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_READ_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_build(environ: Mapping[str, str] | None = None) -> str:
    """The llama.cpp release that decoded the weights, as the job pinned it.

    `.github/workflows/digest.yml` sets `LLAMA_CPP_BUILD` beside the download it
    checks against a recorded sha256, so the tag the stamp carries and the bytes
    that ran are named in one place.

    A developer machine usually pins nothing. That degrades to `UNRECORDED_BUILD`
    rather than inventing a tag: the whole reason this argument stopped being the
    literal `llama-server-local` is that a stamp naming a build nobody checked
    validates and lies (Guardrail #10).
    """
    env = os.environ if environ is None else environ
    return env.get("LLAMA_CPP_BUILD", "").strip() or UNRECORDED_BUILD


def runner_class(environ: Mapping[str, str] | None = None) -> str:
    """Which class of machine ran the work, in that machine's own words.

    A class, never a host. `host_cpu` carries the individual processor and is
    deliberately undigested; the class is a choice somebody made and belongs in
    the digest, while which CPU that choice drew is luck and does not.

    GitHub Actions publishes all three parts. A machine that publishes none of
    them is a developer machine, and says so.
    """
    env = os.environ if environ is None else environ
    inside_actions = env.get("GITHUB_ACTIONS") == "true"
    where = env.get("RUNNER_ENVIRONMENT") or ("github" if inside_actions else "local")
    system = env.get("RUNNER_OS") or platform.system() or "unknown"
    arch = env.get("RUNNER_ARCH") or platform.machine() or "unknown"
    return f"{where}/{system}/{arch}".lower()


def host_cpu(cpuinfo: Path = CPUINFO) -> str:
    """The processor this run drew. A diagnostic, and not part of the manifest.

    It is the only field that explains a determinism violation, which is why it
    has to name the part rather than the architecture.
    """
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            name, _, value = line.partition(":")
            if name.strip() == _CPU_MODEL_KEY and value.strip():
                return value.strip()
    return platform.processor() or platform.machine() or "unknown"


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


def runtime_flags_spelling(inference: InferenceConfig) -> str:
    """One canonical spelling of the runtime knobs that move the arithmetic.

    These five were enumerated as known blind spots and left out of the record
    until 2026-08-26, so they could be moved without moving anything anybody
    could read. A quantised KV cache, another attention kernel, a second slot or
    a different prompt-thread count each change how the partial sums accumulate,
    and a summary that changed for one of those reasons used to record identical
    to the one before it.

    They arrive folded into one field for the same reason `sampling` is one
    field: five values that are null on almost every run are five lines nobody
    reads.
    """
    return ";".join(
        (
            f"cache_type_k={inference.cache_type_k or RUNTIME_DEFAULT}",
            f"cache_type_v={inference.cache_type_v or RUNTIME_DEFAULT}",
            f"flash_attention={inference.flash_attention or RUNTIME_DEFAULT}",
            f"n_parallel={inference.n_parallel if inference.n_parallel else RUNTIME_DEFAULT}",
            (
                "n_threads_batch="
                f"{inference.n_threads_batch if inference.n_threads_batch else RUNTIME_DEFAULT}"
            ),
        )
    )


class Undigested(NamedTuple):
    """Why one inference knob sits outside the recorded manifest."""

    moves_logits: bool
    reason: str


#: Every `InferenceConfig` knob the manifest does not carry, and why each one is out.
#:
#: Every knob left here is one that cannot move an output. The five that could -
#: `cache_type_k`, `cache_type_v`, `flash_attention`, `n_parallel` and
#: `n_threads_batch` - were listed here as known blind spots until 2026-08-26
#: and are now folded into `runtime_flags`.
#:
#: The set is closed: a knob that is neither here nor recorded fails the
#: contract test in `backend/tests/test_fingerprint.py`.
NOT_DIGESTED: Final[Mapping[str, Undigested]] = MappingProxyType(
    {
        "declared_for": Undigested(
            False,
            "Names the weights the block is set for. The manifest already carries those "
            "bytes as model_sha256, so recording it twice would say a swap happened "
            "twice.",
        ),
        "load_mode": Undigested(
            False, "mmap and mlock move where the weights sit, not what they hold."
        ),
        "log_verbosity": Undigested(
            False,
            "How much the server says about itself. It cannot move a logit, and "
            "recording it would report a change the day somebody turned the logging up.",
        ),
        "metrics": Undigested(
            False, "Exposes an endpoint. It counts the decode, it does not change one."
        ),
        "poll": Undigested(False, "How the runtime waits for work. It calculates nothing."),
        "priority": Undigested(
            False, "Scheduler priority changes when work runs, not what it produces."
        ),
        "startup_warmup": Undigested(
            False, "A pass before the run. It decodes nothing that we keep."
        ),
        "request_timeout_minutes": Undigested(
            False, "A clock bound on one call. It stops a call, it does not reword one."
        ),
    }
)


def digested_inference_fields() -> frozenset[str]:
    """The `InferenceConfig` knobs the manifest carries, read back from the manifest.

    Four reach `PipelineInputs` under their own name. The rest arrive folded
    into one of the two canonical spellings, so the names come out of those
    spellings rather than out of a third list somebody has to keep in step.
    """
    defaults = InferenceConfig()
    spellings = (sampling_spelling(defaults), runtime_flags_spelling(defaults))
    folded = {pair.split("=", 1)[0] for spelling in spellings for pair in spelling.split(";")}
    reaches_the_digest = frozenset(PipelineInputs.model_fields) | frozenset(folded)
    return frozenset(InferenceConfig.model_fields) & reaches_the_digest


def build_inputs(
    *,
    model: ModelRef,
    model_sha256: str | None,
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
    """Assemble the manifest from the weights that were loaded, not the ones configured.

    `model_sha256` is the digest of the file the runtime actually opened.
    `ModelRef.sha256` is what config expected, and the two disagreeing is the
    exact event this record exists to make visible.

    An absent digest stops the record. The caller used to substitute
    `PLACEHOLDER_DIGEST`, which turned "nobody measured the weights" into a
    manifest that looked measured.
    """
    if not model_sha256 or model_sha256 == PLACEHOLDER_DIGEST:
        raise ValueError(
            f"{model.id} has no measured weights digest. Record the sha256 of "
            f"{model.file} in config before the stamp is built."
        )
    return PipelineInputs(
        model_sha256=model_sha256,
        quantisation=model.quantisation,
        runtime_build=runtime_build,
        chat_template_sha256=text_digest(chat_template),
        prompt_sha256=text_digest(prompt),
        output_schema_sha256=text_digest(output_schema),
        truncation_cap_tokens=truncation_cap_tokens,
        sampling=sampling_spelling(inference),
        runtime_flags=runtime_flags_spelling(inference),
        n_ctx=inference.n_ctx,
        n_batch=inference.n_batch,
        n_ubatch=inference.n_ubatch,
        n_threads=inference.n_threads,
        runner_class=runner_class,
        extractor_version=extractor_version,
        sanitizer_version=sanitizer_version,
    )


#: The inputs that are the words we hand the model. Prose, in the alarm's sense.
PROSE_INPUTS: Final = ("prompt_sha256", "chat_template_sha256", "output_schema_sha256")

#: The inputs that are the machine doing the reading.
MACHINE_INPUTS: Final = ("model_sha256", "quantisation", "runtime_build")


def prose_changed_alone(
    previous: PipelineInputs | None, current: PipelineInputs
) -> tuple[str, ...]:
    """The prose inputs that moved while the model and the binary held still.

    The one alarm that survives the gate (owner decision, 2026-09-10). It
    reports, it never blocks, and it never withholds a number: a run whose
    prompt changed publishes exactly as a run whose prompt did not.

    Empty on a first run, on a run where nothing moved, and on a run where the
    weights or the build moved too - the last of those is a model change, which
    an operator already reads off the boundary the console draws. What is left
    is the case nobody else can see: the same weights, the same binary, and
    different words asked of them.

    The comparison is against one earlier manifest, handed in by the caller. It
    costs the same on a repository of one published day and of a thousand
    (Guardrail #12).
    """
    if previous is None:
        return ()
    moved = set(current.changed_inputs(previous))
    if moved & set(MACHINE_INPUTS):
        return ()
    return tuple(name for name in PROSE_INPUTS if name in moved)
