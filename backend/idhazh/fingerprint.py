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
from typing import Any, Final

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.knobs.models import ModelRef
from idhazh.llm.server import SETTING_KEYS, TurnMarkers, setting, turn_markers_digest, window

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

#: How the stamp spells a bare flag - one the file names with no argument, so
#: the switch is on and there is no value to record beside it.
SET: Final = "set"

#: How the stamp spells a thinking span with no cap. Not `RUNTIME_DEFAULT`: that
#: word says the runtime chose a number we did not, and this says there is no
#: number - the span ends on the entry's closing marker or on the window. Not
#: `None` either, which is Python's spelling of an absent value and would put a
#: language's vocabulary in a stamp that outlives the language.
UNCAPPED: Final = "uncapped"

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

    `.github/scripts/llama-cpp-pin.sh` decides the build, the job that installs
    it reads that file, and the step running this stage is handed the same
    answer as `LLAMA_CPP_BUILD` - so the tag the stamp carries and the bytes
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


def sampling_spelling(request: Mapping[str, Any]) -> str:
    """One canonical spelling of the decoding parameters.

    `seed` is enumerated as an input, and above temperature 0 it is the control
    that decides which sample the sampler draws rather than dead code. It was
    recorded from the start for exactly this move: a change of sampler cannot
    shift the words without shifting this string.

    **No span budget is here, because no span carries one.** The two decode caps
    left the settings on 2026-09-21, and what bounds a span now is the window
    and the per-request timeout - both enumerated elsewhere. There is no
    reasoning flag here either: what turns reasoning on is the closing marker on
    the turn envelope, which arrives under `turn_markers_sha256`.

    A value the file leaves out records as `RUNTIME_DEFAULT`, for the reason a
    missing flag does: what the server picks is a real and different choice from
    pinning a number, and writing our guess at its default here would record a
    guess as a measurement (Guardrail #10).
    """
    spelled = []
    for name, digits in (("temperature", 4), ("top_p", 4), ("seed", 0)):
        value = setting(request, name)
        if value is None:
            spelled.append(f"{name}={RUNTIME_DEFAULT}")
        elif digits:
            spelled.append(f"{name}={float(value):.{digits}f}")
        else:
            spelled.append(f"{name}={value}")
    return ";".join(spelled)


#: The server flags that can change arithmetic, prompt rendering or cache reuse,
#: spelled as llama-server spells them. It enumerated this project's own field
#: names until the model file started carrying the flags, so the recorded string
#: moves once and the console reports the server switches moved on the first run
#: after. That is a one-time true statement rather than a defect.
DIGESTED_FLAGS: Final[tuple[str, ...]] = (
    "-ctk",
    "-ctv",
    "-fa",
    "-np",
    "-tb",
    "-cms",
    "-ctxcp",
    "-cram",
    "--cache-prompt",
    "--no-cache-prompt",
    "-sps",
    "--jinja",
    "--no-jinja",
    "--reasoning-preserve",
    "--no-reasoning-preserve",
)


def runtime_flags_spelling(server: Mapping[str, Any]) -> str:
    """Canonical settings that can change arithmetic, prompt rendering or cache reuse.

    A cached prefix and a newly evaluated prefix need not take the same numeric
    path. Record the controls that choose between them as well as the cache
    type, attention kernel, slot count and prompt-thread count.

    A bare flag records as `SET`. A flag the file leaves out records as
    `RUNTIME_DEFAULT`, because "whatever the runtime picks" is a real and
    different choice from pinning a value.
    """
    return ";".join(f"{flag}={_flag_spelling(server, flag)}" for flag in DIGESTED_FLAGS)


def _flag_spelling(server: Mapping[str, Any], flag: str) -> object:
    if flag not in server:
        return RUNTIME_DEFAULT
    value = server[flag]
    return SET if value is None else value


def _recorded(server: Mapping[str, Any], name: str) -> int:
    """One server setting the manifest records under this project's name for it.

    Absent raises rather than substituting a number. The manifest says what a
    run decoded on, and a default written here would be this project's guess at
    llama-server's default recorded as a measurement (Guardrail #10).
    """
    value = setting(server, name)
    if value is None:
        raise ValueError(
            f"the model file declares no {SETTING_KEYS[name]}, so this run has no "
            f"{name} to record. Name it in the entry's server block"
        )
    return int(value)


def build_inputs(
    *,
    model: ModelRef,
    model_sha256: str | None,
    server: Mapping[str, Any],
    request: Mapping[str, Any],
    truncation_cap_tokens: int,
    runtime_build: str,
    chat_template: str,
    prompt: str,
    output_schema: str,
    runner_class: str,
    extractor_version: str,
    sanitizer_version: str,
    markers: TurnMarkers | None = None,
) -> PipelineInputs:
    """Assemble the manifest from the weights that were loaded, not the ones configured.

    `model_sha256` is the digest of the file the runtime actually opened.
    `ModelRef.sha256` is what config expected, and the two disagreeing is the
    exact event this record exists to make visible.

    An absent digest stops the record. The caller used to substitute
    `PLACEHOLDER_DIGEST`, which turned "nobody measured the weights" into a
    manifest that looked measured.

    `markers` is optional because a caller may have none: they are read off the
    server at start-up, and a caller holding only a recorded `ModelRef` never
    stood a server up. An absent envelope leaves the key absent rather than
    substituting a digest, which is the read-side rule
    `PipelineInputs.turn_markers_sha256` states.
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
        turn_markers_sha256=turn_markers_digest(markers) if markers is not None else None,
        output_schema_sha256=text_digest(output_schema),
        truncation_cap_tokens=truncation_cap_tokens,
        sampling=sampling_spelling(request),
        runtime_flags=runtime_flags_spelling(server),
        n_ctx=window(server),
        n_batch=_recorded(server, "n_batch"),
        n_ubatch=_recorded(server, "n_ubatch"),
        n_threads=_recorded(server, "n_threads"),
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
