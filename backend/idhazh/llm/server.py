"""Talk to a local llama-server over the two routes it answers on.

Nothing here is hosted - `CLAUDE.md` section 0a forbids that. Two transports,
and which one a caller takes is decided by whether the prompt bytes are ours.

**The chat-completions shape** hands the server a message array and lets the
model's own chat template render the prompt. It is the one wire format every
local runtime already speaks, so swapping llama.cpp for something else later is
a URL change rather than a rewrite. One call, one prompt, nothing replayed.

**The rendered-completion shape** hands the server the prompt string itself.
A sequence of calls needs it: a chat template renders the same assistant turn
differently as a generation prompt and as history, so the second call's prompt
stops matching the first one part-way through and the server re-reads
everything behind the break. Rendering the bytes here makes the second prompt
literally the first one plus the reply plus the new turn, so the prefix holds by
construction rather than by a template's goodwill.

Decoding parameters are assembled in exactly one place. A second place to set
temperature is a second place for an output to move for a reason nobody
recorded (`docs/architecture/contracts/determinism.md`).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any, Final
from urllib import request
from urllib.parse import urlsplit, urlunsplit

from idhazh.contracts.app_config import InferenceConfig, ModelRef

# One port per job. A workflow declares it once as `LLAMA_PORT`, and both halves
# read it here: the argv the server binds with, and the address the stage posts
# to. Two answers would leave a server listening on one port and a summarizer
# posting to another, and every item would fail as "model unreachable".
# It is a process-boundary value, not a tunable, so it is not a config field and
# `idhazh.fingerprint` has nothing to classify (Guardrail #6, `CLAUDE.md` section 11).
DEFAULT_PORT: Final = int(os.environ.get("LLAMA_PORT") or 8080)
DEFAULT_ENDPOINT: Final = f"http://127.0.0.1:{DEFAULT_PORT}/v1/chat/completions"
DEFAULT_HEALTH: Final = f"http://127.0.0.1:{DEFAULT_PORT}/health"

# The route that takes a prompt string. It is a consequence of which builder
# rendered the payload rather than a dial anybody turns - a chat body posted
# here is broken, not differently tuned - so it sits beside the port for the
# same reason the port does, and `idhazh.fingerprint` has nothing to classify
# (Guardrail #6, `CLAUDE.md` section 11).
#
# llama-server's own `/completions` rather than the OpenAI-compatible
# `/v1/completions` beside it. Measured 2026-09-12 on build b10444-5f754ea0e:
# both routes ignore `response_format` outright and return unconstrained prose,
# and both honour a top-level `json_schema`. On the native route that field is
# the route's own; on the compatibility route it survives a layer whose job is
# to rewrite this body, and that layer already drops `response_format`. No
# workflow pins a llama.cpp build, so a build that started stripping it would
# turn constrained decoding off for every item at once.
_COMPLETION_PATH: Final = "/completions"
DEFAULT_COMPLETION_ENDPOINT: Final = f"http://127.0.0.1:{DEFAULT_PORT}{_COMPLETION_PATH}"

#: The reply stopped because it ran out of budget. llama-server's own word for
#: it on the rendered-completion route, where the chat route says `length`.
_STOPPED_AT_THE_BUDGET: Final = "limit"

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


#: How one turn is written for the weights we load. It is model-shaped text and
#: it moves when the model does, so it sits beside the prompts rather than in
#: `config/`: an operator turns no dial here, and a wrong value renders a prompt
#: with no turn structure that the decoder's grammar still accepts - worse
#: summaries and no error. JSON rather than raw text because the trailing
#: newlines are load-bearing and invisible, and an editor or a line-ending pass
#: would rewrite them in silence.
TURN_MARKERS_PATH: Final = Path(__file__).parent.parent / "prompts" / "turn_markers.json"


@dataclass(frozen=True, slots=True)
class TurnMarkers:
    """The strings that open and close a turn, and the two ways a reply opens.

    **The reply opening is not derived from the turn opening**, because a chat
    template ends a generation prompt with more than a role header. The weights
    this project runs today close an empty reasoning block there when reasoning
    is off, and open one when it is on; both are recorded rather than invented,
    from the server that applies them.
    """

    turn_opening: Template
    turn_closing: str
    reply_opening: str
    reply_opening_thinking: str

    def turn(self, role: str, content: str) -> str:
        """One whole turn. `substitute` rather than `safe_substitute`: a renamed
        placeholder raises here instead of reaching a model as the literal it
        looks like (`docs/architecture/summarize/prompt.md`)."""
        return self.turn_opening.substitute(role=role) + content + self.turn_closing

    def opening(self, *, thinking: bool) -> str:
        return self.reply_opening_thinking if thinking else self.reply_opening

    def opening_of(self, prompt: str) -> str:
        """The reply opening a rendered prompt already ends with.

        A continuation reads it off the prompt rather than off a flag handed in
        beside it, so the second call cannot open its reply differently from the
        first - which is the one way a continuation could still break the prefix
        it exists to preserve.
        """
        for opening in (self.reply_opening_thinking, self.reply_opening):
            if prompt.endswith(opening):
                return opening
        raise ValueError("this prompt does not end on a reply opening, so nothing may follow it")


@lru_cache(maxsize=1)
def turn_markers() -> TurnMarkers:
    """The markers, read once and checked once.

    A missing key raises at the first render rather than becoming a `KeyError`
    part-way through a shard.
    """
    loaded = json.loads(TURN_MARKERS_PATH.read_text(encoding="utf-8"))
    missing = sorted({field.name for field in fields(TurnMarkers)} - set(loaded))
    if missing:
        raise ValueError(f"{TURN_MARKERS_PATH.name} names no {', '.join(missing)}")
    return TurnMarkers(
        turn_opening=Template(loaded["turn_opening"]),
        turn_closing=loaded["turn_closing"],
        reply_opening=loaded["reply_opening"],
        reply_opening_thinking=loaded["reply_opening_thinking"],
    )


def render_prompt(*, system: str, user: str, thinking: bool) -> str:
    """The prompt bytes a rendered completion is sent, from the turns it is made of."""
    markers = turn_markers()
    return markers.turn("system", system) + markers.turn("user", user) + markers.opening(
        thinking=thinking
    )


def continued_prompt(prompt: str, *, reply: str, user: str) -> str:
    """The next prompt in a sequence: this one, what came back, and one new turn.

    The opening is a literal concatenation, so the property a prefix cache needs
    is not something two call sites have to agree about - it is what the
    expression says. The seam sits on the turn-closing marker, which tokenises
    as one entry of the model's own vocabulary, so the byte prefix survives as a
    token prefix rather than re-splitting at the join.
    """
    markers = turn_markers()
    opening = markers.opening_of(prompt)
    return prompt + reply + markers.turn_closing + markers.turn("user", user) + opening


class FlashAttention(StrEnum):
    """What the server's own log says happened to attention. Three states, not two."""

    ACTIVE = "active"
    REFUSED = "refused"
    #: The log does not settle it - almost always because `log_verbosity` was
    #: left null, so the model-loader block was never printed. It is a failure
    #: of the check, never a report that attention was off.
    UNREADABLE = "unreadable"


#: What llama-server was ASKED for, which is not what it did. With no `-fa` flag
#: it prints `auto`, and `auto` is the non-answer this reader exists to refuse.
FLASH_ASKED: Final = re.compile(r"flash_attn\s*=\s*(\w+)")

#: The decision itself, printed only when `auto` left one to make - so it is
#: absent from both explicit arms and present in neither of their logs.
FLASH_FUSED: Final = "resolve_fused_ops: Flash Attention enabled"


def flash_attention_state(server_log: str) -> FlashAttention:
    """Read the attention state off the server, not off the flag we handed it.

    Both lines print at `-lv 4` and neither prints at the runtime default of 3,
    so a log taken from a quiet server answers `UNREADABLE` rather than
    `REFUSED`. That distinction is the whole point: a reader that took a missing
    line for "off" would turn a forgotten verbosity into a finding about
    attention. Measured 2026-09-09, three runs an arm and zero spread -
    `docs/reference/measurements.md`.
    """
    asked = FLASH_ASKED.search(server_log)
    if asked is None:
        return FlashAttention.UNREADABLE
    if asked.group(1) == "enabled":
        return FlashAttention.ACTIVE
    if asked.group(1) == "disabled":
        return FlashAttention.REFUSED
    if asked.group(1) == "auto" and FLASH_FUSED in server_log:
        return FlashAttention.ACTIVE
    return FlashAttention.UNREADABLE


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
    # What the server says about itself. At the runtime default of 3 it prints
    # twelve lines and none of them names the attention state, the KV buffer or
    # the compute buffer, so a check on any of those reads the flag we passed
    # rather than what the runtime did with it.
    if inference.log_verbosity is not None:
        argv.extend(("-lv", str(inference.log_verbosity)))
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


def completion_payload(
    *,
    model_id: str,
    system: str,
    user: str,
    output_schema: dict[str, Any],
    inference: InferenceConfig,
    max_output_tokens: int,
) -> dict[str, Any]:
    """The request body for a prompt we rendered ourselves.

    `json_schema` is the control that survives an injection, exactly as
    `response_format` is on the chat route: text inside the user turn can change
    the words and cannot change the shape. The spelling differs because the
    route does - `response_format` is accepted and ignored here, which is a
    silent loss of the only control that matters, so it is never sent.

    **The budget is handed in rather than read off `inference`**, for the same
    reason `continued_completion_payload` takes one: a rendered call is held to
    a shape of its own, and a budget sized for some other shape cuts a reply
    that did exactly what the grammar allowed. `inference.max_output_tokens` is
    the summariser role's number and sizes the single call that still reads it.

    `cache_prompt` is stated rather than inherited. The whole point of a
    rendered prompt is that the next call reuses this one, the build's own
    default for the flag is not readable off `/props`, and nothing pins the
    build - so a default that flipped would re-read every prompt in full with
    no line in any log to say why.

    `model` is carried although a single-model server ignores it. It is the one
    field that says which weights the body was built for, and a payload read out
    of a log with no model id cannot be attributed to a run.
    """
    return {
        "model": model_id,
        "prompt": render_prompt(system=system, user=user, thinking=inference.thinking),
        "temperature": inference.temperature,
        "top_p": inference.top_p,
        "seed": inference.seed,
        "n_predict": max_output_tokens,
        "stream": False,
        "cache_prompt": True,
        "json_schema": output_schema,
    }


def continued_completion_payload(
    first: Mapping[str, Any],
    *,
    reply: str,
    user: str,
    output_schema: dict[str, Any],
    max_output_tokens: int,
) -> dict[str, Any]:
    """A second request whose prompt IS the first one's, plus what it returned.

    Not "byte for byte by agreement between two call sites" - the same string
    object, extended. A prefix cache reuses the longest common prefix of the
    tokenised prompt, so everything the first call read and everything it wrote
    is answered from the slot and only the new turn is prefilled.

    Only three things move: the prompt grows, the decoder is held to a different
    shape, and the output budget is the one derived for that shape. Temperature,
    `top_p`, `seed`, `stream` and the prompt cache are carried over untouched,
    because `completion_payload` is the one place that sets them
    (`docs/architecture/contracts/determinism.md`).

    **The budget is replaced in the key it was written in.** A second spelling
    would leave both in the body, and llama-server would answer the first call's
    budget to a reply sized for the second - a cut plan on every item, recovered
    into a summary with no picture, and no counter saying why.

    `reply` is the first call's own content, replayed verbatim. It is a string
    the model wrote and it is not trusted any further here than a fetched page
    would be - it has already been parsed against a closed schema, and what it
    can reach downstream is bounded by that schema and not by this turn.
    """
    return {
        **first,
        "prompt": continued_prompt(str(first["prompt"]), reply=reply, user=user),
        "n_predict": max_output_tokens,
        "json_schema": output_schema,
    }


def parse_completion(body: str) -> Completion:
    """Read the envelope. Nothing here trusts the content yet.

    Two envelopes, because the server answers two routes and each names its
    fields its own way. The chat route returns `choices`, a `usage` block and a
    `finish_reason`; the rendered-completion route returns `content`, its token
    counts at the top level, and a `stop_type` whose budget word is `limit`.
    The `timings` block is the same on both.

    `reasoning` stays empty on the rendered-completion route, and that is a
    property rather than a gap: the split `Completion.reasoned` exists to catch
    is the chat template moving a think block into `reasoning_content`, and a
    route with no template applies none. Anything the model writes inline
    arrives in `content`, where each caller's own cleaner already removes it.
    """
    payload = json.loads(body)
    # llama.cpp reports prefill and decode separately; a runtime that does not
    # leaves the rates absent rather than blending them into one wrong number.
    timings = payload.get("timings") or {}
    prefill_ms = round(float(timings.get("prompt_ms", 0.0)))
    decode_ms = round(float(timings.get("predicted_ms", 0.0)))
    cached_tokens = int(timings.get("cache_n", 0))
    if "choices" in payload:
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("the runtime returned no choices")
        usage = payload.get("usage") or {}
        message = choices[0].get("message", {})
        return Completion(
            content=message.get("content") or "",
            reasoning=message.get("reasoning_content") or "",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            finish_reason=choices[0].get("finish_reason") or "stop",
            prefill_ms=prefill_ms,
            decode_ms=decode_ms,
            cached_tokens=cached_tokens,
        )
    if "content" not in payload:
        raise ValueError("the runtime returned neither a choice nor a completion")
    return Completion(
        content=payload.get("content") or "",
        prompt_tokens=int(payload.get("tokens_evaluated", 0)),
        completion_tokens=int(payload.get("tokens_predicted", 0)),
        finish_reason="length" if payload.get("stop_type") == _STOPPED_AT_THE_BUDGET else "stop",
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        cached_tokens=cached_tokens,
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


def completion_url(endpoint: str = DEFAULT_ENDPOINT) -> str:
    """The rendered-completion address on the server an endpoint names.

    Derived from a sibling address for the same reason `props_url` is: a run
    pointed at another port asks one server for everything.
    """
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, _COMPLETION_PATH, "", ""))


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
