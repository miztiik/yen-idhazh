"""Separate a declared inline reasoning prefix from the answer, without guessing its syntax."""

from __future__ import annotations


def split_reasoning(
    raw: str, *, delimiters: tuple[str, str] | None = None
) -> tuple[str, str | None]:
    """Read every leading block, preserving delimiter text inside the answer.

    An unclosed prefix has no answer. It must never let reasoning be read as a
    schema-constrained reply, even when the entry requested reasoning.
    """
    if delimiters is None:
        return raw, None
    content = raw.lstrip()
    opening, closing = delimiters
    if not opening or not closing:
        raise ValueError("reasoning_delimiters must contain two nonempty strings")
    blocks: list[str] = []
    while content.startswith(opening):
        end = content.find(closing, len(opening))
        if end < 0:
            blocks.append(content[len(opening) :])
            return "", "\n".join(blocks)
        blocks.append(content[len(opening) : end])
        content = content[end + len(closing) :].lstrip()
    return (content, "\n".join(blocks)) if blocks else (raw, None)
