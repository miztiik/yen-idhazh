"""Offer the article's exact readings as complete, selectable pairs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from pydantic import ValidationError

from idhazh.classify.chart_reply import Reading
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.elements import NUMBER, PERCENT, read_quantity
from idhazh.sanitize import BLOB_PLACEHOLDER, LINK_PLACEHOLDER, sanitize, untrusted_block


class ChartCandidate(NamedTuple):
    reading: Reading
    element: Element


def plain_chart_words(text: str) -> bool:
    return (
        bool(text)
        and text == sanitize(text)
        and "\n" not in text
        and not any(mark in text for mark in (LINK_PLACEHOLDER, BLOB_PLACEHOLDER, "<", ">"))
    )


def chart_candidates(table: ElementTable) -> tuple[ChartCandidate, ...]:
    """Keep the stated coefficient and unit together; preserve source order and repeats."""
    candidates: list[ChartCandidate] = []
    for element in table.elements:
        if element.kind is not ElementKind.QUANTITY or not plain_chart_words(element.span_excerpt):
            continue
        match = NUMBER.fullmatch(element.span_excerpt)
        if match is None or (read := read_quantity(match)) is None:
            continue
        if (
            read.span_end != len(element.span_excerpt)
            or (read.value, read.unit) != (element.value, element.unit)
        ):
            continue
        magnitude = match["magnitude"] or match["currency_suffix"]
        currency = (match["currency"] or "").strip()
        unit = None if currency else match["unit"]
        parts = (
            [magnitude] if magnitude and magnitude.casefold() in PERCENT
            else [word for word in (currency, magnitude, unit) if word]
        )
        try:
            reading = Reading(
                value=(match["sign"] or "") + match["value"], unit=" ".join(parts) or None,
            )
        except ValidationError:
            # A source quantity is not selectable if it exceeds the reply's decoder bounds.
            continue
        candidates.append(ChartCandidate(reading, element))
    return tuple(candidates)


def candidate_block(candidates: Sequence[ChartCandidate]) -> str:
    readings = "; ".join(candidate.element.span_excerpt for candidate in candidates)
    return "\n\n" + untrusted_block(f"Candidate readings:\n{readings}")
