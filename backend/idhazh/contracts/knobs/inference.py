"""How the model decodes, pinned so a change of output is a reviewable diff."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final, Literal, Self

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
    max_think_tokens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "The thinking span's budget. Null means no cap: the span runs until the "
            "model writes turns.thinking_close, and the window is the only other "
            "thing that stops it. An integer bounds the span at that many tokens. A "
            "cap exists at all because a model that never closes its reasoning block "
            "would otherwise decode to n_ctx and be recorded as a truncated summary, "
            "which names the wrong cause - the closing marker is what normally ends "
            "the span, and the cap is what catches a model that never writes one. Set "
            "it only from a reading taken on the weights it is set for; a number "
            "carried over from other weights caps a thought mid-sentence, and a "
            "truncated thought is worse than no thought at the same budget "
            "(arxiv 2504.09858). It is read only where the entry declares "
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

    @model_validator(mode="after")
    def _cpu_range_is_ordered(self) -> Self:
        if self.cpu_range is not None:
            first, last = (int(cpu) for cpu in self.cpu_range.split("-"))
            if first > last:
                raise ValueError("cpu_range must start at or before its end")
        return self

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
