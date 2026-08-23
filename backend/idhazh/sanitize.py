"""The trust boundary's control, crossed exactly once.

Anything the pipeline pulls from the open web is untrusted (Rule #11). A
system prompt asking a model to ignore embedded instructions is a request, not
a control - it is written in the same channel as the attack and loses to a
better-worded attack. The controls are this module and the output schema.

Two guarantees, and nothing else:

- `sanitize` removes the machinery an injection needs: the invisible characters
  that hide it, the chat-control tokens that would end the user's turn, the
  encoded blob that smuggles it past a reader, and the address it would
  exfiltrate to.
- `untrusted_block` is the only way source text is ever handed to a model, and
  the text can never close the fence it sits inside, because the fence markers
  do not survive sanitization.

The bounds here are structural, not tunable. A knob that weakens the trust
boundary is a knob that gets widened during an incident (CLAUDE.md section 6
names the caps a reasonable operator would move; these are not among them).
"""

from __future__ import annotations

import re
from typing import Final

#: Bumped whenever the transformation below changes. It is a fingerprint input,
#: so a silent edit here would otherwise re-summarize nothing and explain less.
SANITIZER_VERSION: Final = "idhazh-sanitizer-1"

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
# End the user's turn and start a forged system turn. Covers the ChatML family,
# the Llama instruct family, and the plain-text headers a model may honour.
_CHAT_CONTROL = re.compile(
    r"<\|[^|>\n]{0,64}\|>|\[/?INST\]|<</?SYS>>|^[ \t]*#{2,}[ \t]*(?:system|assistant|user)[ \t]*:",
    re.IGNORECASE | re.MULTILINE,
)
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
    text = _CHAT_CONTROL.sub(" ", text)
    text = _FENCE.sub(" ", text)
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
