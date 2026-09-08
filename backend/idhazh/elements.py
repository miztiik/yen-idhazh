"""Every quantity one article states, and the characters that prove each one.

The candidate pass. It reads the article's own bytes with a pattern, and for
every quantity it matches it keeps three things the visual planner throws away:
where the quantity starts, where it ends, and the verbatim slice between them.
Those offsets are not new work - `visual_planner.numeric_facts` has always
computed them and always discarded them.

**This pass keeps what `numeric_facts` is right to drop.** That function picks a
few bars for one chart, so it collapses a figure repeated across two periods
into one fact, drops a magnitude at or below two, drops a bare year, and stops
at sixteen. Every one of those is correct for choosing bars and wrong for a
candidate set: the collapsed repeat is exactly the series a trend chart exists
to show. Nothing here dedupes and nothing here drops on size. `numeric_facts`
is untouched and still behaves that way for the planner that calls it.

**What it will not write is a reading the shape cannot hold.** A pattern over
fetched bytes can match a 200-digit serial number or a 600-character hyphenated
word (Rule #11). A value too wide to write is not a quantity and is not emitted;
a word too wide to be a unit is read as no unit, and the element still lands
with its span.

**The number pattern lives here now.** It moved off `visual_planner` with the
magnitude table, the percent set, the unit stop list and `normalise_unit`,
because two passes read the same vocabulary and the fact pass is the lower of
the two. The planner imports them back and reads them exactly as it did.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from decimal import Decimal, InvalidOperation
from typing import Final, NamedTuple

from idhazh.contracts.app_config import ElementsConfig
from idhazh.contracts.article import Article
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.element import (
    UNIT_MAX_LENGTH,
    VALUE_MAX_LENGTH,
    Element,
    ElementKind,
    ElementTable,
    Extractor,
    derive_element_id,
)
from idhazh.evals.metrics import _SENTENCE_SPLIT

# A number with optional thousands separators, an optional decimal part, an
# optional magnitude word, and the one word that follows it. The leading
# lookbehind excludes a hyphen so `COVID-19`, `GPT-4` and `Qwen3-4B` do not read
# as quantities.
NUMBER: Final = re.compile(
    r"(?<![\w.-])"
    r"(?P<currency>[$\u00a3\u20ac\u20b9]\s?)?"
    r"(?P<sign>-)?"
    r"(?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"\s*"
    r"(?P<magnitude>percent|per cent|%|billion|bn|million|mn|thousand|trillion|tn)?"
    r"\s*"
    r"(?P<unit>[a-zA-Z][a-zA-Z-]*)?",
    re.IGNORECASE,
)

# `m` and `k` are deliberately absent. The model never writes a number, but the
# extractor does, and reading `15 m` as fifteen million is a one-million-fold
# error on a published bar decided by a guess about metres.
MAGNITUDE: Final[dict[str, Decimal]] = {
    "thousand": Decimal(1_000),
    "million": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "billion": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "trillion": Decimal(1_000_000_000_000),
    "tn": Decimal(1_000_000_000_000),
}

PERCENT: Final[frozenset[str]] = frozenset({"percent", "per cent", "%"})

# A bare four-digit integer in this range reads as a calendar year rather than
# as a measurement. It lives with the number pattern because it is a fact about
# the same bytes, and `visual_planner` reads it back.
YEAR_MIN: Final = 1900
YEAR_MAX: Final = 2100

# The word after a number is a unit only sometimes. These are the ones that
# never are, so a quantity does not end up measured in "of".
NOT_A_UNIT: Final[frozenset[str]] = frozenset(
    """a an and are as at be been before but by during for from had has have he her his in is it
    its more most of on or over per said says she should such than that the their then there these
    they this to under until up was we were what when which while who will with would you""".split()
)


def normalise_unit(unit: str) -> str:
    """Lowercase and de-pluralised, so `Megawatts` and `megawatt` are one unit."""
    lowered = unit.strip().lower()
    if len(lowered) > 3 and lowered.endswith("s") and not lowered.endswith("ss"):
        return lowered[:-1]
    return lowered


class Candidates(NamedTuple):
    """One pass's elements, and how many it matched before the cap.

    `found` is taken before anything is discarded, so it stays true when
    `elements` has saturated. Read one without the other and a full table and a
    dense article look the same.
    """

    elements: list[Element]
    found: int


class _Reading(NamedTuple):
    """What one match says: its value, its unit, and where its characters end."""

    value: str
    unit: str | None
    span_end: int


def _sentence_starts(text: str) -> list[int]:
    """Where each sentence after the first begins, so an offset maps to an index."""
    return [match.end() for match in _SENTENCE_SPLIT.finditer(text)]


def _read(match: re.Match[str]) -> _Reading | None:
    """The quantity one match states, or nothing when it states none.

    The span ends where the reading does. A trailing word is inside the span
    only when it was read as the unit, so `40 percent of` never becomes an
    excerpt and `1,200 MW` always does.
    """
    digits = match.group("value")
    try:
        magnitude = Decimal(digits.replace(",", ""))
    except InvalidOperation:
        return None

    suffix = (match.group("magnitude") or "").strip().lower()
    word = normalise_unit(match.group("unit") or "")
    if word in NOT_A_UNIT or len(word) > UNIT_MAX_LENGTH:
        word = ""

    span_end = match.end("value")
    if suffix in PERCENT:
        unit = "%"
        span_end = match.end("magnitude")
    else:
        if suffix in MAGNITUDE:
            magnitude *= MAGNITUDE[suffix]
            span_end = match.end("magnitude")
        currency = (match.group("currency") or "").strip()
        unit = currency or word
        if word and unit == word:
            span_end = match.end("unit")

    if match.group("sign"):
        magnitude = -magnitude
    # `f` rather than `str`, which writes a scientific form once a magnitude
    # word has multiplied the figure - and `4.5E+9` is not a number anybody
    # wrote or can read back. The trailing zeros go for the reason the value is
    # text at all: "4.2 billion" and "4,200,000,000" are one quantity, and they
    # have to compare equal as strings or the pinning buys nothing.
    value = format(magnitude, "f")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    if len(value) > VALUE_MAX_LENGTH:
        return None
    return _Reading(value, unit or None, span_end)


def quantity_elements(text: str, *, limit: int) -> Candidates:
    """Every quantity the number pattern matches, in the order the article wrote them.

    `text` is `Article.text` - post-sanitize and post-truncation - because that
    is the string the offsets index and the string a later re-slice will hold.
    Pass anything else and every offset points somewhere else in the article.

    No dedupe, no floor on the magnitude, and no bare-year drop: this is the
    candidate set, and the drops belong to whoever chooses from it.
    """
    starts = _sentence_starts(text)
    kept: list[Element] = []
    found = 0
    for match in NUMBER.finditer(text):
        reading = _read(match)
        if reading is None:
            continue
        found += 1
        if len(kept) >= limit:
            continue
        span_start = match.start()
        kept.append(
            Element(
                element_id=derive_element_id(ElementKind.QUANTITY, span_start, reading.span_end),
                kind=ElementKind.QUANTITY,
                span_start=span_start,
                span_end=reading.span_end,
                span_excerpt=text[span_start : reading.span_end],
                value=reading.value,
                unit=reading.unit,
                sentence_index=bisect_right(starts, span_start),
                extractor=Extractor.REGEX,
            )
        )
    return Candidates(kept, found)


def element_table(article: Article, *, config: ElementsConfig) -> ElementTable:
    """One article's candidates, and the text every span in them indexes.

    A pure function over one payload, so the pass is testable on its own and
    nothing has to be committed for it to be checked (CLAUDE.md section 4).
    """
    text = article.text or ""
    quantities = quantity_elements(text, limit=config.max_per_article)
    return ElementTable(
        version=ElementTable.schema_version(),
        item_id=article.item_id,
        url_key=derive_url_key(article.canonical_url),
        canonical_url=article.canonical_url,
        source_text_hash=derive_text_digest(text),
        source_text_length=len(text),
        elements=quantities.elements,
        candidates_found={ElementKind.QUANTITY: quantities.found},
    )
