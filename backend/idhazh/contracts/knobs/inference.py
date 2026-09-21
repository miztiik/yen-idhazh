"""How the model decodes, pinned so a change of output is a reviewable diff."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Sha256, without_retired_keys


class InferenceConfig(Model):
    """Decoding is pinned here so a change of output is a reviewable diff."""

    n_ctx: int = Field(
        default=8192,
        ge=512,
        description=(
            "The window one sequence gets. The default stays 8192 because it is the "
            "conservative window for weights nobody has put in front of a runner; "
            "each model file sets its own window. Whether its KV cache fits is "
            "decided by what the machine has free, not by the process's resident "
            "memory alone - docs/reference/pipeline-cost.md."
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
    cpu_range: str | None = Field(
        default=None,
        pattern=r"^[0-9]+-[0-9]+$",
        description="llama-server --cpu-range, inclusive lo-hi. None omits the flag.",
    )
    cpu_strict: int | None = Field(
        default=None,
        ge=0,
        le=1,
        description="llama-server --cpu-strict, 0 or 1. None omits the flag.",
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
    checkpoint_min_step: int | None = Field(
        default=None,
        ge=0,
        description="llama-server -cms, in tokens; 0 means no minimum. None omits the flag.",
    )
    ctx_checkpoints: int | None = Field(
        default=None,
        ge=0,
        description="llama-server -ctxcp, maximum checkpoints per slot. None omits the flag.",
    )
    cache_ram: int | None = Field(
        default=None,
        ge=-1,
        description=(
            "llama-server -cram, in MiB; -1 is unlimited and 0 disables the cache. "
            "None omits the flag."
        ),
    )
    cache_prompt: bool | None = Field(
        default=None,
        description=(
            "llama-server --cache-prompt or --no-cache-prompt. None omits the flag "
            "and preserves the completion requests' existing enabled cache."
        ),
    )
    slot_prompt_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="llama-server -sps, shared-prefix fraction. None omits the flag.",
    )
    jinja: bool | None = Field(
        default=None,
        description="llama-server --jinja or --no-jinja. None omits the flag.",
    )
    reasoning_preserve: bool | None = Field(
        default=None,
        description=(
            "llama-server --reasoning-preserve or --no-reasoning-preserve. "
            "None omits the flag."
        ),
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
            "Gen Intel Core i7-1265U against llama.cpp b10444, three runs a case and "
            "zero spread: one server start goes from 12 lines and 1,085 bytes to about "
            "206 lines and 16,011 bytes. That is a job artifact kept for two days, never "
            "a committed file. It changes what the server says about itself and nothing "
            "about what it decodes, so idhazh.fingerprint leaves it out of the stamp."
        ),
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "How far the sampler may stray from the likeliest token. The default is "
            "0.0 for the reason n_ctx's default is conservative: a temperature is a "
            "reading of one model's weights, and a number that suited one family "
            "applied to weights nobody has run is a setting somebody will trust. "
            "Every committed entry pins its own. Above 0.0 the seed stops being dead "
            "code and becomes the control that decides which token is drawn - "
            "docs/architecture/contracts/determinism.md."
        ),
    )
    top_p: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description=(
            "The share of probability mass the sampler may draw from. 1.0 is the "
            "whole distribution, which is not a second temperature and does not "
            "contradict one: temperature reshapes the distribution and this truncates "
            "its tail, so 1.0 leaves the truncation off and lets temperature alone "
            "decide. Lowering both is two instruments aimed at one effect, and then "
            "neither reading says which of them moved the words."
        ),
    )
    seed: int = Field(
        default=0,
        description=(
            "Which sample the sampler draws. It is the whole of the repeatability "
            "story above temperature 0: same inputs and same seed is the same reply, "
            "same inputs and a different seed is a different one. At temperature 0 it "
            "is dead code and nothing reads it, which is what it was until "
            "2026-09-17. It is enumerated in the fingerprint either way, so a change "
            "of sampler cannot move the words without moving the stamp."
        ),
    )
    request_timeout_minutes: float = Field(
        default=22.1,
        gt=0.0,
        description=(
            "One summarizer POST may wait this long. Sized from the measured worst "
            "8B long article plus one cold prompt prefix, doubled; the shard timeout "
            "remains the outer bound. With no decode cap set anywhere, this and the "
            "window are the two bounds a runaway decode meets - each per item, each "
            "loud, and each already recorded."
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

    @model_validator(mode="after")
    def _cpu_range_is_ordered(self) -> Self:
        if self.cpu_range is not None:
            first, last = (int(cpu) for cpu in self.cpu_range.split("-"))
            if first > last:
                raise ValueError("cpu_range must start at or before its end")
        return self

    @model_validator(mode="before")
    @classmethod
    def _a_run_written_while_a_span_was_capped_still_reads(cls, data: Any) -> Any:
        """The read-side migration for a block a run record embeds.

        **This shape is two things at once, and that is why the refusal is not
        here.** `ModelsConfig` reaches it through `ModelEntry`, which is a file a
        person edits and where a removed knob is refused by name.
        `run_manifest.ModelUse` reaches it through `ModelRef`, which is a payload
        yesterday's run wrote - and a build that cannot read yesterday's payload
        is a release blocker (`CLAUDE.md` section 11).

        Every retired name here is dropped rather than renamed, because nothing
        replaces any of them. The two decode caps sent a number where the
        runtime's own default is already unbounded by anything but the window,
        and `max_output_tokens` was the single budget they were split out of.
        `thinking` was a decoding flag that could never have worked on its own -
        the output schema binds the decode from the first token, so a think
        opener is not a legal token - and reasoning is declared by the closing
        marker on the turn envelope instead.
        """
        return without_retired_keys(data, *RETIRED_INFERENCE_NAMES)


#: The `models.<role>.inference` knobs this block used to carry. Each is refused
#: by name rather than by "extra inputs are not permitted", which tells an
#: operator nothing about where their number went.
#:
#: `max_think_tokens` and `max_answer_tokens` were the two decode caps, and
#: `max_output_tokens` was the one budget they were split out of in 2026-09-14.
#: All three sent a number where llama-server's own default is already unbounded
#: by anything but the window, and the server is started with no prediction
#: flag - so what actually stopped a runaway decode was never the cap. The two
#: bounds that remain are the per-request timeout, which lands `model_timed_out`,
#: and the window with no context shift, which lands `CONTEXT_EXCEEDED`. Both
#: are per item and both are already recorded. `thinking` was a decoding flag
#: the output schema made unreachable; reasoning is declared by
#: `turns.thinking_close`.
#:
#: **This map refuses a config file and never a run record.** `ModelEntry` is
#: the shape a person edits and is where it is read; the same block inside a
#: `ModelRef` a run wrote is migrated instead, by the map below.
SUPERSEDED_INFERENCE_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "max_output_tokens": "",
        "max_answer_tokens": "",
        "max_think_tokens": "",
        "thinking": "models.<role>.turns.thinking_close",
    }
)


#: Every knob a run record written before 2026-09-21 can carry and nothing
#: carries now. Dropped rather than migrated: no field here has a successor to
#: hold its number, and a reading of a cap that no longer bounds anything is not
#: a reading worth carrying forward (Guardrail #10).
RETIRED_INFERENCE_NAMES: Final[frozenset[str]] = frozenset(
    {"max_output_tokens", "max_answer_tokens", "max_think_tokens", "thinking"}
)
