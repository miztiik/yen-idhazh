"""Every quantity and every date one article states, and the characters that prove each.

The candidate pass. It reads the article's own bytes with two patterns, and for
every quantity and every date it matches it keeps three things the visual
planner throws away: where the fact starts, where it ends, and the verbatim
slice between them. Those offsets are not new work - `visual_planner.numeric_facts`
has always computed them and always discarded them.

**This pass keeps what `numeric_facts` is right to drop.** That function picks a
few bars for one chart, so it collapses a figure repeated across two periods
into one fact, drops a magnitude at or below two, drops a bare year, and stops
at sixteen. Every one of those is correct for choosing bars and wrong for a
candidate set: the collapsed repeat is exactly the series a trend chart exists
to show. Nothing here dedupes and nothing here drops on size. `numeric_facts`
is untouched and still behaves that way for the planner that calls it.

**Two patterns read the same bytes, so one of them has to lose.** Both match
`2026`, and `settle` is the rule: `KIND_PRECEDENCE` puts the date first because
its vocabulary is a closed list of calendar shapes while the number pattern
accepts any run of digits, and the closed claim is the stronger one. A date
drops every quantity it shares a character with. The ruling and what it costs
are on `docs/architecture/extraction/elements.md`.

**What it will not write is a reading the shape cannot hold.** A pattern over
fetched bytes can match a 200-digit serial number or a 600-character hyphenated
word (Rule #11). A value too wide to write is not a quantity and is not emitted;
a word too wide to be a unit is read as no unit, and the element still lands
with its span. A date needs no such bound: the longest reading either pattern
can produce is ten characters.

**The number pattern lives here now.** It moved off `visual_planner` with the
magnitude table, the percent set, the unit stop list, the year range and
`normalise_unit`, because two passes read the same vocabulary and the fact pass
is the lower of the two. The planner imports them back and reads them exactly
as it did.

**A table is re-sliced before it leaves this module.** `element_table` cuts the
text at every span it is about to return and refuses a table it cannot cut, so
the hash, the length and every excerpt provably describe one string. That is the
write-time half of the span-drift invariant; the read-time half degrades one
item and lives on `ElementTable.span_drift`.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections import Counter
from collections.abc import Iterable
from datetime import date
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
from idhazh.contracts.item_health import ElementClass
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

# The month names a date may be written with, and the number each one is. The
# closed list is the point: a shape the article did not write is a date nobody
# stated (decision 4).
MONTHS: Final[dict[str, int]] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
# Longest first, so `june` is read as June rather than as `jun` with a stray
# letter after it. The alternation is ordered, and this is cheaper than a
# backtrack on every month in every article.
_MONTH_ALTERNATION: Final = "|".join(sorted(MONTHS, key=len, reverse=True))

# The four shapes an article may state a date in, tried longest-first so a full
# date is never read as the bare year inside it. The two lookbehinds keep a
# price and a decimal out: `$2026` and `12.2026` are numbers, and the four
# digits inside them are not a year anybody wrote. The lookaheads do the same
# job on the other side, so `2026.5` is a number while `2026.` ends a sentence.
# The bare-year branch matches any four digits and `_read_date` holds it to
# YEAR_MIN..YEAR_MAX, because that bound is a number and not a spelling.
DATE: Final = re.compile(
    r"(?<![\w.,$\u00a3\u20ac\u20b9-])"
    r"(?<![$\u00a3\u20ac\u20b9]\s)"
    r"(?:"
    r"(?P<iso_year>\d{4})-(?P<iso_month>\d{2})-(?P<iso_day>\d{2})"
    rf"|(?P<dmy_day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<dmy_month>{_MONTH_ALTERNATION})\.?,?"
    r"\s+(?P<dmy_year>\d{4})"
    rf"|(?P<mdy_month>{_MONTH_ALTERNATION})\.?\s+(?P<mdy_day>\d{{1,2}})(?:st|nd|rd|th)?,?"
    r"\s+(?P<mdy_year>\d{4})"
    r"|(?P<year>\d{4})"
    r")"
    r"(?![\w-])(?![.,]\d)",
    re.IGNORECASE,
)

#: Which pass keeps the characters when both of them match the same ones. The
#: date pattern accepts a closed list of calendar shapes; the number pattern
#: accepts any run of digits. The closed vocabulary is the stronger claim about
#: what those characters are, so it wins. `docs/architecture/extraction/
#: elements.md` carries the ruling and what it costs.
KIND_PRECEDENCE: Final[tuple[ElementKind, ...]] = (ElementKind.DATE, ElementKind.QUANTITY)
_RANK: Final[dict[ElementKind, int]] = {kind: rank for rank, kind in enumerate(KIND_PRECEDENCE)}

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


class SpanDriftError(ValueError):
    """The table cannot cut its own excerpts out of the text it was handed.

    A `ValueError` so every caller written before this class still catches it,
    and its own type so a caller can tell it from a shape refusal. The two want
    opposite dispositions: a span that stopped pointing where it did degrades one
    item, and a payload the contract refuses is our own arithmetic being wrong
    everywhere it runs (`docs/architecture/extraction/elements.md`).
    """


class Candidates(NamedTuple):
    """One pass's elements, and how many it matched before the cap.

    `found` is taken before anything is discarded, so it stays true when
    `elements` has saturated. Read one without the other and a full table and a
    dense article look the same.
    """

    elements: list[Element]
    found: int


class Reading(NamedTuple):
    """What one match says: its value, its unit, and where its characters end."""

    value: str
    unit: str | None
    span_end: int


def sentence_starts(text: str) -> list[int]:
    """Where each sentence after the first begins, so an offset maps to an index."""
    return [match.end() for match in _SENTENCE_SPLIT.finditer(text)]


def read_quantity(match: re.Match[str]) -> Reading | None:
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
    return Reading(value, unit or None, span_end)


def _read_date(match: re.Match[str]) -> str | None:
    """The date one match states, or nothing when the calendar refuses it.

    A bare four-digit run is a year only inside YEAR_MIN..YEAR_MAX, because
    outside it the digits are far likelier to be a measurement. A written date
    needs no such bound: `2026-08-24` says what it is whatever the year, and a
    day the calendar does not have - `February 31, 2026` - is refused outright
    rather than rounded to one that exists.
    """
    if (bare := match.group("year")) is not None:
        return bare if YEAR_MIN <= int(bare) <= YEAR_MAX else None
    if (iso := match.group("iso_year")) is not None:
        year, month, day = iso, int(match.group("iso_month")), match.group("iso_day")
    elif (dmy := match.group("dmy_year")) is not None:
        year, month, day = dmy, MONTHS[match.group("dmy_month").lower()], match.group("dmy_day")
    else:
        mdy = match.group("mdy_year")
        year, month, day = mdy, MONTHS[match.group("mdy_month").lower()], match.group("mdy_day")
    try:
        return date(int(year), month, int(day)).isoformat()
    except ValueError:
        return None


def read_value(kind: ElementKind, excerpt: str) -> str | None:
    """What an element's own characters state, read back by the pass that wrote it.

    `Element` holds `span_excerpt` to the width of its span. It cannot hold it to
    the `value` beside it, because the value is a *reading* of those characters
    and the shape does no reading - so a table crossing a stage boundary can
    carry a cell that disagrees with the characters it names, and the consumer
    about to draw that figure is the last place to notice.

    `None` for the four kinds that are words, which is what they carry, so one
    comparison covers every kind. `None` also for characters this reader cannot
    read at all, which fails closed: an unreadable excerpt is not a value
    anybody can show.
    """
    if kind is ElementKind.QUANTITY:
        match = NUMBER.match(excerpt)
        reading = read_quantity(match) if match is not None else None
        return reading.value if reading is not None else None
    if kind is ElementKind.DATE:
        match = DATE.match(excerpt)
        return _read_date(match) if match is not None else None
    return None


def quantity_elements(text: str, *, limit: int) -> Candidates:
    """Every quantity the number pattern matches, in the order the article wrote them.

    `text` is `Article.text` - post-sanitize and post-truncation - because that
    is the string the offsets index and the string a later re-slice will hold.
    Pass anything else and every offset points somewhere else in the article.

    No dedupe, no floor on the magnitude, and no bare-year drop: this is the
    candidate set, and the drops belong to whoever chooses from it.
    """
    starts = sentence_starts(text)
    kept: list[Element] = []
    found = 0
    for match in NUMBER.finditer(text):
        reading = read_quantity(match)
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


def date_elements(text: str, *, limit: int) -> Candidates:
    """Every absolute date the date pattern matches, in the order the article wrote them.

    Absolute dates and years only (decision 4). "Three years ago" resolves
    against a publication date the article never wrote, and a derived value is
    not a found one.

    `text` is `Article.text`, for the reason `quantity_elements` says: the
    offsets index that string and nothing else. The whole match is the span,
    with nothing trimmed off either end, so a written date keeps the month word
    that makes it readable on the page.
    """
    starts = sentence_starts(text)
    kept: list[Element] = []
    found = 0
    for match in DATE.finditer(text):
        value = _read_date(match)
        if value is None:
            continue
        found += 1
        if len(kept) >= limit:
            continue
        span_start, span_end = match.start(), match.end()
        kept.append(
            Element(
                element_id=derive_element_id(ElementKind.DATE, span_start, span_end),
                kind=ElementKind.DATE,
                span_start=span_start,
                span_end=span_end,
                span_excerpt=text[span_start:span_end],
                value=value,
                unit=None,
                sentence_index=bisect_right(starts, span_start),
                extractor=Extractor.REGEX,
            )
        )
    return Candidates(kept, found)


def settle(candidates: Iterable[Element]) -> list[Element]:
    """One reading per stretch of characters, in the order the article wrote them.

    Two passes now read the same bytes and both match `2026`. The rule is
    `KIND_PRECEDENCE`: the pass with the closed vocabulary keeps the characters,
    so a date drops any quantity it shares a character with, whether the two
    spans are equal, nested either way round, or merely crossing.

    **It is the rule between the two pattern passes and takes no other kind.**
    `KIND_PRECEDENCE` names the two it ranks, so a model-pointed kind reaching
    here raises rather than being ranked by accident - and it must not be ranked
    at all, because a quote carrying a quantity inside it is the shape those
    kinds need and this rule would drop one of the two. `visual_planner.anchored`
    merges them after this has run.

    Quadratic in one article's candidates and bounded by the cap the caller
    passes, so it cannot grow with the archive (Rule #12).
    """
    kept: list[Element] = []
    for element in sorted(candidates, key=lambda item: (_RANK[item.kind], item.span_start)):
        if any(
            other.span_start < element.span_end and element.span_start < other.span_end
            for other in kept
        ):
            continue
        kept.append(element)
    return sorted(kept, key=lambda item: item.span_start)


def element_table(article: Article, *, config: ElementsConfig) -> ElementTable:
    """One article's candidates, and the text every span in them indexes.

    A pure function over one payload, so the pass is testable on its own and
    nothing has to be committed for it to be checked (CLAUDE.md section 4).

    `elements.max_per_article` bounds each pass and then the settled table, so
    neither a runaway pattern nor two passes together can put more elements in
    an article than the knob names.

    **The table is re-sliced before it is returned, and that is the write-time
    half of the span-drift invariant.** It is what makes decision 3 mechanical:
    the hash, the length and every excerpt come out of one call against one
    string, and the re-slice proves it rather than the call site promising it.
    Neither pattern pass can fail it, because each cuts its excerpt at its own
    offsets - so the failure it exists for is a caller that builds elements from
    one string and a table over another, which is what happens the first time
    somebody reaches for the pre-cap body, and what plan 11's producers risk on
    every article once a model proposes the location and code cuts at it.

    It raises rather than degrading because at this point the text is in hand
    and it is the string the excerpts came from, so a mismatch is this process's
    own arithmetic being wrong. Read time is the other half and it degrades one
    item: see `ElementTable.span_drift`.
    """
    text = article.text or ""
    dates = date_elements(text, limit=config.max_per_article)
    quantities = quantity_elements(text, limit=config.max_per_article)
    table = ElementTable(
        version=ElementTable.schema_version(),
        item_id=article.item_id,
        url_key=derive_url_key(article.canonical_url),
        canonical_url=article.canonical_url,
        source_text_hash=derive_text_digest(text),
        source_text_length=len(text),
        elements=settle(dates.elements + quantities.elements)[: config.max_per_article],
        candidates_found={
            ElementKind.QUANTITY: quantities.found,
            ElementKind.DATE: dates.found,
        },
    )
    if (drift := table.span_drift(text)) is not None:
        raise SpanDriftError(f"the pass cannot re-slice its own output: {drift}")
    return table


class ExtractionHealth(NamedTuple):
    """What the pass got out of one article, as three cells a census row holds.

    `span_integrity` is stated first because it governs the other two: false
    means the table would not re-slice and there is nothing trustworthy to
    count, so both of the others are `None`. True means the pass ran and both are
    filled. The triple is never half-filled any other way.
    """

    span_integrity: bool
    elements_found: int | None
    element_class: ElementClass | None


def classify(table: ElementTable, *, min_chart_points: int) -> ElementClass:
    """Which of the three classes one article's numbers put it in.

    **Distinct quantities per unit, because a bar chart cannot draw the same
    figure twice.** `visual_planner.same_unit_bars` groups the chosen bars by
    unit and the bars are distinct by construction, so counting a repeated
    figure here would call an article chartable that no planner could ever draw -
    and `extractable_but_unused_rate` would carry that gap for ever while
    claiming to measure the planner.

    **The empty unit is a group like any other**, which is the reading
    `chart_is_reachable` already takes: `numeric_facts` writes an empty unit when
    nothing after the number reads as one, and excluding the group would call an
    article narrative that publishes a chart today.

    **This is not `chart_is_reachable` and is not meant to be.** That function
    asks whether a chart could survive the planner's own drops - the sixteen-fact
    cap and the floor under a magnitude of two. This asks what the article
    states. The gap between the two answers is what row 5 exists to report, so
    closing it here would delete the measurement.

    `min_chart_points` is `visuals.min_chart_points` and not a second knob
    (Rule #6). Mint one and the console can call an article chartable while the
    planner refuses to draw it, and the rate then measures two knobs drifting
    apart rather than the planner.
    """
    units = Counter(
        (element.unit or "", element.value)
        for element in table.elements
        if element.kind is ElementKind.QUANTITY
    )
    if not units:
        return ElementClass.NARRATIVE
    widest = Counter(unit for unit, _ in units).most_common(1)[0][1]
    return ElementClass.CHARTABLE if widest >= min_chart_points else ElementClass.UNCLASSIFIED


def extraction_health(
    article: Article, *, config: ElementsConfig, min_chart_points: int
) -> ExtractionHealth | None:
    """The three census cells for one article, or nothing when there was no text.

    O(1) in the archive: it reads one article and builds one table (Rule #12).

    **A drifted span degrades this item and nothing else.** That is row 4's
    ruling, and this is where it is carried out: `element_table` raises because
    it cut those characters out of that string moments earlier, and the caller
    that has to file a row for every planned item records the failure instead of
    taking the run down with it. `span_integrity_rate` is what makes the refusal
    visible - a run whose own arithmetic broke reports zero percent rather than
    silently reporting nothing.

    A shape refusal is deliberately not caught. A payload the contract will not
    hold is failing for every article that took the same path, and a rate that
    swallowed it would report the run as healthy.
    """
    if not article.text:
        return None
    try:
        table = element_table(article, config=config)
    except SpanDriftError:
        return ExtractionHealth(span_integrity=False, elements_found=None, element_class=None)
    return ExtractionHealth(
        span_integrity=True,
        elements_found=len(table.elements),
        element_class=classify(table, min_chart_points=min_chart_points),
    )
