"""How the model decodes, pinned so a change of output is a reviewable diff."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from idhazh.contracts.base import Model, Sha256


class InferenceConfig(Model):
    """Decoding is pinned here so a change of output is a reviewable diff."""

    n_ctx: int = Field(
        default=8192,
        ge=512,
        description=(
            "The window one sequence gets. The default stays 8192 because it is the "
            "conservative window for weights nobody has put in front of a runner; "
            "models.summarize pins 49152, and the "
            "measurement that earns the raise is about the 9B on a GitHub-hosted "
            "runner rather than about this field. Doubling buys nothing but KV cache: "
            "32 KiB a token on those weights, measured 2026-09-13 at 512.00 MiB for "
            "16384, 1024.00 for 32768 and 2048.00 for 65536, which interpolates to "
            "1536.00 MiB at the pinned 49152, over the 8 attention "
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
    thinking: bool = Field(
        default=False,
        description="Off. Reasoning measurably increases hallucination when summarizing.",
    )
    max_output_tokens: int = Field(
        default=900,
        ge=1,
        description=(
            "A crash guard, not a length target. The prompt sets the length; this only "
            "stops a runaway decode from burning a shard's whole timeout. Sized at 250 "
            "the reply ran out of budget mid-object and failed as a shape error, which "
            "named the wrong cause - so it is set well above any summary we want."
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
