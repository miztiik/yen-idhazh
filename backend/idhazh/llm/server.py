"""Talk to a local llama-server over its OpenAI-compatible endpoint.

The transport is the OpenAI chat-completions shape, not because anything is
hosted - `CLAUDE.md` section 0a forbids that - but because it is the one wire
format every local runtime already speaks, so swapping llama.cpp for something
else later is a URL change rather than a rewrite.

Decoding parameters are assembled in exactly one place. A second place to set
temperature is a second place for an output to move for a reason nobody
recorded (`docs/architecture/contracts/determinism.md`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib import request
from urllib.parse import urlsplit, urlunsplit

from idhazh.contracts.app_config import InferenceConfig, ModelRef

# One port per job. A workflow declares it once as `LLAMA_PORT`, and both halves
# read it here: the argv the server binds with, and the address the stage posts
# to. Two answers would leave a server listening on one port and a summarizer
# posting to another, and every item would fail as "model unreachable".
# It is a process-boundary value, not a tunable, so it is not a config field and
# `idhazh.fingerprint` has nothing to classify (Rule #6, `CLAUDE.md` section 11).
DEFAULT_PORT: Final = int(os.environ.get("LLAMA_PORT") or 8080)
DEFAULT_ENDPOINT: Final = f"http://127.0.0.1:{DEFAULT_PORT}/v1/chat/completions"
DEFAULT_HEALTH: Final = f"http://127.0.0.1:{DEFAULT_PORT}/health"

# llama.cpp maps ERROR_TYPE_EXCEED_CONTEXT_SIZE to HTTP 400 and names it here.
# The message beside it states the token counts and its wording moves between
# builds; this identifier does not, so it is what we match on.
CONTEXT_EXCEEDED_TYPE: Final = "exceed_context_size_error"


def is_context_exceeded(body: str) -> bool:
    """Did the runtime refuse this request because the prompt did not fit?

    `body` is the error envelope of a non-2xx reply, which llama.cpp shapes as
    `{"error": {"code": ..., "message": ..., "type": ...}}`. Anything that is
    not that shape, or names another type, is not a recognised context error and
    stays an unreachable server rather than becoming a new silent class.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return False
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return False
    return bool(error.get("type") == CONTEXT_EXCEEDED_TYPE)


@dataclass(frozen=True, slots=True)
class Completion:
    """What came back, before anything has been believed about it."""

    content: str
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"
    prefill_ms: int = 0
    decode_ms: int = 0
    cached_tokens: int = 0

    @property
    def hit_the_budget(self) -> bool:
        """The reply stopped because it ran out of tokens, not because it was done."""
        return self.finish_reason == "length"

    @property
    def reasoned(self) -> bool:
        """The runtime split a reasoning channel out of the content channel.

        Newer llama.cpp builds move thinking into `message.reasoning_content`
        rather than leaving `<think>` inline, so reading only `content` makes a
        reasoning model look compliant. On the build in ggml-org/llama.cpp issue
        27134 it empties `content` outright for any template whose generation
        prompt ends in a closing think tag - which is exactly what Qwen3 renders
        under `enable_thinking: false`. No workflow pins a llama.cpp build, so
        this arrives without a commit of ours.
        """
        return bool(self.reasoning.strip())


def server_argv(
    *,
    binary: Path,
    weights: Path,
    model: ModelRef,
    inference: InferenceConfig,
    port: int = DEFAULT_PORT,
) -> list[str]:
    """The exact process the run stands up.

    The only function in this repository that spells a `llama-server` flag.
    Every workflow that starts a server imports it; nothing renders the same
    list a second time, because a second rendering is a second server.

    The list is built from config, not written out by hand at the call site, so
    one config edit moves the local server and the workflow together.

    Not every knob here reaches the stamp. `idhazh.fingerprint.NOT_DIGESTED`
    names the ones that do not and says which of them can still move the words.
    """
    argv = [
        str(binary),
        "--model",
        str(weights),
        "--alias",
        model.id,
        "--ctx-size",
        str(inference.n_ctx),
        # Without this the server silently drops the middle of an oversized
        # prompt and answers about a document it no longer holds, which scores
        # as a hallucination and names the wrong cause. Refusing is the signal.
        "--no-context-shift",
        "--batch-size",
        str(inference.n_batch),
        "--ubatch-size",
        str(inference.n_ubatch),
        "--threads",
        str(inference.n_threads),
        "--port",
        str(port),
    ]
    if inference.n_parallel is not None:
        argv.extend(("-np", str(inference.n_parallel)))
    if inference.flash_attention is not None:
        argv.extend(("-fa", inference.flash_attention))
    if inference.load_mode is not None:
        argv.extend(("-lm", inference.load_mode))
    if inference.cache_type_k is not None:
        argv.extend(("-ctk", inference.cache_type_k))
    if inference.cache_type_v is not None:
        argv.extend(("-ctv", inference.cache_type_v))
    if inference.priority is not None:
        argv.extend(("--prio", str(inference.priority)))
    if inference.poll is not None:
        argv.extend(("--poll", str(inference.poll)))
    if inference.n_threads_batch is not None:
        argv.extend(("-tb", str(inference.n_threads_batch)))
    # Loopback only, and only inside a CI job. It opens no surface a reader can
    # reach, and it is the only place the context high-water mark and the
    # busy-slot average are published at all.
    if inference.metrics:
        argv.append("--metrics")
    if not inference.startup_warmup:
        argv.append("--no-warmup")
    return argv


def request_payload(
    *,
    model_id: str,
    system: str,
    user: str,
    output_schema: dict[str, Any],
    inference: InferenceConfig,
    schema_name: str = "summary",
) -> dict[str, Any]:
    """The request body, with the output shape enforced by the decoder.

    `response_format` is the control that survives an injection: text inside the
    user turn can change the words, and cannot change the shape.
    """
    return {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": inference.temperature,
        "top_p": inference.top_p,
        "seed": inference.seed,
        "max_tokens": inference.max_output_tokens,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": output_schema},
        },
        # Reasoning measurably increases hallucination when summarizing, and
        # summarization is compression - every reasoning token is a chance to
        # leave the source.
        "chat_template_kwargs": {"enable_thinking": inference.thinking},
    }


def parse_completion(body: str) -> Completion:
    """Read the envelope. Nothing here trusts the content yet."""
    payload = json.loads(body)
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("the runtime returned no choices")
    usage = payload.get("usage") or {}
    message = choices[0].get("message", {})
    # llama.cpp reports prefill and decode separately; a runtime that does not
    # leaves the rates absent rather than blending them into one wrong number.
    timings = payload.get("timings") or {}
    return Completion(
        content=message.get("content") or "",
        reasoning=message.get("reasoning_content") or "",
        prompt_tokens=int(usage.get("prompt_tokens", 0)),
        completion_tokens=int(usage.get("completion_tokens", 0)),
        finish_reason=choices[0].get("finish_reason") or "stop",
        prefill_ms=round(float(timings.get("prompt_ms", 0.0))),
        decode_ms=round(float(timings.get("predicted_ms", 0.0))),
        cached_tokens=int(timings.get("cache_n", 0)),
    )


def post(
    payload: dict[str, Any], *, endpoint: str = DEFAULT_ENDPOINT, timeout: float
) -> Completion:
    """The only place an item is sent for summarizing. Loopback only, by construction."""
    outbound = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(outbound, timeout=timeout) as response:
        return parse_completion(response.read().decode("utf-8"))


def props_url(endpoint: str = DEFAULT_ENDPOINT) -> str:
    """The `/props` address on the server a chat-completions endpoint names.

    Derived rather than configured, so a caller that points the run at another
    port cannot ask one server for a template and another for an answer.
    """
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, "/props", "", ""))


def props(endpoint: str = DEFAULT_ENDPOINT, *, timeout: float) -> dict[str, Any]:
    """What the running server says about itself, including its chat template.

    The template is the model's own Jinja source, which the server applies to
    every request. Reading it here is what makes the stamp's template digest an
    observation of the runtime rather than a restatement of config.

    A server that does not answer yields nothing rather than raising. The caller
    records the absence, because a run that stops over an unread diagnostic is
    worse than one that says the diagnostic was unread (`CLAUDE.md` section 1a).
    Bounded by the same configured clock as a completion, so a hung server costs
    the stage a knob somebody can turn rather than a number in this file.
    """
    try:
        with request.urlopen(props_url(endpoint), timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}
