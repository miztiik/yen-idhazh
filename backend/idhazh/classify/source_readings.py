"""Re-read proposed figures and locate their exact source evidence."""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass
from decimal import Decimal

from idhazh.classify.chart_reply import Reading
from idhazh.contracts.element import VALUE_MAX_LENGTH, Element, ElementKind, ElementTable
from idhazh.elements import (
    DATE,
    MAGNITUDE,
    NUMBER,
    PERCENT,
    read_quantity,
    read_value,
    sentence_starts,
)
from idhazh.sanitize import BLOB_PLACEHOLDER, LINK_PLACEHOLDER, sanitize

# Markers exist only in the local index. They cannot survive source sanitization.
QUANTITY = "\x01"
DATE_SLOT = "\x02"
ASIDE = "\x03"
_STATED_NUMBER = re.compile(
    rf"-?(?:[0-9]{{1,3}}(?:,[0-9]{{3}}){{1,{VALUE_MAX_LENGTH // 4}}}|[0-9]+)(?:\.[0-9]+)?"
)
_UNIT_TOKEN = re.compile(r"[^\W\d_]+|[%$\u00a3\u20ac\u20b9]", re.UNICODE)
_CURRENCY = frozenset({"$", "\u00a3", "\u20ac", "\u20b9"})
_LEADING_ARTICLE = re.compile(r"^(?:the|a|an)\s+")


def plain_words(text: str) -> bool:
    return (
        bool(text)
        and text == sanitize(text)
        and "\n" not in text
        and not any(marker in text for marker in (LINK_PLACEHOLDER, BLOB_PLACEHOLDER, "<", ">"))
    )


def words_key(text: str) -> str:
    return _LEADING_ARTICLE.sub("", " ".join(text.casefold().split()))


def _unit_tokens(tokens: list[str]) -> tuple[str, ...]:
    words: list[str] = []
    for token in tokens:
        scale = MAGNITUDE.get(token)
        words.append(str(int(scale)) if scale is not None else "%" if token in PERCENT else token)
    return tuple(words)


def reading_key(reading: Reading) -> tuple[Decimal, tuple[str, ...]] | None:
    """A numeric spelling and the scale and unit the model actually declared."""
    if not _STATED_NUMBER.fullmatch(reading.value):
        return None
    raw_unit = reading.unit
    unit: tuple[str, ...] = ()
    if raw_unit is not None:
        if not plain_words(raw_unit):
            return None
        if raw_unit.casefold() in PERCENT:
            unit = ("%",)
        else:
            tokens = _UNIT_TOKEN.findall(raw_unit.casefold())
            if not tokens or " ".join(tokens) != raw_unit.casefold():
                return None
            unit = _unit_tokens(tokens)
    return Decimal(reading.value.replace(",", "")), unit


def source_key(element: Element) -> tuple[Decimal, tuple[str, ...]] | None:
    """Keep the coefficient and scale separate, and check the stored value and unit."""
    match = NUMBER.fullmatch(element.span_excerpt)
    checked = read_quantity(match) if match is not None else None
    if (
        match is None
        or checked is None
        or checked.span_end != len(element.span_excerpt)
        or (checked.value, checked.unit) != (element.value, element.unit)
    ):
        return None
    suffix = (match["magnitude"] or "").strip().casefold()
    unit: tuple[str, ...]
    if suffix in PERCENT:
        unit = ("%",)
    else:
        unit = _unit_tokens(
            [
                word
                for word in (
                    suffix,
                    checked.unit
                    if match["currency"]
                    else (match["unit"] or "").casefold()
                    if checked.unit
                    else None,
                )
                if word
            ]
        )
    digits = match["value"].replace(",", "")
    return Decimal((match["sign"] or "") + digits), unit


def date_key(text: str) -> str | None:
    return read_value(ElementKind.DATE, text) if DATE.fullmatch(text) else None


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Clause:
    start: int
    text: str
    masked: str
    slots: dict[int, Element]

    def slice(self, start: int, end: int) -> Span:
        value = self.text[start:end]
        lo = start + len(value) - len(value.lstrip())
        hi = start + len(value.rstrip())
        return Span(self.start + lo, self.start + hi, self.text[lo:hi])

    def subclause(self, start: int, end: int) -> Clause:
        return Clause(self.start + start, self.text[start:end], self.masked[start:end], self.slots)

    def element(self, match: re.Match[str], name: str) -> Element:
        return self.slots[self.start + match.start(name)]


def source_clauses(text: str, table: ElementTable) -> list[Clause]:
    """Mask only checked quantity/date spans, without shifting source offsets.

    Parentheses with just a currency equivalent cannot stand in for the main
    reading. Other parentheses remain text so the clause rules can refuse them.
    """
    starts = sorted({0, *sentence_starts(text), *(m.end() for m in re.finditer(r"\n+", text))})
    chars = [c if c not in (QUANTITY, DATE_SLOT, ASIDE) else " " for c in text]
    elements: dict[int, Element] = {}
    for item in table.elements:
        if item.kind is ElementKind.QUANTITY and source_key(item) is not None:
            slot = QUANTITY
        elif item.kind is ElementKind.DATE and date_key(item.span_excerpt) == item.value:
            slot = DATE_SLOT
        else:
            continue
        elements[item.span_start] = item
        chars[item.span_start : item.span_end] = [
            slot,
            *" " * (item.span_end - item.span_start - 1),
        ]
    masked = "".join(chars)
    for match in re.finditer(
        rf"\((?:[A-Z]{{2}})?(?P<currency>[$\u00a3\u20ac\u20b9])?(?P<q>{QUANTITY}) *\)",
        masked,
    ):
        equivalent = elements[match.start("q")]
        main = masked[: match.start()].rstrip()
        if (
            equivalent.unit in _CURRENCY or (match["currency"] and equivalent.unit is None)
        ) and main.endswith(QUANTITY):
            chars[match.start() : match.end()] = [ASIDE, *" " * (match.end() - match.start() - 1)]
    by_sentence: dict[int, dict[int, Element]] = {}
    for offset, item in elements.items():
        by_sentence.setdefault(bisect_right(starts, offset) - 1, {})[offset] = item
    masked = "".join(chars)
    return [
        Clause(lo, text[lo:hi], masked[lo:hi], by_sentence[index])
        for index, (lo, hi) in enumerate(zip(starts, [*starts[1:], len(text)], strict=True))
        if index in by_sentence
    ]
