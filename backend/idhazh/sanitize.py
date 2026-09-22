"""The trust boundary's control, crossed exactly once.

Anything the pipeline pulls from the open web is untrusted (Guardrail #11). A
system prompt asking a model to ignore embedded instructions is a request, not
a control - it is written in the same channel as the attack and loses to a
better-worded attack. The controls are this module and the output schema.

Three guarantees, and nothing else:

- `sanitize` removes the machinery an injection needs: the invisible characters
  that hide it, the chat-control tokens that would end the user's turn, the
  encoded blob that smuggles it past a reader, and the address it would
  exfiltrate to.
- `untrusted_block` is the only way source text is ever handed to a model, and
  the text can never close the fence it sits inside, because the fence markers
  do not survive sanitization.
- `why_a_forged_turn_would_survive` answers, for one rendered turn marker,
  whether the first guarantee reaches it. `idhazh.llm.server` asks it of every
  marker it derives from a model's own template at server start and refuses the
  run that fails, so a model from a family this module does not know stops the
  run before the first article rather than opening a turn boundary on it.

The bounds here are structural, not tunable. A knob that weakens the trust
boundary is a knob that gets widened during an incident (CLAUDE.md section 6
names the caps a reasonable operator would move; these are not among them).
"""

from __future__ import annotations

import re
from typing import Final

#: Bumped whenever the transformation below changes. It is a fingerprint input,
#: so a silent edit here would otherwise re-summarize nothing and explain less.
SANITIZER_VERSION: Final = "idhazh-sanitizer-3"

FENCE_OPEN: Final = "<<<UNTRUSTED_SOURCE_TEXT>>>"
FENCE_CLOSE: Final = "<<<END_UNTRUSTED_SOURCE_TEXT>>>"

#: What replaces a removed span, so a sentence still reads and a reader can see
#: that something was taken out rather than silently losing it.
LINK_PLACEHOLDER: Final = "[link]"
BLOB_PLACEHOLDER: Final = "[omitted]"

# Hide an instruction where a human reviewer cannot see it: C0/C1 controls, the
# zero-width family, bidi overrides, and the Unicode tag block - which encodes
# arbitrary ASCII in codepoints that render as nothing at all.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_INVISIBLE = re.compile(
    "[\u00ad\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060-\u2064\ufeff\U000e0000-\U000e007f]"
)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

#: The families of chat-control token the pattern knows, one entry each, so a
#: widening is a line in a list rather than a longer string nobody can read.
#: **The threat is a forged turn in any syntax a model might honour, not only
#: the syntax of the model configured today** - an injection is written for
#: whoever reads it, and an article is fetched once and summarized by whatever
#: is loaded. So the list covers the families a configured entry can bring
#: rather than the entry's own markers. It cannot be complete: the answer to a
#: family nobody anticipated is `why_a_forged_turn_would_survive` below, which
#: turns an unknown family into a refused run rather than a silent hole.
_CHAT_CONTROL_FAMILIES: Final[tuple[str, ...]] = (
    # ChatML and every pipe-delimited descendant - Qwen, Llama 3 and 4, Phi-3,
    # Zephyr, Granite, Command-R, Harmony. The second delimiter is U+FF5C, the
    # fullwidth vertical line, which is how DeepSeek spells its whole
    # vocabulary: it renders as a pipe and is a different codepoint, so an
    # ASCII-only pattern reads `<|User|>` as ordinary words.
    r"<[|\uff5c][^|\uff5c>\n]{0,64}[|\uff5c]>",
    # The same idea with the delimiter on one side only, which is how Gemma 4
    # spells a turn: `<|turn>` opens it and `<turn|>` closes it, and the same
    # pair opens and closes its thinking channel. Neither shape can reach the
    # family above, which needs a delimiter at both ends, nor the bare-token
    # family below, which needs a letter immediately after the bracket - so
    # without this line `<|turn>system` is four ordinary words to the pattern
    # and an article may write a whole forged turn.
    r"<(?:[|\uff5c][A-Za-z][A-Za-z0-9_]{0,62}|[A-Za-z][A-Za-z0-9_]{0,62}[|\uff5c])>",
    # Llama 2's system fence, which is two angle brackets rather than one and
    # so has to be tried before the single-bracket family below.
    r"<</?SYS>>",
    # Llama 2 and the Mistral bracket family - [INST], [SYSTEM_PROMPT],
    # [AVAILABLE_TOOLS], [TOOL_CALLS]. Case-sensitive inside a case-insensitive
    # pattern, and three characters at least, so an editor's [sic] and a
    # dateline's [AP] stay. What it does take from prose is a bracketed
    # all-capital tag like [UPDATE]; that is a space in the summarized text
    # against a forged turn, and Guardrail #11 decides which way that trades.
    r"(?-i:\[/?[A-Z][A-Z_]{2,30}\])",
    # A bare angle-bracket special token, which is what a family spells when it
    # has no delimiter of its own: Gemma's <start_of_turn> and <end_of_turn>,
    # Nemotron's <extra_id_0>, the <s> and </s> a Mistral forged turn rides in
    # on, and the <think> channel a reasoning model opens its reply with - the
    # incumbent declares two of those in its own reply opening. No whitespace
    # is allowed inside, so `a < b` is arithmetic and stays arithmetic.
    r"</?[A-Za-z][A-Za-z0-9_]{0,62}>",
    # The plain-text header a model may honour whatever it was trained on.
    r"^[ \t]*#{2,}[ \t]*(?:system|assistant|user)[ \t]*:",
)
_CHAT_CONTROL = re.compile("|".join(_CHAT_CONTROL_FAMILIES), re.IGNORECASE | re.MULTILINE)
#: What makes a token a token in every family above. One of these left standing
#: after sanitization means the marker's structure came through with it.
_MARKER_DELIMITERS: Final = frozenset("<>[]|\uff5c")
# Smuggle an instruction past anyone reading the extracted text. No trailing
# word boundary: padding is not a word character, and requiring one would leave
# the `==` behind.
_BASE64_RUN = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}")
# An address in the body is never needed: the item's own link is carried on the
# payload, from the feed, and is not this text.
_URL = re.compile(r"(?:\b(?:https?://|www\.)|\bdata:)[^\s<>\"']+", re.IGNORECASE)
_FENCE = re.compile("|".join(re.escape(marker) for marker in (FENCE_OPEN, FENCE_CLOSE)), re.I)
_HORIZONTAL_SPACE = re.compile(r"[^\S\n]+")
_BLANK_RUN = re.compile(r"\n{3,}")


def sanitize(text: str) -> str:
    """Strip what an injection needs, keep what the article says.

    Idempotent: sanitizing sanitized text is a no-op, so a defensive second
    pass at the prompt boundary costs nothing and cannot be forgotten.
    """
    text = _HTML_COMMENT.sub(" ", text)
    text = _INVISIBLE.sub("", text)
    text = _CONTROL.sub(" ", text)
    # The fence goes before the chat-control pass, not after. Its markers are
    # three angle brackets around a word, so the bare-token family would take
    # the word out of the middle and leave `<< >>` standing where a whole
    # marker used to be. Removed first, there is nothing left to half-match.
    text = _FENCE.sub(" ", text)
    text = _CHAT_CONTROL.sub(" ", text)
    text = _URL.sub(LINK_PLACEHOLDER, text)
    text = _BASE64_RUN.sub(BLOB_PLACEHOLDER, text)
    text = _HORIZONTAL_SPACE.sub(" ", text)
    # Lines are trimmed before blank runs are collapsed, not after: a removed
    # marker leaves a line of spaces behind, and trimming it afterwards would
    # create a blank run that only a second pass would find.
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def untrusted_block(text: str) -> str:
    """The only way source text is ever handed to a model.

    It goes in the user turn, fenced and labelled as data. It never reaches a
    system prompt, and it cannot close the fence: the markers are removed by the
    sanitization this function applies itself, rather than trusting a caller to
    have applied it earlier.
    """
    return f"{FENCE_OPEN}\n{sanitize(text)}\n{FENCE_CLOSE}"


def why_a_forged_turn_would_survive(marker: str) -> str | None:
    """Why an article writing this turn marker verbatim would still carry it.

    `None` means the pattern strips it, so a forged turn spelled this way dies
    at extraction. Anything else is the sentence a refusal quotes.

    Two questions, because either one alone passes a marker the boundary cannot
    hold. **Is the marker recognised at all** - one the pattern never matches is
    one an article may write out in full, and a marker made of ordinary words
    (`USER: `) is that case with nowhere to widen toward, because a pattern that
    stripped it would strip prose. **Is anything structural left** - a marker
    matched only in part leaves the delimiters behind, and a template that reads
    a delimiter is a template a remnant can still reach.

    It answers about one string and knows nothing about where the string came
    from. `idhazh.llm.server` is what asks it, over the markers a model's own
    template really rendered, because `backend/idhazh/contracts/` may import no
    other subpackage (`CLAUDE.md` section 4) and so cannot ask anything at all.
    """
    if _CHAT_CONTROL.search(marker) is None:
        return "the control-token pattern matches nothing in it, so an article may write it whole"
    left = sorted(set(sanitize(marker)) & _MARKER_DELIMITERS)
    if left:
        return f"sanitizing it leaves the token delimiters {''.join(left)!r} standing"
    return None
