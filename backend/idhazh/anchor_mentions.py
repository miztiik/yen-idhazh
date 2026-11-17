"""Which names, places and non-figures do the text-analysis service's mentions make in one article?

A mention is a stretch of `Article.text` the service labelled. What the label means is the
operator's to say in `elements.label_kinds`: a person, an organisation, a product or an
event becomes an `entity` element, a location a `place` element, and a date, a time or an
ordinal makes no element at all - it marks characters that are not a figure, so a regex
quantity row over them can be dropped. Any other label is ignored.

**Every excerpt is cut out of `Article.text` here.** The service's words are never kept,
so nothing it returned reaches an element, and an element cannot disagree with the article
it indexes. A mention that cannot be an element - past the end of the text, blank, or
wider than a line the shape holds - is dropped on its own and never raises, because the
service is one more thing that can be wrong about one article.

**One element per distinct name, at its first occurrence.** A chart cites a name by
the element's id and draws the cited words, so a second occurrence of the same words adds
a menu row the model must read and no chart it could not already draw. Reading costs
about 101 ms a prompt token at the configured model's median of 9.85 tokens a second
(`ubuntu-latest`, 2026-09-09, `docs/architecture/summarize/throughput.md`) and a row is
about 34 tokens, so each row is worth about 3.5 seconds an item for as long as the menu is
shown (an estimate from those two readings). `found` still counts every labelled mention,
taken before the repeats go, so a reader can see how many were folded.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import NamedTuple

from idhazh.contracts.article import UNTRUSTED_LINE_MAX
from idhazh.contracts.element import Element, ElementKind, Extractor, derive_element_id
from idhazh.contracts.knobs.extract import MentionUse


class Mention(NamedTuple):
    """One stretch of `Article.text` the service labelled, as the service said it.

    The label is the service's own word (`PERSON`, `GPE`) and means nothing until
    `elements.label_kinds` maps it. The offsets are code points into `Article.text`, half
    open, and the client has already checked that they cut the words the service returned.
    """

    label: str
    start_char: int
    end_char: int


class Anchored(NamedTuple):
    """What one article's mentions came to."""

    #: The entity and place elements to show, one per distinct name, in article order.
    elements: list[Element]
    #: Every labelled mention that could be an element, per kind, before repeats folded.
    found: Counter[ElementKind]
    #: The spans of date, time and ordinal mentions: characters that are not a figure.
    not_figures: list[tuple[int, int]]


def _name(excerpt: str) -> str:
    """One name however it was spaced or capitalised, so a repeat compares equal."""
    return " ".join(excerpt.split()).casefold()


def anchor_mentions(
    text: str,
    mentions: Iterable[Mention],
    *,
    label_kinds: Mapping[str, MentionUse],
    sentence_starts: Sequence[int],
) -> Anchored:
    """The elements, the counts and the non-figure spans that one article's mentions make.

    `text` is `Article.text`, the string the offsets index, and `sentence_starts` is the
    candidate pass's own sentence boundaries over it, so a name and a figure agree about
    which sentence they are in.
    """
    named: dict[tuple[ElementKind, str], Element] = {}
    found: Counter[ElementKind] = Counter()
    not_figures: list[tuple[int, int]] = []
    for mention in mentions:
        use = label_kinds.get(mention.label)
        start, end = mention.start_char, mention.end_char
        if use is None or not 0 <= start < end <= len(text):
            continue
        if use is MentionUse.NOT_QUANTITY:
            not_figures.append((start, end))
            continue
        excerpt = text[start:end]
        if not excerpt.strip() or len(excerpt) > UNTRUSTED_LINE_MAX:
            continue
        kind = ElementKind(use.value)
        found[kind] += 1
        named.setdefault(
            (kind, _name(excerpt)),
            Element(
                element_id=derive_element_id(kind, start, end),
                kind=kind,
                span_start=start,
                span_end=end,
                span_excerpt=excerpt,
                value=None,
                unit=None,
                sentence_index=bisect_right(sentence_starts, start),
                extractor=Extractor.MODEL,
            ),
        )
    return Anchored(list(named.values()), found, not_figures)
