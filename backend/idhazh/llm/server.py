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
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from string import Template
from types import MappingProxyType
from typing import Any, Final
from urllib import request
from urllib.parse import urlsplit, urlunsplit

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.knobs.models import CompanionFile, ModelEntry, ModelRef
from idhazh.sanitize import why_a_forged_turn_would_survive

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

# The four read-only routes the start-up probe asks, beside the one it posts
# completions to. Paths rather than addresses, because every one of them is
# derived from whichever endpoint the caller was given - one server answers all
# five or the probe is reconciling two different processes.
_PROPS_PATH: Final = "/props"
_APPLY_TEMPLATE_PATH: Final = "/apply-template"
_TOKENIZE_PATH: Final = "/tokenize"

#: llama-server's own stop vocabulary on the rendered-completion route, in the
#: words the chat route would have used for the same ending. `limit` is the one
#: the rest of the pipeline keys on, because it is the budget stop; `eos` and
#: `word` are both a decode that ended itself.
#:
#: **A value not listed here is carried through as the server wrote it.** A
#: reason nobody has seen before is the one worth seeing, and folding it into
#: `stop` would report a novel ending as an ordinary one.
_STOP_TYPES: Final[dict[str, str]] = {"limit": "length", "eos": "stop", "word": "stop"}

# llama.cpp maps ERROR_TYPE_EXCEED_CONTEXT_SIZE to HTTP 400 and names it here.
# The message beside it states the token counts and its wording moves between
# builds; this identifier does not, so it is what we match on.
CONTEXT_EXCEEDED_TYPE: Final = "exceed_context_size_error"

#: What `n_predict` is sent as when a span carries no cap. It is llama.cpp's own
#: spelling, not a sentinel of ours: `--predict` documents `number of tokens to
#: predict (default: -1, -1 = infinity)`, recorded in
#: `tests/fixtures/runtime/b10598-llama-server-help.txt`. Omitting the key would
#: mean the same thing, and saying it is what lets a recorded request body be
#: read without knowing which flags the server was started with.
UNCAPPED_N_PREDICT: Final = -1

#: What span two owns and span one may not inherit. A key here is stripped when
#: the thinking span is derived from the answer body, and each one is here for
#: its own reason rather than as a class.
_ANSWER_ONLY_KEYS: Final[frozenset[str]] = frozenset(
    {
        # A schema binds the decode from the first token, and a think opener is
        # not a legal token under it.
        "json_schema",
        # Same fault, one route along and worse: a grammar of a few literals
        # leaves the model able to write those literals and nothing else, so
        # span one cannot write a reasoning block at all.
        "grammar",
        # The alternatives reading is about the answer's opening token. Carried
        # into span one it asks the server for a list at every position of a
        # span nobody reads a distribution off.
        "n_probs",
    }
)


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


#: The name a turn opening substitutes the role under. `string.Template` renders
#: it, so both `$role` and `${role}` spell it.
TURN_ROLE: Final = "role"

#: The roles this project renders, and the two a forged turn would be spelled
#: with. "system" and "user" share no first character and no last one, so what
#: two renderings have in common is exactly the bytes around the role rather
#: than part of the role itself. The derivation reads them to find the marker,
#: and `turn_markers_digest` reads them to record what the marker writes.
_TURN_ROLES: Final = ("system", "user")


class SystemPlacement(StrEnum):
    """Where this model's template takes the system text. Two, and no third.

    A turn topology, so it is an enum rather than a free-form string: what
    "folded into the first user turn" MEANS is a code path
    (`docs/architecture/summarize/model-boundary.md`).
    """

    #: A system turn of its own, ahead of the first user turn. Every chat
    #: template that has a system role.
    OWN_TURN = "own_turn"
    #: No system role exists, so the same bytes open the first user turn instead,
    #: behind the joiner the template writes. The same words at a different
    #: address, never different words.
    FOLD_INTO_FIRST_USER = "fold_into_first_user"


@dataclass(frozen=True, slots=True)
class TurnMarkers:
    """The strings that open and close a turn, and the two ways a reply opens.

    Six of these are read off the model's own rendering at server start, so this
    project's render IS the template's render rather than a copy of it that can
    drift. The two that cannot be read off a rendering come from the entry: a
    generation prompt never contains the marker the model writes to close its
    reasoning, and a template cannot hand back the name of a variable nobody
    sent it (`docs/architecture/summarize/model-boundary.md`).
    """

    turn_opening: Template
    turn_closing: str
    reply_opening: str
    reply_opening_thinking: str
    system_role: SystemPlacement
    #: Empty under `own_turn`, where nothing reads it. The fold is the only case
    #: that reads it, and there the derivation takes it from the template's own
    #: rendering, so it is never empty on the case that reads it.
    system_joiner: str
    #: What closes this model's reasoning block, and the whole declaration that
    #: reasoning is wanted. `None` is one schema-constrained span and no
    #: reasoning; a string is two spans on one slot.
    thinking_close: str | None
    #: The template variable that turns this model's reasoning on and off, sent
    #: as the one key of `chat_template_kwargs`. `None` is a template that reads
    #: no keywords, and then a request carries none.
    thinking_kwarg: str | None = None

    def turn(self, role: str, content: str) -> str:
        """One whole turn. `substitute` rather than `safe_substitute`: a renamed
        placeholder raises here instead of reaching a model as the literal it
        looks like (`docs/architecture/summarize/prompt.md`)."""
        return self.turn_opening.substitute(role=role) + content + self.turn_closing

    def conversation(self, *, system: str, user: str) -> str:
        """Both turns, with the system text at the address this model's template gives it.

        Two code paths chosen by a value, never by a model id. The fold is the
        model with no system role: the same bytes, one turn earlier, behind the
        joiner the entry declares. What the turns say does not change and cannot
        - the instructions are one set for every model
        (`docs/architecture/summarize/model-boundary.md`).
        """
        if self.system_role is SystemPlacement.FOLD_INTO_FIRST_USER:
            return self.turn("user", system + self.system_joiner + user)
        return self.turn("system", system) + self.turn("user", user)

    @property
    def thinks(self) -> bool:
        """Whether a call on these markers is decoded as two spans."""
        return self.thinking_close is not None

    def opening(self) -> str:
        """Where the model starts writing, on the case this envelope declares.

        It takes no argument. A flag handed in beside the markers is a second
        answer to a question the markers already answer, and the two disagreeing
        renders a prompt that opens a reasoning block the decode is then held to
        close somewhere else.
        """
        return self.reply_opening_thinking if self.thinks else self.reply_opening

    def opening_of(self, prompt: str) -> str:
        """The reply opening a rendered prompt already ends with.

        A continuation reads it off the prompt rather than off a flag handed in
        beside it, so the second call cannot open its reply differently from the
        first - which is the one way a continuation could still break the prefix
        it exists to preserve.

        **Longest first.** The match is on a suffix, so a shorter opening that
        is a suffix of a longer one would answer for both and a thinking
        continuation would be spliced with the plain opening. Sorting by length
        makes that unreachable for any pair, rather than safe for the pair the
        incumbent happens to declare.
        """
        for opening in sorted(
            (self.reply_opening_thinking, self.reply_opening), key=len, reverse=True
        ):
            if prompt.endswith(opening):
                return opening
        raise ValueError("this prompt does not end on a reply opening, so nothing may follow it")


def turn_markers_digest(markers: TurnMarkers) -> str:
    """One digest over the whole envelope, for the stamp and for the bench.

    `prompt_sha256` moves when a marker moves and stops short of two envelope
    facts that move an output without moving a rendered prompt: which of the two
    reply openings a call ends on, and the marker the thinking span stops at. So
    the envelope is digested whole, in one place, and both readers take it from
    here - a second rendering is a second answer.

    **The turn opening is digested as the bytes it writes, not as the template
    that writes them.** `Template("...$role...")` and `Template("...${role}...")`
    substitute to the same string and are different source, so digesting the
    source made a brace a change to the envelope. It was: on 2026-09-21 the
    markers stopped being typed into config and started being read off the
    model's own template, every one of the eight came back byte-identical, and
    this digest moved anyway because the derivation writes the braced form. What
    reaches a model is what a record of the envelope should turn on.

    Both roles are substituted rather than one. A template that spelled the two
    openings differently would be refused at server start, so the pair is always
    one marker with a role in it - and digesting both says so rather than
    assuming it.

    `thinking_kwarg` is out. It is a name in somebody else's template that no
    published word is decoded under.
    """
    return derive_text_digest(
        "\n".join(
            (
                *(markers.turn_opening.safe_substitute({TURN_ROLE: role}) for role in _TURN_ROLES),
                markers.turn_closing,
                markers.reply_opening,
                markers.reply_opening_thinking,
                markers.system_role.value,
                markers.system_joiner,
                markers.thinking_close or "",
            )
        )
    )


def render_prompt(*, system: str, user: str, markers: TurnMarkers) -> str:
    """The prompt bytes a rendered completion is sent, from the markers it is made of."""
    return markers.conversation(system=system, user=user) + markers.opening()


def continued_prompt(prompt: str, *, reply: str, user: str, markers: TurnMarkers) -> str:
    """The next prompt in a sequence: this one, what came back, and one new turn.

    The opening is a literal concatenation, so the property a prefix cache needs
    is not something two call sites have to agree about - it is what the
    expression says. The seam sits on the turn-closing marker, which tokenises
    as one entry of the model's own vocabulary, so the byte prefix survives as a
    token prefix rather than re-splitting at the join.

    **`reply` is the answer, never the thinking.** Under a thinking envelope the
    slot behind this prompt also holds what span one wrote, and none of it is
    replayed here: it is model-written text, and a prompt is exactly the channel
    Guardrail #11 exists to keep model-written text out of. What that costs is
    the answer's own tokens re-prefilled, which is prefill rather than decode.
    """
    opening = markers.opening_of(prompt)
    return prompt + reply + markers.turn_closing + markers.turn("user", user) + opening


@dataclass(frozen=True, slots=True)
class TokenChoice:
    """One token the server said it could have written here, and how likely it was.

    `logprob` is the natural log llama-server reports, carried as it arrived. An
    exponential taken here would be a scale this class chose; the caller that
    wants a probability is the one that knows what it is subtracting from what.
    """

    token_id: int
    token: str
    logprob: float


@dataclass(frozen=True, slots=True)
class Completion:
    """What came back, before anything has been believed about it."""

    content: str
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    #: Why the decode stopped, as the server said it. None where the reply named
    #: no reason at all - a default of `stop` is a belief, and this class holds
    #: nothing that has been believed yet.
    finish_reason: str | None = None
    prefill_ms: int = 0
    decode_ms: int = 0
    cached_tokens: int = 0
    #: Which prefix-cache slot answered this call, as llama-server's `id_slot`.
    #: None where the reply named none, because slot 0 is a real slot.
    slot_id: int | None = None
    #: What the slot holds once this call's prompt is in it, as `tokens_cached`.
    #: `cached_tokens` beside it is what this call read back OUT of the slot, so
    #: the two answer different questions and a cold slot answers 0 to one of
    #: them and the whole prompt to the other.
    slot_tokens_held: int | None = None
    #: Did this call read anything at all out of the slot? Derived once, in the
    #: one place that can see whether the server reported `cache_n`: an absent
    #: field is a server that did not say, not a call that reused nothing.
    prefix_reused: bool | None = None
    #: What the server said it could have written at the position the caller
    #: named as the answer's opening, likeliest first, on a request that asked
    #: for alternatives. Empty where none were asked for and where the reply
    #: carried none, which is a server that did not say rather than a position
    #: with one candidate.
    first_token_choices: tuple[TokenChoice, ...] = ()

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


#: Our name for a value, and the key the model file spells it under. These are
#: the settings this project reads BY NAME rather than handing to the server
#: whole. Four of them are persisted under our names on the run record and drawn
#: in words on a console panel, so a rename would move a published string and an
#: alias does not.
SETTING_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "n_ctx": "--ctx-size",
        "n_batch": "--batch-size",
        "n_ubatch": "--ubatch-size",
        "n_threads": "--threads",
        "n_parallel": "-np",
        "load_mode": "-lm",
        "temperature": "temperature",
        "top_p": "top_p",
        "seed": "seed",
        "request_timeout_minutes": "request_timeout_minutes",
    }
)


def setting(block: Mapping[str, Any], name: str, default: Any = None) -> Any:
    """One value out of a settings block, under this project's name for it."""
    return block.get(SETTING_KEYS[name], default)


def window(server: Mapping[str, Any]) -> int:
    """The window one sequence gets. Required, because this project computes on it."""
    return int(server[SETTING_KEYS["n_ctx"]])


def request_timeout_seconds(request: Mapping[str, Any]) -> float:
    """How long one POST may wait. Required: no server-side default bounds it."""
    return float(request[SETTING_KEYS["request_timeout_minutes"]]) * 60


def caches_the_prompt(server: Mapping[str, Any]) -> bool:
    """Does a request built for this server ask the slot to keep the prefix?

    The server flag and the request key are one decision, so they are read off
    one place. llama-server keeps an enabled prompt cache unless the file turns
    it off, and the build's own default is not readable off `/props` - so a
    request states the answer rather than inheriting one that could flip with no
    log saying why.
    """
    return "--no-cache-prompt" not in server


def companion_path(weights: Path, companion: CompanionFile) -> Path:
    """Where a companion file lands: beside the weights, under its own name.

    The one place inside `idhazh` that answers this. The workflow side composes
    the same landing from `backend/utilities/model_refs.py`, which imports
    nothing from this package because it runs on a runner that has not installed
    it - so the two are read together whenever either moves.
    """
    return weights.parent / companion.file


def server_argv(
    *,
    binary: Path,
    weights: Path,
    model: ModelRef,
    server: Mapping[str, Any],
    port: int = DEFAULT_PORT,
) -> list[str]:
    """The exact process the run stands up.

    The only function in this repository that spells a `llama-server` flag, and
    it spells four. Everything else comes out of the entry's `server` block
    verbatim: a key is a flag, and a value that is not null is the argument
    beside it. Naming one more option is a key in the model file and no edit
    here.

    A flag this build does not accept is refused by llama-server at start-up,
    which names it and does not start. A sampling value cannot reach this list
    at all, because it lives in the `request` block and nothing here reads one.

    The four below stay in code because no key in the file produces them: the
    weights and the alias are the run's own, the port is the caller's, and the
    context-shift refusal is a correctness rule rather than a setting. Without
    it the server silently drops the middle of an oversized prompt and answers
    about a document it no longer holds, which scores as a hallucination and
    names the wrong cause.

    A companion file that declares a flag is emitted last, with the path it
    landed at - the one argument a config file cannot spell for itself.
    """
    argv = [
        str(binary),
        "--model",
        str(weights),
        "--alias",
        model.id,
        "--no-context-shift",
        "--port",
        str(port),
    ]
    for flag, value in server.items():
        argv.append(flag)
        if value is not None:
            argv.append(str(value))
    for companion in model.companion_files:
        if companion.flag is not None:
            # POSIX separators: the runner is Linux, and this argument is
            # captured into a committed golden (`CLAUDE.md` section 2).
            argv += [companion.flag, companion_path(weights, companion).as_posix()]
    return argv


def request_payload(
    *,
    model_id: str,
    system: str,
    user: str,
    output_schema: dict[str, Any],
    request: Mapping[str, Any],
    markers: TurnMarkers,
    schema_name: str = "summary",
) -> dict[str, Any]:
    """The request body, with the output shape enforced by the decoder.

    `response_format` is the control that survives an injection: text inside the
    user turn can change the words, and cannot change the shape.

    `markers` is handed in and has no default here. Both the keyword that turns
    reasoning on and the marker that declares it wanted are variables in
    somebody else's chat template, so they belong to the weights - a default in
    this signature would be a project constant sent to every model, which is
    what this argument replaced.

    **This route decodes one span and the runtime owns the split.** The prompt
    is rendered by the model's own template, so a caller cannot stop the decode
    at a marker and restart it under a grammar. The digest's own path renders
    its bytes and gets the two spans separately (`thinking_span`,
    `answer_span`).

    **No token cap is sent, on either envelope.** One span carries both here, so
    any number would have to be the sum of two budgets and a thinking envelope
    has no honest sum to send. The server is started without `--predict` and its
    own default is `-1`, infinity bounded by the window
    (`tests/fixtures/runtime/b10598-llama-server-help.txt`), so omitting the key
    says exactly what is true: the window stops this decode, and the
    per-request timeout stops the wait.
    """
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": setting(request, "temperature"),
        "top_p": setting(request, "top_p"),
        "seed": setting(request, "seed"),
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": output_schema},
        },
    }
    # A null keyword is a template that reads none, so the key is absent rather
    # than carrying a name no template answers to; the entry refuses that pair
    # with a closing marker declared.
    if markers.thinking_kwarg is not None:
        payload["chat_template_kwargs"] = {markers.thinking_kwarg: markers.thinks}
    return payload


def completion_payload(
    *,
    model_id: str,
    system: str,
    user: str,
    output_schema: dict[str, Any],
    server: Mapping[str, Any],
    request: Mapping[str, Any],
    markers: TurnMarkers,
    max_answer_tokens: int,
) -> dict[str, Any]:
    """The request body for a prompt we rendered ourselves.

    `json_schema` is the control that survives an injection, exactly as
    `response_format` is on the chat route: text inside the user turn can change
    the words and cannot change the shape. The spelling differs because the
    route does - `response_format` is accepted and ignored here, which is a
    silent loss of the only control that matters, so it is never sent.

    **The budget is handed in rather than read off the entry**, for the same
    reason `continued_completion_payload` takes one: a rendered call is held to
    a shape of its own, and a budget sized for some other shape cuts a reply
    that did exactly what the grammar allowed. It is the caller's own
    grammar-derived number and there is no role-level cap behind it: the
    settings block carried two until 2026-09-21 and neither bounded this route.

    **This is the answer span, whether or not one is thought in front of it.**
    Under a thinking envelope `thinking_span` derives span one from this body
    and `answer_span` puts this body's own shape back on the same slot, so the
    budget here is never a share of a combined number.

    `cache_prompt` is explicit on every request, and `caches_the_prompt` reads
    it off the same block the startup flag comes from so the two cannot
    disagree. The build's own default is not readable off `/props`, so
    inheriting a default that flipped could re-read every prompt with no log
    saying why.

    `model` is carried although a single-model server ignores it. It is the one
    field that says which weights the body was built for, and a payload read out
    of a log with no model id cannot be attributed to a run.
    """
    return {
        "model": model_id,
        "prompt": render_prompt(system=system, user=user, markers=markers),
        "temperature": setting(request, "temperature"),
        "top_p": setting(request, "top_p"),
        "seed": setting(request, "seed"),
        "n_predict": max_answer_tokens,
        "stream": False,
        "cache_prompt": caches_the_prompt(server),
        "json_schema": output_schema,
    }


def grammar_completion_payload(
    *,
    model_id: str,
    system: str,
    user: str,
    grammar: str,
    server: Mapping[str, Any],
    request: Mapping[str, Any],
    markers: TurnMarkers,
    max_answer_tokens: int,
    first_token_alternatives: int,
    post_sampling_probs: bool = False,
) -> dict[str, Any]:
    """The request body for a reply that is a word rather than a document.

    `grammar` is the control here, and it is the same control `json_schema` is
    one level up: text inside the user turn can change which word comes back and
    cannot change that a word is what comes back. The two are never sent
    together - llama.cpp would have to pick one, and which one it picks is a
    property of a build nothing here pins.

    `n_probs` asks the server what else it could have written at each position.
    The caller sizes it from its own grammar's legal opening set and reads the
    one position it named; what the reading is for is the case where the grammar
    picked a word the model gave almost no weight to, which is a reply that
    parses, enters the record, and means nothing.

    **`post_sampling_probs` is stated rather than left to the build.** It
    decides whether the numbers that come back are the model's own distribution
    or the distribution after the grammar and the sampler have reshaped it, and
    the two answer different questions: only the first can say the grammar chose
    a word the model did not. False is llama.cpp's own default and is what the
    key says here, so a recorded body names the mode rather than leaving it to a
    build nothing pins. What the server actually returns under it is measured in
    `docs/reference/benchmarks/which-probabilities-the-server-returns.md`.

    `cache_prompt` is stated for the reason `completion_payload` states it: the
    build's own default is not readable off `/props`, and nothing pins the
    build. Here the shared prefix is the system turn, which a day of pairs pays
    once instead of once a call.
    """
    return {
        "model": model_id,
        "prompt": render_prompt(system=system, user=user, markers=markers),
        "temperature": setting(request, "temperature"),
        "top_p": setting(request, "top_p"),
        "seed": setting(request, "seed"),
        "n_predict": max_answer_tokens,
        "n_probs": first_token_alternatives,
        "post_sampling_probs": post_sampling_probs,
        "stream": False,
        "cache_prompt": caches_the_prompt(server),
        "grammar": grammar,
    }


def thinking_span(
    answer: Mapping[str, Any],
    *,
    markers: TurnMarkers,
    temperature: float | None = None,
) -> dict[str, Any]:
    """Span one: this call's own prompt, decoded unconstrained and stopped at the marker.

    Derived from the answer body rather than built beside it, so the two spans
    open on the same string object and the slot the first one filled is the slot
    the second one continues. A prompt rendered twice is a prefix that holds by
    agreement between two call sites, which is the property this whole design
    exists to stop depending on.

    **What comes off is `_ANSWER_ONLY_KEYS`, and the shape control is only the
    first of them.** A schema or a grammar binds the decode from the first token
    and a think opener is not a legal token under either, so span one would be
    held to the answer's shape and could not think at all. `n_probs` comes off
    with them: it asks for a list of alternatives at every position, and the
    position anybody reads one at is in span two.

    **A caller that decodes its answer greedily states a thinking temperature.**
    `temperature` left null carries over whatever the answer body declared,
    which is what every committed entry wants - each pins 0.2, and a span that
    stops at a marker is in no danger. A caller that pins 0.0 for a one-word
    answer is a different case: greedy decoding on a span whose length is
    uncapped runs until it repeats itself, and the repetition ends only at the
    marker it is looping instead of writing, or at the window.

    **`n_predict` is written here rather than left alone, and that is the whole
    reason the constant survives.** The answer body this span is derived from
    carries the caller's own grammar-derived budget, and a span that inherited
    it would think under a number sized for the answer - four tokens on the
    judge's route. `-1` is the spelling `--predict` documents, `number of tokens
    to predict (default: -1, -1 = infinity)`, recorded in
    `tests/fixtures/runtime/b10598-llama-server-help.txt`. The span then ends on
    the entry's own closing marker or on the window, and on nothing else - and
    llama-server excludes the stop string from what it returns, which is why
    `answer_span` writes the marker itself rather than trusting the reply to
    carry it.

    **A stop alone would not do**, because a block that never closes eats the
    window - which is exactly what this accepts, and why an uncapped span rests
    its whole weight on the marker being the bytes this model actually writes.
    """
    close = markers.thinking_close
    if close is None:
        raise ValueError(
            "these markers declare no thinking_close, so there is no span to think in - "
            "a caller reached for one on an envelope that does not think"
        )
    span = {name: value for name, value in answer.items() if name not in _ANSWER_ONLY_KEYS}
    span["n_predict"] = UNCAPPED_N_PREDICT
    span["stop"] = [close]
    if temperature is not None:
        span["temperature"] = temperature
    return span


def answer_span(
    answer: Mapping[str, Any], *, thought: str, markers: TurnMarkers
) -> dict[str, Any]:
    """Span two: the same body, with the thinking behind it and the shape back on.

    The prompt is span one's prompt extended by what span one wrote, so the KV
    slot holds everything in front of it and only the closing marker is new.
    That is the same property `continued_completion_payload` keeps between two
    calls, one level down.

    **This is where a grammar is applied, and that is the point of the pair.**
    Constraining the first token of the whole decode forces an answer where the
    model meant to start reasoning. The body handed in is the answer body whole,
    so whichever shape control it declares comes back on here, at the position
    the answer actually opens at.

    **The thinking goes into this request body and nowhere else.** It is
    model-written text, so it is trusted exactly as far as a fetched page is: it
    reaches no reader, no persisted payload and no replayed prompt, and the
    schema on this span binds the decode from its first token, so nothing
    written in span one can change what comes back (Guardrail #11).

    The closing marker is written here rather than taken from the reply.
    llama-server excludes a stop string from the content it returns, so a reply
    that stopped at the marker does not carry it - and a span that ran to its
    budget never wrote one at all. Writing it closes both.
    """
    close = markers.thinking_close
    if close is None:
        raise ValueError(
            "these markers declare no thinking_close, so nothing may be spliced into this "
            "prompt - a caller reached for a second span on an envelope that does not think"
        )
    return {**answer, "prompt": str(answer["prompt"]) + thought + close}


def one_reply(*, thought: Completion, answer: Completion) -> Completion:
    """Two spans of one call, as the single reply the rest of the pipeline reads.

    **The thinking span contributes its cost and not one character of its
    content.** What comes out carries span two's words, span two's finish reason
    and span two's prompt accounting; the token counts and the clocks are the
    pair's, because one item made one call and a ledger that recorded only the
    answer would under-report every thinking run.

    `prompt_tokens` and `cached_tokens` are span two's own. Their difference is
    what span two really had to prefill, which is the one number that settles
    whether the slot held the thinking or re-read it. The three slot facts ride
    with them for the same reason and by the same mechanism - `replace` carries
    what it is not told to change - so a row's slot columns and its cache count
    describe one span rather than two.
    """
    return replace(
        answer,
        completion_tokens=thought.completion_tokens + answer.completion_tokens,
        prefill_ms=thought.prefill_ms + answer.prefill_ms,
        decode_ms=thought.decode_ms + answer.decode_ms,
    )


def continued_completion_payload(
    first: Mapping[str, Any],
    *,
    reply: str,
    user: str,
    output_schema: dict[str, Any],
    markers: TurnMarkers,
    max_answer_tokens: int,
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

    `first` is the first call's ANSWER body, never its thinking span. The
    thinking span carries no grammar and a budget of its own, and building a
    continuation on it would send the second call unconstrained.

    `reply` is the first call's own answer content, replayed verbatim. It is a
    string the model wrote and it is not trusted any further here than a fetched
    page would be - it has already been parsed against a closed schema, and what
    it can reach downstream is bounded by that schema and not by this turn.
    """
    return {
        **first,
        "prompt": continued_prompt(str(first["prompt"]), reply=reply, user=user, markers=markers),
        "n_predict": max_answer_tokens,
        "json_schema": output_schema,
    }


def _reported(value: object) -> int | None:
    """One of the server's own counts, or None where the reply did not carry it.

    **Absent is not zero.** Slot 0 is a real slot and a cold slot really holds
    nothing, so a field that defaulted to 0 would read downstream as a
    measurement nobody took. A value that is not a whole number is absent too:
    these fill an instrument column, and an instrument may not cost an item.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _first_token_choices(payload: Mapping[str, Any], *, at: int) -> tuple[TokenChoice, ...]:
    """What the server said it could have written at one position, likeliest first.

    Read out of `top_logprobs`, which is the one spelling llama-server answers
    `n_probs` with, and out of nothing else. A reply shaped some other way
    leaves this empty rather than being guessed at: the column it fills is
    nullable, and an alternative reconstructed from a field that meant something
    else reads downstream as a measurement somebody took.

    **One position, and which one is the caller's to say.** Every position after
    the answer's opening is bound by what that opening chose, so a reading taken
    further in reports on the shape rather than on the model. Where the answer
    opens is a fact about the caller's own spans, not about this layer - so the
    number is handed in, and a position the reply does not carry leaves this
    empty for the same reason a missing field does.
    """
    positions = payload.get("completion_probabilities")
    if not isinstance(positions, list) or not 0 <= at < len(positions):
        return ()
    first = positions[at]
    alternatives = first.get("top_logprobs") if isinstance(first, Mapping) else None
    if not isinstance(alternatives, list):
        return ()
    choices = [
        TokenChoice(
            token_id=int(entry["id"]),
            token=str(entry["token"]),
            logprob=float(entry["logprob"]),
        )
        for entry in alternatives
        if isinstance(entry, Mapping) and {"id", "token", "logprob"} <= entry.keys()
    ]
    return tuple(sorted(choices, key=lambda choice: choice.logprob, reverse=True))


def parse_completion(body: str, *, answer_at: int = 0) -> Completion:
    """Read the envelope. Nothing here trusts the content yet.

    Two envelopes, because the server answers two routes and each names its
    fields its own way. The chat route returns `choices`, a `usage` block and a
    `finish_reason`; the rendered-completion route returns `content`, its token
    counts at the top level, and a `stop_type` whose budget word is `limit`.
    The `timings` block is the same on both.

    `answer_at` is which decoded position the answer opens at. Zero on a decode
    that opens on the answer, which is every call this pipeline makes today; a
    caller whose span writes something in front of the answer names the offset
    rather than having one guessed here.

    `reasoning` stays empty on the rendered-completion route, and that is a
    property rather than a gap: the split `Completion.reasoned` exists to catch
    is the chat template moving a think block into `reasoning_content`, and a
    route with no template applies none. Anything the model writes inline
    arrives in `content`, where each caller's own cleaner already removes it.

    **A reply that named no reason for stopping carries none.** Both routes used
    to read an absence as `stop`, which is the one reading that cannot be told
    from a real clean stop afterwards - so an unreported ending reached the
    census as a reported one, on every row, for ever.

    **The three slot facts are read here and derived nowhere else.** This is the
    only place that can tell a field the server omitted from a field it set to
    zero, and `prefix_reused` is taken off the same `cache_n` that
    `cached_tokens` is, so the boolean and the count cannot disagree about one
    reply.
    """
    payload = json.loads(body)
    # llama.cpp reports prefill and decode separately; a runtime that does not
    # leaves the rates absent rather than blending them into one wrong number.
    timings = payload.get("timings") or {}
    prefill_ms = round(float(timings.get("prompt_ms", 0.0)))
    decode_ms = round(float(timings.get("predicted_ms", 0.0)))
    cached_tokens = int(timings.get("cache_n", 0))
    slot_id = _reported(payload.get("id_slot"))
    slot_tokens_held = _reported(payload.get("tokens_cached"))
    prefix_reused = cached_tokens > 0 if "cache_n" in timings else None
    first_token_choices = _first_token_choices(payload, at=answer_at)
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
            finish_reason=choices[0].get("finish_reason"),
            prefill_ms=prefill_ms,
            decode_ms=decode_ms,
            cached_tokens=cached_tokens,
            slot_id=slot_id,
            slot_tokens_held=slot_tokens_held,
            prefix_reused=prefix_reused,
            first_token_choices=first_token_choices,
        )
    if "content" not in payload:
        raise ValueError("the runtime returned neither a choice nor a completion")
    stop_type = payload.get("stop_type")
    return Completion(
        content=payload.get("content") or "",
        prompt_tokens=int(payload.get("tokens_evaluated", 0)),
        completion_tokens=int(payload.get("tokens_predicted", 0)),
        finish_reason=None if stop_type is None else _STOP_TYPES.get(stop_type, str(stop_type)),
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        cached_tokens=cached_tokens,
        slot_id=slot_id,
        slot_tokens_held=slot_tokens_held,
        prefix_reused=prefix_reused,
        first_token_choices=first_token_choices,
    )


def post(
    payload: dict[str, Any],
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float,
    answer_at: int = 0,
) -> Completion:
    """The only place an item is sent for summarizing. Loopback only, by construction."""
    outbound = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(outbound, timeout=timeout) as response:
        return parse_completion(response.read().decode("utf-8"), answer_at=answer_at)


def _sibling(endpoint: str, path: str) -> str:
    """Another route on the same server an endpoint names.

    Derived rather than configured, so a caller that points the run at another
    port cannot ask one server for a template and another for an answer.
    """
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def props_url(endpoint: str = DEFAULT_ENDPOINT) -> str:
    """The `/props` address on the server a chat-completions endpoint names."""
    return _sibling(endpoint, _PROPS_PATH)


def completion_url(endpoint: str = DEFAULT_ENDPOINT) -> str:
    """The rendered-completion address on the server an endpoint names."""
    return _sibling(endpoint, _COMPLETION_PATH)


def apply_template_url(endpoint: str = DEFAULT_ENDPOINT) -> str:
    """Where the server renders a conversation with the model's own chat template."""
    return _sibling(endpoint, _APPLY_TEMPLATE_PATH)


def tokenize_url(endpoint: str = DEFAULT_ENDPOINT) -> str:
    """Where the server turns a string into the token ids it would really read."""
    return _sibling(endpoint, _TOKENIZE_PATH)


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


# --- What the server settles before the first item --------------------------
#
# The turn markers are read off the model's own rendering here, so this
# project's render IS the template's render rather than a hand-transcribed copy
# of it. Two things are still asked rather than assumed: whether the sanitizer
# can strip the markers that came back (Guardrail #11), and whether the decoder
# is still held to the schema it is given.
#
# **Neither has a skip flag, and an unread proof refuses.** A run that skips
# them is back to worse-summaries-and-no-error with extra ceremony. A refusal
# costs one step where the failure it prevents costs a day of summaries nobody
# reconciled.
#
# Cost, on a stock ubuntu-latest (Guardrail #2): three template renders and one
# completion of at most PROBE_OUTPUT_TOKENS tokens. It runs once per server
# rather than once per run, because a shard starts its own.


#: The turns the derivation renders. Short and about nothing: what is being read
#: back is the SHAPE of the render, so the content only has to be stable, unique
#: and free of any marker.
PROBE_SYSTEM: Final = "You are a probe."
PROBE_USER: Final = "Answer with the one word this shape allows."
#: The turn a second call adds, so its prompt is the first one plus what came
#: back plus one more turn - the exact shape a real item's two calls take. The
#: derivation reuses it as the second user turn of its history render.
PROBE_FOLLOW_UP: Final = "Answer once more."
#: What already-written reply the history render carries. It sits between two
#: user turns so the bytes that close a turn and open the next one can be read
#: off one rendering.
PROBE_REPLY: Final = "The earlier reply."
#: The only value the constrained-decoding case's schema admits.
PROBE_ANSWER: Final = "probe"
#: The decode budget for one probe call. Not a tunable: the grammar admits
#: exactly one short document, so this is a ceiling on a shape that cannot vary,
#: and raising it would only lengthen a refusal (Guardrail #6).
PROBE_OUTPUT_TOKENS: Final = 32

#: What every derived marker is asked about before a prompt is built from it.
#: The keys are the marker names a refusal has to name; a forged turn is spelled
#: with the bytes an attacker would have to write into an article, and a turn
#: opening carries a role, so it is checked once per role.
_BOUNDARY_ADVICE: Final = (
    "An article carrying that marker would reach this model with the turn "
    "boundary intact. Teach the family to backend/idhazh/sanitize.py and move "
    "SANITIZER_VERSION with it, or name a model whose markers it already strips"
)


class ProbeRefusedError(RuntimeError):
    """Something the server had to settle did not hold, so no item runs.

    The message names both sides - what came back and what could not be made of
    it - because a refusal that names only one of them sends the reader to the
    wrong file.
    """


def one_document_schema(
    output_schema: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A schema exactly one document satisfies, and that document.

    Built from the schema this run really sends, at call time, never from a
    fixture: the real schema is generated from a model, so a committed copy
    would be a second answer that drifts out of sync in silence (Guardrail #3).
    What is borrowed is the field the real reply is keyed on, so the probe asks
    the grammar for the same shape of thing the run asks it for.
    """
    required = [name for name in (output_schema.get("required") or []) if isinstance(name, str)]
    field = required[0] if required else "answer"
    schema = {
        "type": "object",
        "properties": {field: {"type": "string", "const": PROBE_ANSWER}},
        "required": [field],
        "additionalProperties": False,
    }
    return schema, {field: PROBE_ANSWER}


def decoding_still_constrains(*, reply: str, only: Mapping[str, Any]) -> None:
    """Case 3. The grammar is still as narrow as the schema that built it.

    One call under a schema exactly one document satisfies. A reply that is
    anything else means the schema-to-grammar converter dropped a feature, so
    the decoder is looser than the shape every item is held to - and nothing
    else in the pipeline can see that, because a looser grammar still accepts
    every good reply.
    """
    wanted = json.dumps(dict(only), sort_keys=True)
    try:
        got = json.loads(reply)
    except json.JSONDecodeError:
        got = None
    if got == dict(only):
        return
    raise ProbeRefusedError(
        "the decoder is not held to the schema it was given: the only document the "
        f"grammar admits is {wanted}, and the server returned {reply!r}. Constrained "
        "decoding is the control that survives an injection, so a run may not start "
        "without it"
    )


def _ask(url: str, payload: Mapping[str, Any] | None, *, timeout: float) -> Any:
    """One start-up request. A server that will not answer refuses the run.

    Unlike `props`, which records an absence and lets the stage carry on. What
    is being asked here is what every prompt will be built out of, and an
    unanswered question is not a yes.
    """
    outbound = (
        request.Request(url, method="GET")
        if payload is None
        else request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    )
    try:
        with request.urlopen(outbound, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as unreachable:
        raise ProbeRefusedError(
            f"the server did not answer {url}, so the turn markers cannot be read off "
            f"its own rendering: {unreachable}. Neither start-up proof has a skip flag"
        ) from unreachable


def _rendered_by_the_server(
    endpoint: str,
    conversation: list[dict[str, str]],
    *,
    keyword: str | None,
    thinking: bool,
    timeout: float,
) -> str:
    """One rendering the model's own template made, asked for as a real call asks.

    The keyword comes from the entry rather than from a literal here. It is a
    name in somebody else's Jinja source, so spelling it in this file would send
    one model's variable to every model.
    """
    body = _ask(
        apply_template_url(endpoint),
        {
            "messages": conversation,
            **({"chat_template_kwargs": {keyword: thinking}} if keyword is not None else {}),
        },
        timeout=timeout,
    )
    prompt = body.get("prompt") if isinstance(body, Mapping) else None
    if not isinstance(prompt, str) or not prompt:
        raise ProbeRefusedError(
            "the server rendered no prompt for the turns it was handed, so no marker "
            "can be read off this model's own template"
        )
    return prompt


def _where(rendered: str, sentinel: str, *, inside: str) -> int:
    """Where one turn's text sits in a rendering, refusing anything but one copy.

    Two copies would make every byte offset behind the second one ambiguous, and
    the markers are exactly the bytes between the offsets.
    """
    found = rendered.count(sentinel)
    if found == 1:
        return rendered.index(sentinel)
    raise ProbeRefusedError(
        f"this model's template wrote {sentinel!r} {found} times into its rendering of "
        f"{inside}, and a marker can only be read off a turn that appears once. The "
        "template rewrites or repeats what it is given, so nothing here can say where "
        "one turn ends"
    )


def _shared_front(first: str, second: str) -> str:
    end = 0
    while end < min(len(first), len(second)) and first[end] == second[end]:
        end += 1
    return first[:end]


def _shared_back(first: str, second: str) -> str:
    start = 0
    while start < min(len(first), len(second)) and first[-1 - start] == second[-1 - start]:
        start += 1
    return first[len(first) - start :]


def _role_placeholder(*, openings: Mapping[str, str], model_id: str) -> Template:
    """The turn opening with the role lifted back out of it.

    Two openings of the same template differ in the role word and nowhere else,
    so what they share at the front and at the back IS the marker and what is
    left in the middle is the role. `${role}` in braces rather than `$role`,
    because a template whose opening continues with a letter would otherwise
    read the placeholder and that letter as one name.

    A template that renames a role - `System` for `system` - cannot be rebuilt
    this way, and refuses here rather than rendering every turn under a role
    header the model never writes.
    """
    first, second = (openings[role] for role in _TURN_ROLES)
    front = _shared_front(first, second)
    back = _shared_back(first[len(front) :], second[len(front) :])
    rebuilt = {role: front + role + back for role in _TURN_ROLES}
    if rebuilt != dict(openings):
        raise ProbeRefusedError(
            f"the turn opening this model's template writes for {model_id!r} cannot be "
            f"read as one marker with the role inside it: it opens a turn {first!r} for "
            f"{_TURN_ROLES[0]} and {second!r} for {_TURN_ROLES[1]}, which differ "
            "somewhere other than the role word. This project renders a turn by "
            "substituting the role into one opening, so a template that spells a role "
            "its own way has to be read by a rule this one does not have"
        )
    return Template(front + "${" + TURN_ROLE + "}" + back)


def _folded_role_placeholder(user_opening: str, *, model_id: str) -> Template:
    """The turn opening of a template with no system role.

    Only the user turn exists to read, so the role is found by name inside it.
    One occurrence or nothing: two would make the substitution ambiguous, and
    none means the opening carries no role header at all - a prompt that renders
    cleanly and says nothing about who is speaking.
    """
    folded_role = _TURN_ROLES[1]
    if user_opening.count(folded_role) != 1:
        raise ProbeRefusedError(
            f"this model's template has no system role, and the turn opening it writes "
            f"for {model_id!r} is {user_opening!r}, which does not name {folded_role!r} "
            "exactly once. A turn with no role header renders cleanly and says nothing "
            "about who is speaking"
        )
    front, _, back = user_opening.partition(folded_role)
    return Template(front + "${" + TURN_ROLE + "}" + back)


def _the_boundary_can_hold(markers: TurnMarkers, *, model_id: str) -> None:
    """Every marker a forged turn could be spelled with, asked of the sanitizer.

    The control-token pattern in `idhazh.sanitize` is what keeps a forged turn
    out of an article (Guardrail #11), and it knows the families it was written
    for. A server may load weights from a family it does not - and then the
    first article carrying that family's markers is what finds out, which is
    finding out too late. So the question is asked once, over the markers this
    server really renders with, before any article reaches a prompt.

    `system_joiner` is not one of them. It separates two blocks inside one turn
    rather than opening or closing a turn, and every template that folds joins
    with ordinary whitespace - a rule demanding the pattern recognise it would
    refuse a joiner of two newlines.

    `safe_substitute`, where `TurnMarkers.turn` is strict. A marker naming some
    other placeholder is a real failure with a message of its own: it raises at
    the first render. Repeating it here as a `KeyError` would only bury the one
    this function exists to report.
    """
    forgeable: dict[str, str] = {
        f"turn_opening.{role}": markers.turn_opening.safe_substitute({TURN_ROLE: role})
        for role in _TURN_ROLES
    }
    forgeable["turn_closing"] = markers.turn_closing
    forgeable["reply_opening"] = markers.reply_opening
    forgeable["reply_opening_thinking"] = markers.reply_opening_thinking
    refuse_markers_the_boundary_cannot_hold(model_id, forgeable)


def refuse_markers_the_boundary_cannot_hold(model_id: str, markers: Mapping[str, str]) -> None:
    """A marker the sanitizer cannot strip refuses the run, naming the marker.

    A plain mapping of marker name to rendered marker, so what is asked does not
    depend on where the markers came from. It moved here from configuration load
    on 2026-09-21, when the markers stopped being typed by a person and started
    being read off the model's own template; what it refuses did not change.
    """
    for field, marker in markers.items():
        surviving = why_a_forged_turn_would_survive(marker)
        if surviving is None:
            continue
        raise ProbeRefusedError(
            f"the turn markers this server derived for model {model_id!r} are refused: "
            f"{field} renders {marker!r}, and {surviving}. {_BOUNDARY_ADVICE}"
        )


def turn_markers_from_renderings(
    *,
    model_id: str,
    plain: str,
    thinking: str,
    history: str,
    thinking_close: str | None,
    thinking_kwarg: str | None,
) -> TurnMarkers:
    """The markers a model's own template writes, read back off three of its renderings.

    Every marker is the bytes BETWEEN two turns whose text this project chose,
    so nothing here is guessed: the offsets are known and the segments between
    them are the markers. `history` carries a reply between two user turns,
    which is the one rendering where the bytes that close a turn sit next to the
    bytes that open the next one - that pair is what splits a closing marker
    from an opening one without knowing either in advance.

    **A rendering that opens with a preamble refuses.** Some templates write a
    sequence token once at the front of a whole conversation, and this project
    renders turn by turn with nothing in front, so a preamble would be repeated
    at every turn. It is caught here rather than in a prompt: the closing marker
    is read off a seam in the middle of a conversation, and a preamble makes
    that seam disagree with the front of the rendering.

    **What this cannot settle is a template family none of the committed models
    uses.** A template that renames a role, repeats a turn's text, or writes a
    preamble is refused at server start, before the first article - which is
    where a family this rule cannot read is found.
    """
    user_opening_at = _where(history, PROBE_USER, inside="a conversation with a reply in it")
    reply_at = _where(history, PROBE_REPLY, inside="a conversation with a reply in it")
    follow_up_at = _where(history, PROBE_FOLLOW_UP, inside="a conversation with a reply in it")
    if not user_opening_at < reply_at < follow_up_at:
        raise ProbeRefusedError(
            "this model's template reordered the turns it was handed, so the bytes "
            "between them are not the markers that separate them"
        )

    user_opening = history[:user_opening_at]
    seam = history[reply_at + len(PROBE_REPLY) : follow_up_at]
    if not user_opening or not seam.endswith(user_opening) or seam == user_opening:
        raise ProbeRefusedError(
            f"this model's template closes a turn and opens the next one with {seam!r}, "
            f"and opens its first turn with {user_opening!r}. The second is not the end "
            "of the first, so the template writes something once at the front of a "
            "conversation that this project would have to repeat at every turn"
        )
    turn_closing = seam[: len(seam) - len(user_opening)]

    history_tail = history[follow_up_at + len(PROBE_FOLLOW_UP) :]
    if not history_tail.startswith(turn_closing) or history_tail == turn_closing:
        raise ProbeRefusedError(
            f"this model's template ends a generation prompt with {history_tail!r}, "
            f"which does not begin by closing the last turn with {turn_closing!r}. "
            "Nothing here can say where the reply is meant to start"
        )
    reply_opening = history_tail[len(turn_closing) :]

    system_at = _where(plain, PROBE_SYSTEM, inside="a system turn and a user turn")
    user_at = _where(plain, PROBE_USER, inside="a system turn and a user turn")
    if system_at > user_at:
        raise ProbeRefusedError(
            "this model's template put the system text behind the user text, so the "
            "instructions no longer open the conversation"
        )
    head = plain[:system_at]
    between = plain[system_at + len(PROBE_SYSTEM) : user_at]
    if plain[user_at + len(PROBE_USER) :] != turn_closing + reply_opening:
        raise ProbeRefusedError(
            "this model's template ends a two-turn conversation differently from a "
            "longer one, so the bytes a reply opens on are not one marker"
        )

    if between == turn_closing + user_opening:
        placement, joiner = SystemPlacement.OWN_TURN, ""
        turn_opening = _role_placeholder(
            openings={"system": head, "user": user_opening}, model_id=model_id
        )
    elif head == user_opening and between:
        # No system role in this template, so the system text opens the first
        # user turn behind whatever the template joins the two blocks with.
        placement, joiner = SystemPlacement.FOLD_INTO_FIRST_USER, between
        turn_opening = _folded_role_placeholder(user_opening, model_id=model_id)
    else:
        raise ProbeRefusedError(
            f"this model's template neither gives the system text a turn of its own nor "
            f"folds it into the first user turn: it opens with {head!r} and puts "
            f"{between!r} between the system text and the user text. A third placement "
            "needs a rule this project does not have"
        )

    thinking_tail = thinking[_where(thinking, PROBE_USER, inside="the same two turns") :]
    thinking_tail = thinking_tail[len(PROBE_USER) :]
    if not thinking_tail.startswith(turn_closing) or thinking_tail == turn_closing:
        raise ProbeRefusedError(
            "asking this model's template for reasoning changed where a turn ends, so "
            f"the two openings are not one envelope: it ended with {thinking_tail!r}"
        )

    markers = TurnMarkers(
        turn_opening=turn_opening,
        turn_closing=turn_closing,
        reply_opening=reply_opening,
        reply_opening_thinking=thinking_tail[len(turn_closing) :],
        system_role=placement,
        system_joiner=joiner,
        thinking_close=thinking_close,
        thinking_kwarg=thinking_kwarg,
    )
    _the_boundary_can_hold(markers, model_id=model_id)
    return markers


#: One derivation per server and per entry, because a bench holding two entries
#: on two servers would otherwise render the second model's prompts with the
#: first model's markers, and the grammar would accept every reply.
_DERIVED: Final[dict[tuple[str, str, str | None, str | None], TurnMarkers]] = {}


def derive_turn_markers(
    endpoint: str = DEFAULT_ENDPOINT,
    *,
    entry: ModelEntry,
    timeout: float,
) -> TurnMarkers:
    """Read this model's turn markers off its own template. Three renders, no decode.

    The markers are held in memory for as long as the process lives and written
    nowhere. A file of them would be a second copy of somebody else's template
    that a model swap can leave behind, which is what they were until now.

    Two facts a rendering cannot return come from the entry beside the weights:
    the marker this model writes to CLOSE a reasoning block, which a generation
    prompt never contains, and the name of the template variable that turns
    reasoning on, which is an input to the render rather than an output of it.
    """
    held = _DERIVED.get(
        key := (endpoint, entry.id, entry.thinking_close, entry.thinking_kwarg)
    )
    if held is not None:
        return held
    two_turns = [
        {"role": "system", "content": PROBE_SYSTEM},
        {"role": "user", "content": PROBE_USER},
    ]
    plain = _rendered_by_the_server(
        endpoint, two_turns, keyword=entry.thinking_kwarg, thinking=False, timeout=timeout
    )
    derived = turn_markers_from_renderings(
        model_id=entry.id,
        plain=plain,
        # A template that reads no keyword renders one way whatever it is asked,
        # so the second call would repeat the first. The entry refuses a null
        # keyword beside a closing marker, so nothing here needs both openings.
        thinking=(
            _rendered_by_the_server(
                endpoint,
                two_turns,
                keyword=entry.thinking_kwarg,
                thinking=True,
                timeout=timeout,
            )
            if entry.thinking_kwarg is not None
            else plain
        ),
        history=_rendered_by_the_server(
            endpoint,
            [
                {"role": "user", "content": PROBE_USER},
                {"role": "assistant", "content": PROBE_REPLY},
                {"role": "user", "content": PROBE_FOLLOW_UP},
            ],
            keyword=entry.thinking_kwarg,
            thinking=False,
            timeout=timeout,
        ),
        thinking_close=entry.thinking_close,
        thinking_kwarg=entry.thinking_kwarg,
    )
    _DERIVED[key] = derived
    return derived


def token_pieces(endpoint: str, text: str, *, timeout: float) -> list[str]:
    """How the vocabulary SPELLS a string, token by token, in order.

    `with_pieces` asks the tokenizer for the text of each token beside its id,
    so a caller reading a window the server reported can match a token by the
    spelling it came back as. That window carries text, and an id is comparable
    only against a table this repository would have to keep.

    `add_special` stays off: a sequence token the template writes belongs to the
    template, not to the string being asked about.

    A build that answers with bare ids is refused rather than guessed at. Reading
    an id as a spelling would put a number where a word goes and every match
    downstream would quietly miss.
    """
    body = _ask(
        tokenize_url(endpoint),
        {"content": text, "add_special": False, "with_pieces": True},
        timeout=timeout,
    )
    tokens = body.get("tokens") if isinstance(body, Mapping) else None
    if not isinstance(tokens, list) or not tokens:
        raise ProbeRefusedError(
            "the server tokenised nothing, so the vocabulary cannot be read as spellings"
        )
    pieces = [token.get("piece") for token in tokens if isinstance(token, Mapping)]
    if len(pieces) != len(tokens) or not all(isinstance(piece, str) for piece in pieces):
        raise ProbeRefusedError(
            "the server answered with_pieces as bare ids, so this build cannot say how "
            "it spells a token and no window can be matched against a verdict"
        )
    return [str(piece) for piece in pieces]


def prove_the_entry(
    *,
    model: ModelEntry,
    output_schema: Mapping[str, Any],
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float,
) -> None:
    """Read this model's markers off its own template, then prove the decoder is bound.

    The markers cost three renders and no decode, and the boundary check rides
    inside the derivation. Then one short decode under a schema exactly one
    document satisfies: the derivation cannot say whether our own generated
    schema has grown a construct the grammar converter drops, and a looser
    decoder still accepts every good reply, so nothing else in the pipeline
    would see it.

    `output_schema` is handed in rather than imported. The schema this run sends
    is built in `idhazh.classify.calls`, which imports this module, so taking it
    as an argument is what keeps the model layer at the bottom of the graph
    (`CLAUDE.md` section 4) - and it means this is held to whatever shape the
    caller really uses rather than to a copy of it.
    """
    markers = derive_turn_markers(endpoint, entry=model, timeout=timeout)
    schema, only = one_document_schema(output_schema)
    reply = post(
        completion_payload(
            model_id=model.id,
            system=PROBE_SYSTEM,
            user=PROBE_USER,
            output_schema=schema,
            server=model.server,
            request=model.request,
            markers=markers,
            max_answer_tokens=PROBE_OUTPUT_TOKENS,
        ),
        endpoint=completion_url(endpoint),
        timeout=timeout,
    )
    decoding_still_constrains(reply=reply.content, only=only)
