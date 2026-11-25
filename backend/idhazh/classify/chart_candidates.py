"""Offer bounded verbatim sentences with distinct quantity and date occurrence IDs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from idhazh.ask_text_analysis import Sentence
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import VisualType
from idhazh.sanitize import BLOB_PLACEHOLDER, LINK_PLACEHOLDER, sanitize, untrusted_block


class ChartCandidate(NamedTuple):
    evidence_id: str
    element: Element
    sentence: Sentence


def evidence_forms(
    forms: tuple[VisualType, ...], candidates: Sequence[ChartCandidate],
) -> tuple[VisualType, ...]:
    quantities = sum(entry.element.kind is ElementKind.QUANTITY for entry in candidates)
    if quantities < 2:
        return ()
    dates = bool(time_candidates(candidates))
    return tuple(
        form for form in forms
        if (dates or form not in (VisualType.LINE, VisualType.SLOPE))
        and (quantities >= 4 or form is not VisualType.SLOPE)
    )


def time_candidates(candidates: Sequence[ChartCandidate]) -> tuple[ChartCandidate, ...]:
    dates: dict[int, set[str]] = {}
    for candidate in candidates:
        element = candidate.element
        if element.kind is ElementKind.DATE and element.value is not None:
            dates.setdefault(len(element.value), set()).add(element.value)
    return tuple(
        candidate for candidate in candidates
        if candidate.element.kind is ElementKind.DATE
        and candidate.element.value is not None
        and len(dates[len(candidate.element.value)]) >= 2
    )


def plain_chart_words(text: str) -> bool:
    return (
        bool(text)
        and text == sanitize(text)
        and "\n" not in text
        and not any(mark in text for mark in (LINK_PLACEHOLDER, BLOB_PLACEHOLDER, "<", ">"))
    )


def candidate_block(candidates: Sequence[ChartCandidate]) -> str:
    passages: dict[Sentence, list[ChartCandidate]] = {}
    for candidate in candidates:
        passages.setdefault(candidate.sentence, []).append(candidate)
    lines = ["Source evidence (untrusted verbatim passages; offsets within each passage):"]
    for sentence, readings in passages.items():
        lines.extend(("\nPassage:", sentence.text, "Readings:"))
        for reading in readings:
            element = reading.element
            start = element.span_start - sentence.start_char
            end = element.span_end - sentence.start_char
            lines.append(f"{reading.evidence_id} [{start}:{end}]: {element.span_excerpt}")
    return "\n\n" + untrusted_block("\n".join(lines))


def chart_candidates(
    table: ElementTable,
    text: str,
    sentences: Sequence[Sentence],
    *,
    visuals: VisualsConfig | None = None,
) -> tuple[ChartCandidate, ...]:
    """Keep complete verified sentences in source order, never cut off a qualifier."""
    knobs = visuals or VisualsConfig()
    valid: set[Sentence] = set()
    for sentence in sentences:
        if not (
            0 <= sentence.start_char < sentence.end_char <= len(text)
            and text[sentence.start_char:sentence.end_char] == sentence.text
        ):
            continue
        passage = sentence.text.strip()
        if passage:
            start = sentence.start_char + len(sentence.text) - len(sentence.text.lstrip())
            valid.add(Sentence(passage, start, start + len(passage)))
    selected: list[ChartCandidate] = []
    seen: set[str] = set()
    for sentence in sorted(valid, key=lambda span: (span.start_char, span.end_char)):
        proposed = list(selected)
        for element in sorted(table.elements, key=lambda item: (item.span_start, item.span_end)):
            if element.kind not in (ElementKind.QUANTITY, ElementKind.DATE):
                continue
            if element.element_id in seen or not (
                sentence.start_char <= element.span_start < element.span_end <= sentence.end_char
                and text[element.span_start:element.span_end] == element.span_excerpt
            ):
                continue
            prefix = "q" if element.kind is ElementKind.QUANTITY else "d"
            proposed.append(ChartCandidate(f"{prefix}{len(proposed) + 1}", element, sentence))
        if len(proposed) == len(selected):
            continue
        if len(proposed) > knobs.evidence_max_readings or (
            len(candidate_block(proposed)) > knobs.evidence_max_chars
        ):
            continue
        selected = proposed
        seen.update(candidate.element.element_id for candidate in selected)
    return tuple(selected)
