"""What did the model say about this pair, read twice, and how sure was it?

One pair, two calls. The second is the first with the two summaries swapped, and
a pair whose answer changes when the arguments change has said nothing about the
two stories - it has said something about where they sat on the page. So `usable`
means the two readings agree, and a disagreement is never retried: a third
reading with no rule for breaking the tie is a coin toss wearing a number.

**There is no prose path here, on purpose.** The grammar is the control, and a
reply that did not come out of it fails the shard. A parser that could read `I
think these are the same story` back into a YES would restore the whole class of
failure the grammar was put there to remove, and it would restore it on exactly
the days something had already gone wrong with the decoder.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import exp
from typing import Any

from idhazh import config
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.knobs.models import ModelEntry
from idhazh.contracts.story_similarity_pair import SameStoryVerdict
from idhazh.llm.server import (
    Completion,
    TokenChoice,
    answer_span,
    grammar_completion_payload,
    one_reply,
    thinking_span,
)
from idhazh.similarity import prompt

#: The one seam between a verdict and a socket. A judge hands over a request body
#: and is handed back a reply; it holds no address, so no part of a model's
#: output can become one (Guardrail #11).
Client = Callable[[dict[str, Any]], Completion]


class GrammarNotAppliedError(RuntimeError):
    """The reply did not come out of the grammar, so the shard stops here.

    Loud rather than degraded. A constrained decode that quietly stopped being
    constrained writes rows that look exactly like good ones, and every count
    downstream is then a mixture of two measurements with nothing on the row to
    separate them.
    """


@dataclass(frozen=True, slots=True)
class Reading:
    """One call, one order, one verdict."""

    verdict: SameStoryVerdict
    first_token_margin: float | None
    decode_seconds: float
    prompt_tokens: int
    #: How many reasoning spans ran in front of the answer - 0 cold, 1 under a
    #: thinking envelope. `decode_digest` cannot see the difference, because the
    #: only posted key an envelope moves is the prompt and the prompt is not
    #: stamped, so the count is carried rather than derived later.
    thinking_spans: int = 0
    #: What the reasoning span wrote, held for the length of this call and
    #: persisted nowhere. It is model-written text about two strangers' web
    #: pages, so it is trusted no further than a fetched page: it reaches no
    #: reader, no row and no second prompt of ours (Guardrail #11).
    thinking: str = ""


@dataclass(frozen=True, slots=True)
class Judged:
    """Both readings of one pair, and whether they agree."""

    verdict: SameStoryVerdict
    verdict_swapped: SameStoryVerdict
    usable: bool
    first_token_margin: float | None
    decode_seconds: float


def verdict_of(text: str) -> SameStoryVerdict:
    """The three words, exact match, and one leading space spent on the way.

    The space is spent because the grammar admits it: `root ::= " "? (...)`. It
    is the only thing spent. A `.strip()` here would accept a reply with a
    newline and two spaces around it, which is a reply no grammar of three
    literals can produce - so accepting it would be accepting evidence that the
    grammar was not applied.
    """
    word = text[1:] if text.startswith(" ") else text
    try:
        return SameStoryVerdict(word)
    except ValueError:
        raise GrammarNotAppliedError(
            f"the judge answered {text!r}, and the grammar admits only "
            f"{', '.join(verdict.value for verdict in SameStoryVerdict)}. The decode was "
            "not constrained, so nothing this shard wrote can be read as a verdict"
        ) from None


def margin_of(choices: Sequence[TokenChoice]) -> float | None:
    """The gap between the two likeliest VERDICTS, over the mass the grammar admits.

    Three steps, and each one answers a way the raw top-two gap was wrong.

    **Bucketed by prefix.** A window holds tokens, and a token is the opening of
    a legal reply rather than a legal reply. `NO` and ` NO` are one verdict said
    twice, and a rule that subtracts them reports a near-zero gap on a reply the
    model was certain about. Each token is summed into the verdict its stripped
    text opens.

    **Unattributable tokens are dropped.** A lone space and a lone empty token
    are prefixes of every legal reply, so neither says which verdict the model
    was reaching for. Counting one into all three adds the same mass three times
    and moves no gap it should move.

    **Renormalised over what is left.** The window is the model's own
    distribution and not the grammar's - measured, 18 of 25 returned tokens were
    illegal here and they carry mass of their own
    (`docs/reference/benchmarks/what-the-margin-rule-changes.md`). Dividing by
    the legal mass is what turns the number into a gap between the answers the
    caller allowed rather than a gap inside the whole vocabulary.

    None where fewer than two verdicts got any mass at all - a window that named
    one verdict, a window of nothing but illegal tokens, and a server that was
    never asked for alternatives all land here. A 1.0 would read as the model
    agreeing completely with the grammar, which is the opposite of what a window
    that could not say means, and a 0.0 would read as the one thing this column
    exists to catch.
    """
    mass = dict.fromkeys(SameStoryVerdict, 0.0)
    for choice in choices:
        opened = prompt.verdicts_opened_by(choice.token)
        if len(opened) != 1:
            continue
        mass[next(iter(opened))] += exp(choice.logprob)
    legal = sum(mass.values())
    ranked = sorted((share for share in mass.values() if share > 0.0), reverse=True)
    if len(ranked) < 2:
        return None
    return max(0.0, min(1.0, (ranked[0] - ranked[1]) / legal))


def entry_of(settings: config.Settings) -> ModelEntry:
    """Which model entry this judge decodes with, in the one place that decides it.

    `models.judge` where the active models file declares one, and the summariser's
    entry otherwise. The two name the same weights by contract, so a judge role
    changes how a verdict is decoded and never which file the runner's cache has
    to hold - the cache restore is the largest fixed cost in the pipeline
    (Guardrail #2).

    Read here by the decode, by the stamp and by the shard, so a run cannot judge
    under one entry and record another.
    """
    return settings.models.judge or settings.models.summarize


def decode_body(
    settings: config.Settings, *, system: str, user: str
) -> dict[str, Any]:
    """The request body one judging call posts, built once and read three ways.

    The decode runs it, the stamp digests it, and a test asserts on it. A stamp
    built off a config block instead would agree with the config and disagree
    with what went out, which is the one case worth seeing.

    **The temperature is the judging knob's, not the entry's.** The entry pins
    what suits writing a summary; this decode is the one whose answer is compared
    against itself with the two summaries swapped, and that comparison only reads
    position bias while the sampler is adding nothing of its own. `top_p` and
    `seed` still come off the entry, because neither decides anything at
    temperature 0.

    The alternatives window is sized to what the grammar admits at the answer's
    opening - every non-empty prefix of a legal reply - rather than to the three
    verdict words. Sized to the words it holds one verdict spelled two ways and
    nothing else, and `margin_of` then has one verdict to rank and answers null.
    Measured on 2026-09-21: at the old width every reply returned exactly that.
    """
    entry = entry_of(settings)
    tuning = settings.app.assemble.same_story.judging_knobs()
    return grammar_completion_payload(
        model_id=entry.id,
        system=system,
        user=user,
        grammar=prompt.grammar(),
        inference=entry.inference.model_copy(
            update={"temperature": tuning.judge_temperature}
        ),
        turns=entry.turns,
        max_answer_tokens=prompt.REPLY_TOKENS,
        first_token_alternatives=len(prompt.first_token_prefixes()),
    )


def read_once(
    left: DigestItem,
    right: DigestItem,
    *,
    client: Client,
    settings: config.Settings,
) -> Reading:
    """One constrained decode, and the two checks that say it was constrained.

    The model is `judge.entry_of` - the summariser's entry, or a judge role
    declared beside it on the same weights.

    **A reasoning span runs only where the entry declares a closing marker.** An
    entry with none cannot be asked for one: the answer body carries a grammar of
    a few literals, so a span held to it could not write a reasoning block at all,
    and `thinking_span` refuses rather than sending one. Where a marker is
    declared the answer is decoded in span two with the grammar back on and the
    reasoning behind it in the prompt, so the verdict is read off the answer and
    never off the thinking.
    """
    entry = entry_of(settings)
    answer = decode_body(
        settings,
        system=prompt.system_turn(),
        user=prompt.user_turn(left, right),
    )
    started = time.perf_counter()
    if entry.turns.thinks:
        thought = client(
            thinking_span(
                answer,
                turns=entry.turns,
                max_think_tokens=entry.inference.max_think_tokens,
                temperature=entry.inference.temperature,
            )
        )
        reply = one_reply(
            thought=thought,
            answer=client(
                answer_span(answer, thought=thought.content, turns=entry.turns)
            ),
        )
        thinking, spans = thought.content, 1
    else:
        reply = client(answer)
        thinking, spans = "", 0
    elapsed = time.perf_counter() - started
    verdict = verdict_of(reply.content)
    _the_first_token_opened_the_word_that_came_back(reply.first_token_choices, verdict)
    return Reading(
        verdict=verdict,
        first_token_margin=margin_of(reply.first_token_choices),
        decode_seconds=elapsed,
        prompt_tokens=reply.prompt_tokens,
        thinking_spans=spans,
        thinking=thinking,
    )


def judge_pair(
    left: DigestItem,
    right: DigestItem,
    *,
    client: Client,
    settings: config.Settings,
) -> Judged:
    """Both orders, one comparison, no tie-break.

    File order first, so `first_token_margin` on the row is always taken from the
    same call. A margin read off whichever call happened to answer second would
    be two different measurements sharing one column.
    """
    forward = read_once(left, right, client=client, settings=settings)
    swapped = read_once(right, left, client=client, settings=settings)
    return Judged(
        verdict=forward.verdict,
        verdict_swapped=swapped.verdict,
        usable=forward.verdict == swapped.verdict,
        first_token_margin=forward.first_token_margin,
        decode_seconds=forward.decode_seconds + swapped.decode_seconds,
    )


def _the_first_token_opened_the_word_that_came_back(
    choices: Sequence[TokenChoice], verdict: SameStoryVerdict
) -> None:
    """The likeliest first token has to be the opening of the word that arrived.

    Under the grammar those two cannot disagree: it binds the decode from the
    first token, so whatever won position one is what the reply starts with. A
    reply where they differ is a reply something rewrote after the decoder, which
    is the failure a content check alone cannot see.

    A server that reported no alternatives says nothing here and is not refused
    for it - `first_token_margin` is nullable for the same reason. A first token
    that opens more than one verdict says nothing either: a lone space and a lone
    empty token are prefixes of every legal reply, so the word starts at the next
    position and that position is not the one being read.

    Asked through the same rule the margin buckets on, so a token the margin
    credits to a verdict and a token this check accepts for it are one answer.
    """
    if not choices:
        return
    written = choices[0].token
    if verdict in prompt.verdicts_opened_by(written):
        return
    raise GrammarNotAppliedError(
        f"the judge answered {verdict.value} and its likeliest first token was "
        f"{written!r}. Under the grammar those cannot differ, so the reply was shaped "
        "after the decode rather than by it"
    )
