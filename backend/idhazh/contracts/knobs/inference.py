"""How the model decodes, pinned so a change of output is a reviewable diff."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Literal

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Sha256


class InferenceConfig(Model):
    """Decoding is pinned here so a change of output is a reviewable diff."""

    n_ctx: int = Field(
        default=8192,
        ge=512,
        description=(
            "The window one sequence gets. The default stays 8192 because it is the "
            "conservative window for weights nobody has put in front of a runner; "
            "models.summarize pins 65536, and the "
            "measurement that earns the raise is about the 9B on a GitHub-hosted "
            "runner rather than about this field. Doubling buys nothing but KV cache: "
            "32 KiB a token on those weights, which is 2048.00 MiB at the pinned "
            "65536 against 512.00 MiB at 16384, over the 8 attention "
            "layers of 32 - the other 24 are recurrent and cost a fixed 50.25 MiB "
            "whatever the window is. Whether that fits is decided by what the machine "
            "had free and never by what the processes held - "
            "docs/reference/measurements.md."
        ),
    )
    n_threads: int = Field(default=4, ge=1)
    n_batch: int = Field(default=512, ge=1)
    n_ubatch: int = Field(default=512, ge=1)
    n_parallel: int | None = Field(
        default=None,
        ge=1,
        description="llama-server -np. None omits the flag and keeps the runtime default.",
    )
    n_threads_batch: int | None = Field(
        default=None,
        ge=1,
        description="llama-server -tb. None omits the flag and lets it follow n_threads.",
    )
    startup_warmup: bool = Field(
        default=True,
        description="If false, emit --no-warmup. True lets llama-server warm at startup.",
    )
    metrics: bool = Field(
        default=True,
        description=(
            "If true, emit --metrics and llama-server serves its counters on "
            "/metrics. On by default: without them a run cannot say how close it came "
            "to n_ctx, and a concurrency result has no busy-slot number to read it by."
        ),
    )
    flash_attention: Literal["on", "off"] | None = Field(
        default=None,
        description="llama-server -fa. None omits the flag and leaves the runtime on auto.",
    )
    load_mode: Literal["mmap+mlock"] | None = Field(
        default=None,
        description="llama-server -lm. None omits the flag and keeps the runtime default.",
    )
    cache_type_k: Literal["q8_0"] | None = Field(
        default=None,
        description="llama-server -ctk. None omits the flag and keeps full-precision KV.",
    )
    cache_type_v: Literal["q8_0"] | None = Field(
        default=None,
        description="llama-server -ctv. None omits the flag and keeps full-precision KV.",
    )
    priority: int | None = Field(
        default=None,
        ge=-1,
        le=3,
        description="llama-server --prio. None omits the flag and keeps normal priority.",
    )
    poll: int | None = Field(
        default=None,
        ge=0,
        description="llama-server --poll. None omits the flag and keeps the runtime default.",
    )
    log_verbosity: int | None = Field(
        default=None,
        ge=0,
        description=(
            "llama-server -lv. None omits the flag and keeps the runtime default of 3, "
            "which prints twelve lines and none of them names flash attention, the KV "
            "buffer or the compute buffer. At 4 the whole model-loader block comes back, "
            "which is what lets a check read the attention state off the server's own "
            "line instead of off the flag we passed it. Measured 2026-09-09 on a 12th "
            "Gen Intel Core i7-1265U against llama.cpp b10444, three runs an arm and "
            "zero spread: one server start goes from 12 lines and 1,085 bytes to about "
            "206 lines and 16,011 bytes. That is a job artifact kept for two days, never "
            "a committed file. It changes what the server says about itself and nothing "
            "about what it decodes, so idhazh.fingerprint leaves it out of the stamp."
        ),
    )
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    seed: int = Field(
        default=0,
        description="Dead code under greedy decoding. Never cited as the determinism control.",
    )
    max_think_tokens: int = Field(
        default=256,
        ge=1,
        description=(
            "The thinking span's budget, and a hard cap rather than a hint. A model "
            "that never closes its reasoning block would otherwise eat the whole "
            "window and be recorded as a truncated summary, which names the wrong "
            "cause. 256 tokens costs 42.6 s an item at the measured 6.01 +/- 0.11 "
            "tokens a second (2026-08-23, ubuntu-latest, EPYC 9V74, llama.cpp b10598, "
            "three repeats). It is read only where the entry declares "
            "turns.thinking_close; an entry that declares no closing marker spends "
            "none of it."
        ),
    )
    max_answer_tokens: int = Field(
        default=900,
        ge=1,
        description=(
            "The answer span's budget. A crash guard, not a length target: the prompt "
            "sets the length and this only stops a runaway decode from burning a "
            "shard's whole timeout. Sized at 250 the reply ran out of budget "
            "mid-object and failed as a shape error, which named the wrong cause - so "
            "it is set well above any summary we want. It was max_output_tokens until "
            "2026-09-14, when one budget stopped being able to say which of two spans "
            "overran."
        ),
    )
    request_timeout_minutes: float = Field(
        default=22.1,
        gt=0.0,
        description=(
            "One summarizer POST may wait this long. Sized from the measured worst "
            "8B long article plus one cold prompt prefix, doubled; the shard timeout "
            "remains the outer bound."
        ),
    )
    declared_for: Sha256 | None = Field(
        default=None,
        description=(
            "The weights this block is set for - the sha256 of the entry that carries "
            "it. Every number here is a measurement about one model on one runner, "
            "never a property of the pipeline, so the entry states which bytes the "
            "numbers were put in front of. Swap the weights and this is left behind, "
            "which is the one event the field exists to make loud. It says a person "
            "paired these numbers with these bytes; where the numbers came from is "
            "docs/concepts/config.md, because a runner and a date cannot be checked "
            "by a validator and a field nothing checks is a comment."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _a_run_written_before_the_two_spans_still_reads(cls, data: Any) -> Any:
        """The read-side migration for a block a run record embeds.

        **This shape is two things at once, and that is why the refusal is not
        here.** `ModelsConfig` reaches it through `ModelEntry`, which is a file a
        person edits and where a removed knob is refused by name.
        `run_manifest.ModelUse` reaches it through `ModelRef`, which is a payload
        yesterday's run wrote - and a build that cannot read yesterday's payload
        is a release blocker (`CLAUDE.md` section 11).

        `max_output_tokens` is renamed rather than dropped: it sized the answer
        of a single call, which is what `max_answer_tokens` sizes, so the number
        a run recorded keeps its meaning. `thinking` is dropped, because reasoning
        is declared on the turn envelope now and `ModelRef` carries no envelope -
        and every run written under the old flag wrote it false, so no reading is
        lost.

        A payload that carries both spellings is left alone, so the shape refuses
        it: two budgets in one block is not a payload this can read.
        """
        if not isinstance(data, dict):
            return data
        touched = frozenset(data) & (frozenset(MIGRATED_INFERENCE_NAMES) | RETIRED_INFERENCE_NAMES)
        if not touched:
            return data
        migrated: dict[Any, Any] = {}
        for name, value in data.items():
            if name in RETIRED_INFERENCE_NAMES:
                continue
            successor = MIGRATED_INFERENCE_NAMES.get(name, name)
            migrated[name if successor in data else successor] = value
        return migrated


#: The `models.<role>.inference` knobs this block used to carry.
#: `max_output_tokens` was one budget over what is now two spans, so it could not
#: say whether a long think or a cut answer spent it; it is renamed to the span
#: it actually sized. `thinking` was a decoding flag that could never have
#: worked on its own - the output schema binds the decode from the first token,
#: so a think opener is not a legal token - and reasoning is declared by the
#: closing marker on the turn envelope instead.
#:
#: **This map refuses a config file and never a run record.** `ModelEntry` is
#: the shape a person edits and is where it is read; the same block inside a
#: `ModelRef` a run wrote is migrated instead, by the two maps below.
SUPERSEDED_INFERENCE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "max_output_tokens": "max_answer_tokens",
        "thinking": "models.<role>.turns.thinking_close",
    }
)


#: What a run record written before 2026-09-14 spells its output budget, and the
#: name that carries the same number now. A rename rather than a drop: the old
#: key sized the answer of a single call and so does the new one, so the number
#: the run recorded keeps its meaning (Guardrail #10).
MIGRATED_INFERENCE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"max_output_tokens": "max_answer_tokens"}
)


#: The knob a run record written before 2026-09-14 carried and nothing carries
#: now. Reasoning is declared by `turns.thinking_close`, and `ModelRef` - the
#: shape a run records - carries no turn envelope at all. Every run written
#: under the old flag wrote it false, because the output schema made anything
#: else fail on shape, so dropping it loses no reading.
RETIRED_INFERENCE_NAMES: Final[frozenset[str]] = frozenset({"thinking"})
