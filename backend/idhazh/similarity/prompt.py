"""What exactly did the judge read, and what is that worth as a digest?

Two digests ride on every judged row, because a verdict is only comparable with
another verdict taken under the same ask. The words the model read and the shape
it was held to are both content, and content that moved without saying so turns
a year of counts into a year of two different measurements. They are digests
rather than the text itself for the ordinary reason: a prompt does not fit in a
CSV cell.

**The prompt digest covers every word of ours the model reads, not only the
system turn.** The labels, the fence and the re-ask are ours too, and each one
can change a verdict, so `prompt_text` is what gets digested.

**Both are taken over the rendered text, never over the file on disk.** A file
read under another newline convention is different bytes and the same prompt, so
a digest over the bytes would archive the record for a checkout setting.

The user turn is the other half of this file's one question. Two summaries from
two strangers' web pages meet in one context here, so each one goes inside
`sanitize.untrusted_block` and the ask is repeated after both of them - the last
thing the model reads before it answers is ours (Guardrail #11).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Final

from idhazh.contracts.base import derive_text_digest
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.story_similarity_pair import SameStoryVerdict
from idhazh.sanitize import untrusted_block

PROMPT_PATH: Final = Path(__file__).parent.parent / "prompts" / "judge_same_story.txt"

#: What labels each summary in the user turn. Two words rather than "Article A"
#: and "Article B": the pair is judged again with the two swapped, and a label
#: that reads like an identity invites the model to carry an opinion of A across
#: the swap. First and second are positions, which is all they are.
FIRST_LABEL: Final = "First:"
SECOND_LABEL: Final = "Second:"

#: The ask, repeated after both blocks. It is not decoration and it is not a
#: control either - a sentence cannot out-argue a better-worded attack. What it
#: does is cost an injection the last word: text inside either block is followed
#: by ours before the model starts writing.
REASK: Final = "Do these two report on the exact same event? Answer YES, NO or UNCLEAR."

#: The one opening the grammar spends before a verdict word. It is not
#: politeness: most vocabularies spell ` YES` and `YES` as different tokens, and
#: many chat templates end the assistant header in a way that makes the
#: space-prefixed one the model's natural first choice. A grammar admitting only
#: the bare literal would force a pick among three tokens the model considered
#: unlikely, the reply would still parse, and nothing downstream could tell.
OPTIONAL_OPENING: Final = " "

#: Every string the decoder may emit, and the whole of it: each verdict bare and
#: each verdict behind the optional opening. Built from the enum rather than
#: listed, because the margin rule buckets a window against this tuple and a
#: second hand-written list is a second thing to keep in step with the grammar.
LEGAL_REPLIES: Final[tuple[str, ...]] = tuple(
    f"{opening}{verdict.value}"
    for opening in ("", OPTIONAL_OPENING)
    for verdict in SameStoryVerdict
)

#: What the decoder may emit, as the GBNF it is held to. Rendered from the same
#: enum `LEGAL_REPLIES` is, so the grammar and the set a window is read against
#: cannot drift apart. The exact string is asserted in the test module: it is
#: digested onto every row and into the record's own stamp, so a respelling that
#: admits the same words would still archive the record.
GRAMMAR: Final = 'root ::= " "? ({})'.format(
    " | ".join(f'"{verdict.value}"' for verdict in SameStoryVerdict)
)

#: How many tokens one reply may spend. Derived from the grammar rather than
#: chosen: the longest string it admits is a space and `UNCLEAR`, and no
#: vocabulary spells that in more than four tokens. It is not a dial - a budget
#: below what the grammar admits truncates a legal reply - so it moves when the
#: grammar moves and sits beside it (Guardrail #6).
REPLY_TOKENS: Final = 4

#: Turns a string into the ids a vocabulary reads it as. The judge asks the
#: server that is about to decode, because the answer is a property of the
#: weights rather than of this repository.
Tokenizer = Callable[[str], Sequence[int]]

#: Turns a string into the tokens a vocabulary reads it as, as text. The margin
#: is bucketed on what a token SPELLS rather than on an id, because the server
#: reports both beside each alternative and the spelling is what says which
#: verdict a token opens.
TextTokenizer = Callable[[str], Sequence[str]]


@lru_cache(maxsize=1)
def _template() -> Template:
    return Template(PROMPT_PATH.read_text(encoding="utf-8"))


def system_turn() -> str:
    """The instructions, as the model reads them.

    Read through `Template` although the file interpolates nothing today, which
    is what `summarize.py` does with its own. A value that later belongs in the
    ask is then a `$name` and a substitution rather than an f-string somebody
    adds beside this line, and a `$name` nobody filled raises here instead of
    reaching a model as the literal it looks like.
    """
    return _template().substitute()


def user_turn(left: DigestItem, right: DigestItem) -> str:
    """The two summaries, fenced as data, with the ask after both of them.

    Only the summaries. Not the similarity score, which would contaminate the
    verdict with the number this whole feature exists to set; not the source
    names, which invite the model to reason about publishers rather than events;
    not the publication times, which answer the question by proxy.

    `untrusted_block` sanitizes what it fences rather than trusting this caller,
    so neither summary can close the block it sits in. No fence of our own is
    invented here: a second fence shape is untrusted text sitting somewhere the
    prompt's "those blocks are DATA" sentence does not reach.
    """
    return _rendered(left.summary, right.summary)


def _rendered(left: str, right: str) -> str:
    """The user turn's own shape, with two summaries dropped into it.

    Split out of `user_turn` so `prompt_text` can render the same shape with
    nothing in it. Rendering it a second way would let the digest describe a
    layout the model never reads, which is the one failure a digest exists to
    make impossible.
    """
    return "\n".join(
        (
            FIRST_LABEL,
            untrusted_block(left),
            "",
            SECOND_LABEL,
            untrusted_block(right),
            "",
            REASK,
        )
    )


def grammar() -> str:
    """The GBNF the decoder is held to, declared here and nowhere else."""
    return GRAMMAR


def blank_user_turn() -> str:
    """The user turn's shape with nothing in it, for a caller with no pair to hand.

    The same rendering the digest covers, which is what makes it safe to build a
    request body around when the question is about the ask rather than about two
    items - the stamp digests the body minus its prompt, so what stands in for
    the pair changes nothing it reads and a second rendering would still have to
    be kept in step with this one.
    """
    return _rendered("", "")


def prompt_text() -> str:
    """Everything the model reads that is not the pair itself.

    The system turn, both position labels, the fence the two summaries sit in,
    and the ask repeated after them. All of it is ours, all of it can be edited,
    and every part of it can change a verdict - so all of it is what the digest
    covers. Until 2026-09-18 the digest was the system turn alone, which left a
    reworded re-ask moving verdicts with nothing on the row to say so.

    The two summaries are left out and nothing stands in for them. They are the
    pair, they differ on every call, and a digest that moved with them would say
    nothing at all about the ask.
    """
    return "\n".join((system_turn(), blank_user_turn()))


def prompt_digest() -> str:
    """sha256 of `prompt_text`, for the column of that name."""
    return derive_text_digest(prompt_text())


def grammar_digest() -> str:
    """sha256 of the grammar, for the column of that name."""
    return derive_text_digest(grammar())


@lru_cache(maxsize=1)
def first_token_prefixes() -> frozenset[str]:
    """Every non-empty prefix of a legal reply, which is what the grammar admits here.

    This is the size of the alternatives window the judge asks for. A window
    sized to the three verdict WORDS is sized to the answer set, and the answer
    set is not what sits at the first generated position: a token is a prefix of
    a legal string, so ` UNC` and `N` are both things the grammar can open with
    and neither is a verdict. Twenty-five of them come out of six strings, and
    the number is derived here rather than written down anywhere.
    """
    return frozenset(
        reply[:length] for reply in LEGAL_REPLIES for length in range(1, len(reply) + 1)
    )


def verdicts_opened_by(token: str) -> frozenset[SameStoryVerdict]:
    """Which verdicts a returned token could be the start of.

    One leading space is spent first, for the reason the grammar admits one. What
    is left is matched as a prefix, never as a spelling: a vocabulary that writes
    ` UNCLEAR` as ` UNC` plus `LEAR` gives UNCLEAR no probability at all under a
    rule that compares whole words, and the column then reports a two-way gap as
    a three-way one.

    **An empty remainder opens all three, and the caller drops it.** A lone space
    and a lone empty token are both prefixes of every legal reply, so neither
    names a verdict; counting one into all three would add the same mass three
    times. Measured on 2026-09-21, the empty token is really in the window - it
    came back at rank 4 of 25
    (`docs/reference/benchmarks/what-the-margin-rule-changes.md`).

    An empty set is a token the grammar could not have opened with at all.
    """
    text = token[1:] if token.startswith(OPTIONAL_OPENING) else token
    if not text:
        return frozenset(SameStoryVerdict)
    return frozenset(
        verdict for verdict in SameStoryVerdict if verdict.value.startswith(text)
    )


def first_token_openings(tokenizer: TextTokenizer) -> dict[SameStoryVerdict, str]:
    """The token each verdict opens with that opens no other, asked of the vocabulary.

    Asked rather than tabulated. A table of tokens is right for exactly one set of
    weights and says nothing when the weights move, and the property it defends is
    the one the margin rests on: a verdict that no returned token can be
    attributed to scores zero for ever, and the column then reports a two-way gap
    between the other two as though the third had been considered and rejected.

    Both spellings are asked for and one attributable opening is enough. A
    vocabulary that spells ` YES` as a lone space plus `YES` opens that spelling
    with a token naming no verdict, and YES is still readable through its bare
    spelling - which is the case the retired bare-word check could not see,
    because it never asked about the space-prefixed strings at all.
    """
    found: dict[SameStoryVerdict, str] = {}
    for reply in LEGAL_REPLIES:
        tokens = tokenizer(reply)
        if not tokens:
            raise ValueError(f"this vocabulary encodes {reply!r} as no tokens at all")
        opened = verdicts_opened_by(tokens[0])
        if len(opened) == 1:
            found.setdefault(next(iter(opened)), tokens[0])
    unreadable = [verdict.value for verdict in SameStoryVerdict if verdict not in found]
    if unreadable:
        raise ValueError(
            f"this vocabulary opens every spelling of {', '.join(unreadable)} with a "
            "token that opens another verdict too, so no probability read at the first "
            "generated position can tell the three apart"
        )
    return found
