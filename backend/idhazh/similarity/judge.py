"""What did the model say about this pair, read twice, and how sure was it?

One pair, two calls. The second is the first with the two summaries swapped, and
a pair whose answer changes when the arguments change has said nothing about the
two stories - it has said something about where they sat on the page. So `usable`
means the two readings agree, and a disagreement is never retried: a third
reading with no rule for breaking the tie is a coin toss wearing a number.

**There is no prose path here, on purpose.** The grammar is the control, and a
reply that did not come out of it fails the leg. A parser that could read `I
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
from idhazh.contracts.story_similarity_pair import SameStoryVerdict
from idhazh.llm.server import Completion, TokenChoice, grammar_completion_payload
from idhazh.similarity import prompt

#: The one seam between a verdict and a socket. A judge hands over a request body
#: and is handed back a reply; it holds no address, so no part of a model's
#: output can become one (Guardrail #11).
Client = Callable[[dict[str, Any]], Completion]


class GrammarNotAppliedError(RuntimeError):
    """The reply did not come out of the grammar, so the leg stops here.

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
            "not constrained, so nothing this leg wrote can be read as a verdict"
        ) from None


def margin_of(choices: Sequence[TokenChoice]) -> float | None:
    """The gap between the two likeliest first tokens, as probabilities.

    None where the server reported fewer than two alternatives. A 0.0 there would
    read as the one thing this column exists to catch - a grammar that chose
    while the model was indifferent - and it would read that way on every reply
    from a server that was never asked for alternatives at all.
    """
    if len(choices) < 2:
        return None
    ranked = sorted((exp(choice.logprob) for choice in choices), reverse=True)
    return max(0.0, min(1.0, ranked[0] - ranked[1]))


def read_once(
    left: DigestItem,
    right: DigestItem,
    *,
    client: Client,
    settings: config.Settings,
) -> Reading:
    """One constrained decode, and the two checks that say it was constrained.

    The model is `models.summarize` - the one the digest already runs. Naming a
    second would double the weights the runner's cache carries, and the cache
    restore is the largest fixed cost in the pipeline (Guardrail #2).

    **The temperature is the judging knob's, not the entry's.** The entry pins
    what suits writing a summary; this decode is the one whose answer is
    compared against itself with the two summaries swapped, and that comparison
    only reads position bias while the sampler is adding nothing of its own.
    `top_p` and `seed` still come off the entry, because neither decides
    anything at temperature 0.
    """
    entry = settings.models.summarize
    tuning = settings.app.assemble.same_story.judging_knobs()
    payload = grammar_completion_payload(
        model_id=entry.id,
        system=prompt.system_turn(),
        user=prompt.user_turn(left, right),
        grammar=prompt.grammar(),
        inference=entry.inference.model_copy(
            update={"temperature": tuning.judge_temperature}
        ),
        turns=entry.turns,
        max_answer_tokens=prompt.REPLY_TOKENS,
        first_token_alternatives=len(SameStoryVerdict),
    )
    started = time.perf_counter()
    reply = client(payload)
    elapsed = time.perf_counter() - started
    verdict = verdict_of(reply.content)
    _the_first_token_opened_the_word_that_came_back(reply.first_token_choices, verdict)
    return Reading(
        verdict=verdict,
        first_token_margin=margin_of(reply.first_token_choices),
        decode_seconds=elapsed,
        prompt_tokens=reply.prompt_tokens,
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
    that is only the grammar's own optional space says nothing either: the word
    starts at the next position, and that position is not the one being read.
    """
    if not choices:
        return
    written = choices[0].token
    if not written.strip():
        return
    opened = written[1:] if written.startswith(" ") else written
    if verdict.value.startswith(opened):
        return
    raise GrammarNotAppliedError(
        f"the judge answered {verdict.value} and its likeliest first token was "
        f"{written!r}. Under the grammar those cannot differ, so the reply was shaped "
        "after the decode rather than by it"
    )
