"""What exactly did the judge read, and what is that worth as a digest?

Two digests ride on every judged row, because a verdict is only comparable with
another verdict taken under the same ask. The words the model read and the shape
it was held to are both content, and content that moved without saying so turns
a year of counts into a year of two different measurements. They are digests
rather than the text itself for the ordinary reason: a prompt does not fit in a
CSV cell.

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

#: What the decoder may emit, and the whole of it. The optional leading space is
#: not politeness: most vocabularies spell ` YES` and `YES` as different tokens,
#: and many chat templates end the assistant header in a way that makes the
#: space-prefixed one the model's natural first choice. A grammar admitting only
#: the bare literal would force a pick among three tokens the model considered
#: unlikely, the reply would still parse, and nothing downstream could tell.
GRAMMAR: Final = 'root ::= " "? ("YES" | "NO" | "UNCLEAR")'

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
    return "\n".join(
        (
            FIRST_LABEL,
            untrusted_block(left.summary),
            "",
            SECOND_LABEL,
            untrusted_block(right.summary),
            "",
            REASK,
        )
    )


def grammar() -> str:
    """The GBNF the decoder is held to, declared here and nowhere else."""
    return GRAMMAR


def prompt_digest() -> str:
    """sha256 of the rendered system turn, for the column of that name."""
    return derive_text_digest(system_turn())


def grammar_digest() -> str:
    """sha256 of the grammar, for the column of that name."""
    return derive_text_digest(grammar())


def first_token_ids(tokenizer: Tokenizer) -> tuple[int, int, int]:
    """The id each verdict word opens with, asked of the vocabulary that will write it.

    Encoded rather than tabulated. A table of ids is right for exactly one set of
    weights and says nothing at all when the weights move, and the property these
    defend is the one a single probability read rests on: `first_token_margin`
    reports a three-way distribution off one position, which it can only do while
    the three words still differ there.

    The refusal is the point of the function. A vocabulary that opens two of them
    with the same token does not fail anything visible - every reply still parses
    and every row still writes - it just makes one column meaningless for as long
    as nobody looks.
    """
    yes, no, unclear = (_opening_id(tokenizer, verdict) for verdict in SameStoryVerdict)
    if len({yes, no, unclear}) != 3:
        raise ValueError(
            "this vocabulary opens two of YES, NO and UNCLEAR with the same token "
            f"(YES={yes}, NO={no}, UNCLEAR={unclear}), so one probability read at the "
            "first generated position cannot tell the three apart"
        )
    return yes, no, unclear


def _opening_id(tokenizer: Tokenizer, verdict: SameStoryVerdict) -> int:
    ids = tokenizer(verdict.value)
    if not ids:
        raise ValueError(f"this vocabulary encodes {verdict.value} as no tokens at all")
    return ids[0]
