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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final
from urllib import request

from idhazh.contracts.app_config import InferenceConfig, ModelRef

DEFAULT_ENDPOINT: Final = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_HEALTH: Final = "http://127.0.0.1:8080/health"


@dataclass(frozen=True, slots=True)
class Completion:
    """What came back, before anything has been believed about it."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"

    @property
    def hit_the_budget(self) -> bool:
        """The reply stopped because it ran out of tokens, not because it was done."""
        return self.finish_reason == "length"


def server_argv(
    *, binary: Path, weights: Path, model: ModelRef, inference: InferenceConfig, port: int = 8080
) -> list[str]:
    """The exact process the run stands up.

    Every knob here is also a fingerprint input, so a change to this list must
    be a change to the stamp - which is why it is built from config rather than
    written out by hand at the call site.
    """
    argv = [
        str(binary),
        "--model",
        str(weights),
        "--alias",
        model.id,
        "--ctx-size",
        str(inference.n_ctx),
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
    return Completion(
        content=choices[0].get("message", {}).get("content") or "",
        prompt_tokens=int(usage.get("prompt_tokens", 0)),
        completion_tokens=int(usage.get("completion_tokens", 0)),
        finish_reason=choices[0].get("finish_reason") or "stop",
    )


def post(
    payload: dict[str, Any], *, endpoint: str = DEFAULT_ENDPOINT, timeout: float
) -> Completion:
    """The one function here that opens a socket. Loopback only, by construction."""
    outbound = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(outbound, timeout=timeout) as response:
        return parse_completion(response.read().decode("utf-8"))
